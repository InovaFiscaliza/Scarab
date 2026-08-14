"""Tests for `src.pipeline`."""

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

from src.config_loader import AppConfig
from src.database import ProcessResult
from src.pipeline import (
    CONTROL_FIELDS,
    BusinessKeyError,
    IngestionPipeline,
    clean_business_key,
    compute_uuid5,
    resolve_business_key_source,
)
from src.storage_manager import StorageManager

NAMESPACE_TEXT = "38d60acc-fe97-5757-be97-834773f507f2"
NULL_STRINGS = ["", "NA", "N/A", "null", "None"]


# ---------------------------------------------------------------------------
# Shared helpers / fixtures
# ---------------------------------------------------------------------------


class _FakeDatabase:
    """Minimal stand-in for `src.database.Database`."""

    def __init__(
        self,
        result: ProcessResult | None = None,
        exc: Exception | None = None,
    ) -> None:
        self.result = result or ProcessResult(
            status="SUCESSO", message=None, client_id=None
        )
        self.exc = exc
        self.calls: list[tuple[str, dict]] = []

    def call_processar_operacao_json(
        self, filename: str, payload: dict
    ) -> ProcessResult:
        """Record the call and return the canned result (or raise)."""
        self.calls.append((filename, dict(payload)))
        if self.exc is not None:
            raise self.exc
        return self.result


def _build_config(
    tmp_path: Path,
    business_key_field: str = "",
    media_reference_json_path: str = "midia.arquivo",
    orphaned_media_hours: int = 24,
    trash_cleanup_days: int = 7,
) -> AppConfig:
    """Build an `AppConfig` with local repositories rooted under `tmp_path`."""
    raw: dict[str, Any] = {
        "name": "scarab-test",
        "check_period_seconds": 10,
        "maximum_errors_before_exit": 5,
        "uuid_namespace": NAMESPACE_TEXT,
        "business_key_field": business_key_field,
        "media_reference_json_path": media_reference_json_path,
        "null_string_values": NULL_STRINGS,
        "repositories": [
            {
                "name": "inbound",
                "type": "local",
                "path": str(tmp_path / "inbound"),
                "role": "input",
            },
            {
                "name": "media",
                "type": "local",
                "path": str(tmp_path / "media"),
                "role": "storage_media",
            },
        ],
        "prazos": {
            "orphaned_media_hours": orphaned_media_hours,
            "trash_cleanup_days": trash_cleanup_days,
        },
        "database": {
            "host": "localhost",
            "port": 5432,
            "dbname": "scarab",
            "user": "scarab_app",
            "password_env": "SCARAB_TEST_DB_PASSWORD",
            "sslmode": "prefer",
            "min_pool_size": 1,
            "max_pool_size": 5,
        },
        "sharepoint": None,
        "log": {
            "level": "DEBUG",
            "screen_output": True,
            "file_output": False,
            "file_path": [],
            "format": ["%(message)s"],
            "separator": " | ",
        },
    }
    return AppConfig.model_validate(raw)


class _Fixture:
    """Bundle of the objects a pipeline test needs."""

    def __init__(self, tmp_path: Path, config: AppConfig, db: _FakeDatabase) -> None:
        self.config = config
        self.db = db
        self.inbound = tmp_path / "inbound"
        self.media = tmp_path / "media"
        self.trash = tmp_path / "trash"
        self.inbound.mkdir(parents=True, exist_ok=True)
        storage = StorageManager(list(config.repositories), None)
        self.storage = storage
        self.pipeline = IngestionPipeline(
            config,
            storage,
            db,
            trash_path=str(self.trash),  # type: ignore[arg-type]
        )

    def write_descriptor(self, filename: str, payload: dict) -> None:
        """Write a JSON descriptor into the inbound repository."""
        (self.inbound / filename).write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )

    def write_media(self, filename: str, content: bytes = b"binary") -> Path:
        """Write a media file into the inbound repository."""
        path = self.inbound / filename
        path.write_bytes(content)
        return path


def _make_fixture(
    tmp_path: Path,
    db: _FakeDatabase | None = None,
    **config_kwargs: Any,
) -> _Fixture:
    """Build a ready-to-run pipeline fixture rooted at `tmp_path`."""
    config = _build_config(tmp_path, **config_kwargs)
    return _Fixture(tmp_path, config, db or _FakeDatabase())


def _valid_payload(**extra: Any) -> dict[str, Any]:
    """Build a minimal valid descriptor payload."""
    payload: dict[str, Any] = {"operacao": "INSERT", "nome": "Fulano"}
    payload.update(extra)
    return payload


# ---------------------------------------------------------------------------
# resolve_business_key_source / clean_business_key / compute_uuid5
# ---------------------------------------------------------------------------


def test_whole_payload_source_excludes_control_fields() -> None:
    """With `business_key_field == ""`, only control fields are dropped."""
    payload = {
        "operacao": "INSERT",
        "propriedade": "nome",
        "id": "ignored",
        "nome": "Fulano",
        "cpf": "123",
    }

    source = resolve_business_key_source(payload, "")

    assert source == '{"cpf":"123","nome":"Fulano"}'
    assert set(CONTROL_FIELDS) == {"operacao", "propriedade", "id"}


def test_whole_payload_source_is_key_order_independent() -> None:
    """Key insertion order never changes the hash source."""
    first = {"operacao": "INSERT", "b": 2, "a": 1}
    second = {"a": 1, "operacao": "UPDATE", "b": 2}

    assert resolve_business_key_source(first, "") == resolve_business_key_source(
        second, ""
    )


def test_whole_payload_source_keeps_non_ascii_characters() -> None:
    """`ensure_ascii=False` keeps accented content readable and stable."""
    source = resolve_business_key_source({"operacao": "INSERT", "nome": "João"}, "")

    assert source == '{"nome":"João"}'


def test_whole_payload_source_rejects_control_only_payload() -> None:
    """A payload with no business content cannot be hashed."""
    with pytest.raises(BusinessKeyError):
        resolve_business_key_source({"operacao": "DELETE_REGISTRO"}, "")


def test_configured_business_key_cleans_cpf_to_digits() -> None:
    """A `cpf` business key is reduced to digits only."""
    payload = {"operacao": "INSERT", "cpf": " 123.456.789-09 "}

    assert resolve_business_key_source(payload, "cpf", NULL_STRINGS) == "12345678909"


def test_configured_business_key_strips_and_lowers_other_fields() -> None:
    """Non-`cpf` business keys are stripped and lower-cased."""
    payload = {"operacao": "INSERT", "email": "  Fulano@Example.COM "}

    assert (
        resolve_business_key_source(payload, "email", NULL_STRINGS)
        == "fulano@example.com"
    )


def test_configured_business_key_supports_dot_path() -> None:
    """A dot-path business key is resolved through nested objects."""
    payload = {"operacao": "INSERT", "cliente": {"cpf": "123.456.789-09"}}

    assert (
        resolve_business_key_source(payload, "cliente.cpf", NULL_STRINGS)
        == "12345678909"
    )


@pytest.mark.parametrize("null_value", NULL_STRINGS)
def test_configured_business_key_rejects_null_strings(null_value: str) -> None:
    """Values configured as null are validation errors, not empty strings."""
    payload = {"operacao": "INSERT", "email": null_value}

    with pytest.raises(BusinessKeyError):
        resolve_business_key_source(payload, "email", NULL_STRINGS)


@pytest.mark.parametrize(
    "payload",
    [
        {"operacao": "INSERT"},
        {"operacao": "INSERT", "cpf": None},
        {"operacao": "INSERT", "cpf": {"nested": "value"}},
        {"operacao": "INSERT", "cpf": ["1", "2"]},
        {"operacao": "INSERT", "cpf": "..-"},
    ],
)
def test_configured_business_key_rejects_unusable_values(payload: dict) -> None:
    """Missing, non-scalar, or empty-after-cleaning keys are rejected."""
    with pytest.raises(BusinessKeyError):
        resolve_business_key_source(payload, "cpf", NULL_STRINGS)


def test_clean_business_key_variants() -> None:
    """`clean_business_key` normalizes per field name, dot-paths included."""
    assert clean_business_key("123.456.789-09", "cpf") == "12345678909"
    assert clean_business_key("123.456.789-09", "cliente.cpf") == "12345678909"
    assert clean_business_key("  Ab C ", "nome") == "ab c"


def test_compute_uuid5_is_deterministic() -> None:
    """`compute_uuid5` is a thin, stable wrapper over `uuid.uuid5`."""
    namespace = uuid.UUID(NAMESPACE_TEXT)

    result = compute_uuid5("12345678909", namespace)

    assert result == uuid.uuid5(namespace, "12345678909")
    assert result == compute_uuid5("12345678909", namespace)


# ---------------------------------------------------------------------------
# run_once: happy path
# ---------------------------------------------------------------------------


def test_run_once_processes_descriptor_and_dispatches_media(tmp_path: Path) -> None:
    """A valid descriptor is stored, its media dispatched, and the JSON removed."""
    fixture = _make_fixture(tmp_path)
    payload = _valid_payload(midia={"arquivo": "photo.jpg"})
    fixture.write_descriptor("doc.json", payload)
    fixture.write_media("photo.jpg", b"jpeg-bytes")

    fixture.pipeline.run_once()

    assert len(fixture.db.calls) == 1
    filename, sent_payload = fixture.db.calls[0]
    assert filename == "doc.json"
    expected_id = compute_uuid5(
        resolve_business_key_source(payload, ""), uuid.UUID(NAMESPACE_TEXT)
    )
    assert sent_payload["id"] == str(expected_id)
    assert (fixture.media / "photo.jpg").read_bytes() == b"jpeg-bytes"
    assert not (fixture.inbound / "photo.jpg").exists()
    assert not (fixture.inbound / "doc.json").exists()
    assert not fixture.trash.exists()


def test_run_once_uses_configured_business_key_for_the_identifier(
    tmp_path: Path,
) -> None:
    """When configured, only the business key field feeds the UUIDv5."""
    fixture = _make_fixture(tmp_path, business_key_field="cpf")
    fixture.write_descriptor("doc.json", _valid_payload(cpf="123.456.789-09"))

    fixture.pipeline.run_once()

    expected_id = compute_uuid5("12345678909", uuid.UUID(NAMESPACE_TEXT))
    assert fixture.db.calls[0][1]["id"] == str(expected_id)


def test_run_once_processes_descriptor_without_media(tmp_path: Path) -> None:
    """A descriptor with no media reference is processed and deleted."""
    fixture = _make_fixture(tmp_path)
    fixture.write_descriptor("doc.json", _valid_payload())

    fixture.pipeline.run_once()

    assert len(fixture.db.calls) == 1
    assert not (fixture.inbound / "doc.json").exists()


# ---------------------------------------------------------------------------
# run_once: rejections
# ---------------------------------------------------------------------------


def test_run_once_trashes_malformed_json_without_calling_the_database(
    tmp_path: Path,
) -> None:
    """Unparseable descriptors never reach the database."""
    fixture = _make_fixture(tmp_path)
    (fixture.inbound / "broken.json").write_text("{not json", encoding="utf-8")

    fixture.pipeline.run_once()

    assert fixture.db.calls == []
    assert (fixture.trash / "broken.json").exists()
    assert not (fixture.inbound / "broken.json").exists()


@pytest.mark.parametrize(
    "payload",
    [
        {"nome": "Fulano"},
        {"operacao": "DROP TABLE", "nome": "Fulano"},
        {"operacao": "insert", "nome": "Fulano"},
        {"operacao": "REMOVER_PROPRIEDADE", "nome": "Fulano"},
    ],
)
def test_run_once_trashes_invalid_operations(tmp_path: Path, payload: dict) -> None:
    """Missing, unknown, or incomplete operations are trashed, never sent."""
    fixture = _make_fixture(tmp_path)
    fixture.write_descriptor("doc.json", payload)

    fixture.pipeline.run_once()

    assert fixture.db.calls == []
    assert (fixture.trash / "doc.json").exists()


def test_run_once_trashes_descriptor_without_the_configured_business_key(
    tmp_path: Path,
) -> None:
    """A missing business key is a validation error, not a database call."""
    fixture = _make_fixture(tmp_path, business_key_field="cpf")
    fixture.write_descriptor("doc.json", _valid_payload(cpf="NA"))

    fixture.pipeline.run_once()

    assert fixture.db.calls == []
    assert (fixture.trash / "doc.json").exists()


def test_run_once_trashes_oversized_descriptor(tmp_path: Path) -> None:
    """Descriptors above the size limit are rejected before being parsed."""
    fixture = _make_fixture(tmp_path)
    fixture.write_descriptor("doc.json", _valid_payload())
    pipeline = IngestionPipeline(
        fixture.config,
        fixture.storage,
        fixture.db,  # type: ignore[arg-type]
        trash_path=str(fixture.trash),
        max_file_size_bytes=10,
    )

    pipeline.run_once()

    assert fixture.db.calls == []
    assert (fixture.trash / "doc.json").exists()


def test_run_once_trashes_json_and_media_when_the_database_reports_an_error(
    tmp_path: Path,
) -> None:
    """A database `ERRO` sends both the descriptor and its media to trash."""
    db = _FakeDatabase(ProcessResult(status="ERRO", message="boom", client_id=None))
    fixture = _make_fixture(tmp_path, db=db)
    fixture.write_descriptor("doc.json", _valid_payload(midia={"arquivo": "photo.jpg"}))
    fixture.write_media("photo.jpg")

    fixture.pipeline.run_once()

    assert (fixture.trash / "doc.json").exists()
    assert (fixture.trash / "photo.jpg").exists()
    assert not (fixture.media / "photo.jpg").exists()


def test_run_once_trashes_descriptor_with_unsafe_media_reference(
    tmp_path: Path,
) -> None:
    """An unsafe media name invalidates the descriptor before database submission."""
    outside = tmp_path / "secret.txt"
    outside.write_bytes(b"top-secret")
    fixture = _make_fixture(tmp_path)
    fixture.write_descriptor(
        "doc.json", _valid_payload(midia={"arquivo": "../secret.txt"})
    )

    fixture.pipeline.run_once()

    assert fixture.db.calls == []
    assert outside.read_bytes() == b"top-secret"
    assert not (fixture.media / "secret.txt").exists()
    assert (fixture.trash / "doc.json").exists()


def test_run_once_checks_descriptor_size_before_reading_content(tmp_path: Path) -> None:
    """An oversized descriptor is rejected without calling `read_file`."""
    config = _build_config(tmp_path)
    storage = Mock(spec=StorageManager)
    storage.list_files.return_value = ["doc.json"]
    storage.file_size_bytes.return_value = 11
    pipeline = IngestionPipeline(
        config,
        storage,
        _FakeDatabase(),
        trash_path=str(tmp_path / "trash"),
        max_file_size_bytes=10,
    )

    pipeline.run_once()

    storage.read_file.assert_not_called()
    storage.move_to_trash.assert_called_once()


def test_run_once_keeps_going_after_an_unexpected_failure(tmp_path: Path) -> None:
    """One failing file never stops the rest of the batch."""
    db = _FakeDatabase()

    def _flaky(filename: str, payload: dict) -> ProcessResult:
        db.calls.append((filename, dict(payload)))
        if filename == "a.json":
            raise RuntimeError("unexpected")
        return ProcessResult(status="SUCESSO", message=None, client_id=None)

    db.call_processar_operacao_json = _flaky  # type: ignore[method-assign]
    fixture = _make_fixture(tmp_path, db=db)
    fixture.write_descriptor("a.json", _valid_payload(nome="A"))
    fixture.write_descriptor("b.json", _valid_payload(nome="B"))

    fixture.pipeline.run_once()

    assert [name for name, _ in db.calls] == ["a.json", "b.json"]
    assert (fixture.inbound / "a.json").exists()
    assert not (fixture.inbound / "b.json").exists()


def test_run_once_propagates_infrastructure_errors_while_listing(
    tmp_path: Path,
) -> None:
    """A repository that cannot be listed is an infrastructure error for `main.py`."""
    config = _build_config(tmp_path)
    storage = Mock(spec=StorageManager)
    storage.list_files.side_effect = OSError("mount is gone")
    pipeline = IngestionPipeline(
        config,
        storage,
        _FakeDatabase(),
        trash_path=str(tmp_path / "trash"),  # type: ignore[arg-type]
    )

    with pytest.raises(OSError, match="mount is gone"):
        pipeline.run_once()


# ---------------------------------------------------------------------------
# Orphaned media
# ---------------------------------------------------------------------------


def _age_file(path: Path, hours: float) -> None:
    """Backdate a file's modification time by `hours`."""
    old = time.time() - hours * 3600
    os.utime(path, (old, old))


def test_run_once_trashes_media_older_than_orphaned_media_hours(
    tmp_path: Path,
) -> None:
    """Unclaimed media past the deadline is moved to trash."""
    fixture = _make_fixture(tmp_path, orphaned_media_hours=24)
    media = fixture.write_media("orphan.jpg")
    _age_file(media, 25)

    fixture.pipeline.run_once()

    assert (fixture.trash / "orphan.jpg").exists()
    assert not media.exists()


def test_run_once_keeps_recent_orphaned_media(tmp_path: Path) -> None:
    """Media younger than the deadline waits for its descriptor."""
    fixture = _make_fixture(tmp_path, orphaned_media_hours=24)
    media = fixture.write_media("waiting.jpg")
    _age_file(media, 5)

    fixture.pipeline.run_once()

    assert media.exists()
    assert not fixture.trash.exists()


def test_run_once_never_treats_referenced_media_as_orphaned(tmp_path: Path) -> None:
    """Old media claimed by a descriptor in the same batch is dispatched, not trashed."""
    fixture = _make_fixture(tmp_path, orphaned_media_hours=1)
    fixture.write_descriptor("doc.json", _valid_payload(midia={"arquivo": "old.jpg"}))
    media = fixture.write_media("old.jpg", b"old-bytes")
    _age_file(media, 100)

    fixture.pipeline.run_once()

    assert (fixture.media / "old.jpg").read_bytes() == b"old-bytes"
    assert not (fixture.trash / "old.jpg").exists()


def test_run_once_keeps_media_referenced_by_a_failed_descriptor(
    tmp_path: Path,
) -> None:
    """Media claimed by a descriptor that blew up is not aged out in the same cycle."""
    db = _FakeDatabase(exc=RuntimeError("unexpected"))
    fixture = _make_fixture(tmp_path, db=db, orphaned_media_hours=1)
    fixture.write_descriptor("doc.json", _valid_payload(midia={"arquivo": "old.jpg"}))
    media = fixture.write_media("old.jpg")
    _age_file(media, 100)

    fixture.pipeline.run_once()

    assert media.exists()
    assert not (fixture.trash / "old.jpg").exists()


# ---------------------------------------------------------------------------
# Trash maintenance
# ---------------------------------------------------------------------------


def test_run_trash_maintenance_compresses_then_purges(tmp_path: Path) -> None:
    """Maintenance compresses loose files and purges archives past retention."""
    config = _build_config(tmp_path, trash_cleanup_days=7)
    storage = Mock(spec=StorageManager)
    trash_path = str(tmp_path / "trash")
    pipeline = IngestionPipeline(
        config,
        storage,
        _FakeDatabase(),
        trash_path=trash_path,  # type: ignore[arg-type]
    )

    pipeline.run_trash_maintenance()

    storage.compress_trash.assert_called_once_with(trash_path)
    storage.purge_old_trash_archives.assert_called_once_with(trash_path, 7)
