"""Tests for `src.config_loader`."""

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from src.config_loader import (
    AppConfig,
    ConfigError,
    SecretNotFoundError,
    get_config,
    load_config,
)


def _default_config_data() -> dict[str, Any]:
    """Return a full, valid `default_config.json`-shaped mapping for tests."""
    return {
        "name": "scarab",
        "check_period_seconds": 10,
        "maximum_errors_before_exit": 5,
        "uuid_namespace": "38d60acc-fe97-5757-be97-834773f507f2",
        "business_key_field": "",
        "media_reference_json_path": "midia.arquivo",
        "null_string_values": ["", "NA", "N/A", "null", "None"],
        "repositories": [
            {
                "name": "local_inbound",
                "type": "local",
                "path": "/mnt/post",
                "role": "input",
            },
            {
                "name": "local_media",
                "type": "local",
                "path": "/mnt/get",
                "role": "storage_media",
            },
        ],
        "prazos": {"orphaned_media_hours": 24, "trash_cleanup_days": 7},
        "database": {
            "host": "db",
            "port": 5432,
            "dbname": "scarab",
            "user": "scarab_app",
            "password_env": "SCARAB_DB_PASSWORD",
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
            "format": [
                "%(asctime)s",
                "%(module)s: %(funcName)s:%(lineno)d",
                "%(name)s[%(process)d]",
                "%(levelname)s",
                "%(message)s",
            ],
            "separator": " | ",
        },
    }


def _write_json(path: Path, data: dict[str, Any]) -> None:
    """Write `data` as UTF-8 encoded JSON to `path`."""
    path.write_text(json.dumps(data), encoding="utf-8")


@pytest.fixture(autouse=True)
def _clear_config_cache():
    """Ensure `get_config`'s cache does not leak state between tests."""
    get_config.cache_clear()
    yield
    get_config.cache_clear()


def test_load_config_reads_defaults(tmp_path: Path) -> None:
    """`load_config` parses a directory containing only `default_config.json`."""
    _write_json(tmp_path / "default_config.json", _default_config_data())

    config = load_config(str(tmp_path))

    assert isinstance(config, AppConfig)
    assert config.name == "scarab"
    assert config.database.host == "db"
    assert config.sharepoint is None
    assert len(config.repositories) == 2
    assert [repository.path for repository in config.repositories] == [
        "/mnt/post",
        "/mnt/get",
    ]
    assert config.trash_path == "/mnt/trash"


def test_business_key_field_defaults_to_empty_string(tmp_path: Path) -> None:
    """`business_key_field` defaults to `""`, never a specific field name."""
    _write_json(tmp_path / "default_config.json", _default_config_data())

    config = load_config(str(tmp_path))

    assert config.business_key_field == ""


def test_override_merges_shallow_per_section(tmp_path: Path) -> None:
    """`config.json` overrides only the keys it sets; sibling keys inherit defaults."""
    _write_json(tmp_path / "default_config.json", _default_config_data())
    _write_json(
        tmp_path / "config.json",
        {"log": {"level": "INFO"}, "database": {"host": "db.internal"}},
    )

    config = load_config(str(tmp_path))

    assert config.log.level == "INFO"
    assert config.database.host == "db.internal"
    # Sibling keys within the same overridden section inherit the default.
    assert config.log.screen_output is True
    assert config.database.port == 5432
    assert config.database.password_env == "SCARAB_DB_PASSWORD"


def test_override_file_missing_is_ignored(tmp_path: Path) -> None:
    """Without a `config.json`, only the default values are used."""
    _write_json(tmp_path / "default_config.json", _default_config_data())

    config = load_config(str(tmp_path))

    assert config.name == "scarab"


def test_missing_default_config_raises_config_error(tmp_path: Path) -> None:
    """A missing `default_config.json` raises a descriptive `ConfigError`."""
    with pytest.raises(ConfigError):
        load_config(str(tmp_path))


def test_invalid_repository_type_raises_config_error(tmp_path: Path) -> None:
    """An unknown `repositories[].type` value raises a descriptive `ConfigError`."""
    data = _default_config_data()
    data["repositories"][0]["type"] = "ftp"
    _write_json(tmp_path / "default_config.json", data)

    with pytest.raises(ConfigError):
        load_config(str(tmp_path))


def test_invalid_repository_role_raises_config_error(tmp_path: Path) -> None:
    """An unknown `repositories[].role` value raises a descriptive `ConfigError`."""
    data = _default_config_data()
    data["repositories"][0]["role"] = "output"
    _write_json(tmp_path / "default_config.json", data)

    with pytest.raises(ConfigError):
        load_config(str(tmp_path))


def test_database_password_reads_environment_variable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`DatabaseConfig.password` reads the secret from the environment on demand."""
    _write_json(tmp_path / "default_config.json", _default_config_data())
    monkeypatch.setenv("SCARAB_DB_PASSWORD", "s3cr3t")

    config = load_config(str(tmp_path))

    assert config.database.password == "s3cr3t"


def test_database_password_missing_env_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Accessing `password` without the environment variable set raises a clear error."""
    _write_json(tmp_path / "default_config.json", _default_config_data())
    monkeypatch.delenv("SCARAB_DB_PASSWORD", raising=False)

    config = load_config(str(tmp_path))

    with pytest.raises(SecretNotFoundError):
        _ = config.database.password


def test_sharepoint_client_secret_reads_environment_variable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`SharePointConfig.client_secret` reads the secret from the environment on demand."""
    data = _default_config_data()
    data["sharepoint"] = {
        "tenant_id": "tenant-123",
        "client_id": "client-123",
        "client_secret_env": "SCARAB_SP_CLIENT_SECRET",
        "site_url": "https://example.sharepoint.com/sites/Dev",
    }
    _write_json(tmp_path / "default_config.json", data)
    monkeypatch.setenv("SCARAB_SP_CLIENT_SECRET", "sp-s3cr3t")

    config = load_config(str(tmp_path))

    assert config.sharepoint is not None
    assert config.sharepoint.client_secret == "sp-s3cr3t"


def test_config_is_frozen(tmp_path: Path) -> None:
    """Config instances are immutable (`pydantic` `frozen=True`)."""
    _write_json(tmp_path / "default_config.json", _default_config_data())

    config = load_config(str(tmp_path))

    with pytest.raises(ValidationError):
        config.name = "changed"  # type: ignore[misc]


def test_get_config_is_cached_singleton(tmp_path: Path) -> None:
    """`get_config` returns the same cached instance for the same argument."""
    _write_json(tmp_path / "default_config.json", _default_config_data())

    first = get_config(str(tmp_path))
    second = get_config(str(tmp_path))

    assert first is second
