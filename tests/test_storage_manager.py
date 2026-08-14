"""Tests for `src.storage_manager`."""

import os
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from requests.exceptions import RequestException

from src import storage_manager
from src.config_loader import RepositoryConfig, SharePointConfig
from src.storage_manager import (
    InvalidFilenameError,
    SharePointNotConfiguredError,
    SharePointOperationError,
    StorageManager,
    _SharePointBackend,
)

# ---------------------------------------------------------------------------
# Shared helpers / fixtures
# ---------------------------------------------------------------------------


def _local_repo(name: str, path: Path, role: str = "input") -> RepositoryConfig:
    """Build a `type: "local"` `RepositoryConfig` rooted at `path`."""
    return RepositoryConfig(name=name, type="local", path=str(path), role=role)  # type: ignore[arg-type]


def _sharepoint_repo(
    name: str, path: str = "/sites/Dev/Docs", role: str = "storage_media"
) -> RepositoryConfig:
    """Build a `type: "sharepoint"` `RepositoryConfig`."""
    return RepositoryConfig(name=name, type="sharepoint", path=path, role=role)  # type: ignore[arg-type]


def _sharepoint_config(**overrides: Any) -> SharePointConfig:
    """Build a valid `SharePointConfig` for tests, with `overrides` applied."""
    base: dict[str, object] = {
        "tenant_id": "contoso-tenant",
        "client_id": "client-id",
        "client_secret_env": "SCARAB_TEST_SP_SECRET",
        "site_url": "https://contoso.sharepoint.com/sites/Dev",
    }
    base.update(overrides)
    return SharePointConfig(**base)  # type: ignore[arg-type]


@pytest.fixture(autouse=True)
def _sharepoint_secret_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure the fake SharePoint client secret is resolvable unless a test removes it."""
    monkeypatch.setenv("SCARAB_TEST_SP_SECRET", "s3cr3t")


PATH_TRAVERSAL_FILENAMES = [
    "../evil.txt",
    "..",
    ".",
    "",
    "/etc/passwd",
    "a/b.txt",
    "\x00name",
]


# ---------------------------------------------------------------------------
# Local backend, via StorageManager
# ---------------------------------------------------------------------------


def test_list_files_returns_sorted_file_names(tmp_path: Path) -> None:
    """`list_files` returns only files, sorted, never sub-directories."""
    (tmp_path / "b.json").write_bytes(b"{}")
    (tmp_path / "a.json").write_bytes(b"{}")
    (tmp_path / "subdir").mkdir()
    manager = StorageManager([_local_repo("inbound", tmp_path)], None)

    assert manager.list_files("inbound") == ["a.json", "b.json"]


def test_list_files_returns_empty_when_directory_missing(tmp_path: Path) -> None:
    """A repository whose folder does not exist yet behaves as empty, not an error."""
    missing = tmp_path / "does_not_exist_yet"
    manager = StorageManager([_local_repo("inbound", missing)], None)

    assert manager.list_files("inbound") == []


def test_list_files_unknown_repository_raises(tmp_path: Path) -> None:
    """An unconfigured repository name is a clear error, not a `KeyError`."""
    manager = StorageManager([_local_repo("inbound", tmp_path)], None)

    with pytest.raises(storage_manager.UnknownRepositoryError):
        manager.list_files("does_not_exist")


def test_write_then_read_roundtrip(tmp_path: Path) -> None:
    """`write_file` followed by `read_file` returns exactly what was written."""
    manager = StorageManager([_local_repo("inbound", tmp_path)], None)

    manager.write_file("inbound", "report.json", b'{"a": 1}')

    assert manager.read_file("inbound", "report.json") == b'{"a": 1}'


def test_write_file_creates_missing_directory(tmp_path: Path) -> None:
    """The repository folder is created on first write if it does not exist yet."""
    repo_path = tmp_path / "brand_new"
    manager = StorageManager([_local_repo("inbound", repo_path)], None)

    manager.write_file("inbound", "report.json", b"data")

    assert (repo_path / "report.json").read_bytes() == b"data"


def test_delete_file_removes_it(tmp_path: Path) -> None:
    """`delete_file` removes the file so it no longer appears in `list_files`."""
    manager = StorageManager([_local_repo("inbound", tmp_path)], None)
    manager.write_file("inbound", "report.json", b"data")

    manager.delete_file("inbound", "report.json")

    assert manager.list_files("inbound") == []


def test_file_age_hours_reports_elapsed_time(tmp_path: Path) -> None:
    """`file_age_hours` reflects the file's actual modification time."""
    target = tmp_path / "report.json"
    target.write_bytes(b"data")
    two_hours_ago = datetime.now(UTC).timestamp() - 2 * 3600
    os.utime(target, (two_hours_ago, two_hours_ago))
    manager = StorageManager([_local_repo("inbound", tmp_path)], None)

    age = manager.file_age_hours("inbound", "report.json")

    assert age == pytest.approx(2.0, abs=0.05)


def test_file_age_hours_unknown_repository_raises(tmp_path: Path) -> None:
    """`file_age_hours` also validates the repository name before touching disk."""
    manager = StorageManager([_local_repo("inbound", tmp_path)], None)

    with pytest.raises(storage_manager.UnknownRepositoryError):
        manager.file_age_hours("does_not_exist", "report.json")


# ---------------------------------------------------------------------------
# Filename sanitization (security-critical)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_name", PATH_TRAVERSAL_FILENAMES)
def test_read_file_rejects_malicious_filenames(tmp_path: Path, bad_name: str) -> None:
    """`read_file` never touches disk with an unsanitized filename."""
    manager = StorageManager([_local_repo("inbound", tmp_path)], None)

    with pytest.raises(InvalidFilenameError):
        manager.read_file("inbound", bad_name)


@pytest.mark.parametrize("bad_name", PATH_TRAVERSAL_FILENAMES)
def test_write_file_rejects_malicious_filenames(tmp_path: Path, bad_name: str) -> None:
    """`write_file` never writes outside the repository root, even under attack."""
    manager = StorageManager([_local_repo("inbound", tmp_path)], None)

    with pytest.raises(InvalidFilenameError):
        manager.write_file("inbound", bad_name, b"malicious payload")

    # Nothing observable was created anywhere near the sandbox: no stray file
    # named "evil.txt"/"passwd" escaped into the parent of the repository root.
    assert not (tmp_path.parent / "evil.txt").exists()
    assert not (tmp_path.parent / "passwd").exists()


@pytest.mark.parametrize("bad_name", PATH_TRAVERSAL_FILENAMES)
def test_delete_file_rejects_malicious_filenames(tmp_path: Path, bad_name: str) -> None:
    """`delete_file` never deletes outside the repository root."""
    manager = StorageManager([_local_repo("inbound", tmp_path)], None)

    with pytest.raises(InvalidFilenameError):
        manager.delete_file("inbound", bad_name)


@pytest.mark.parametrize("bad_name", PATH_TRAVERSAL_FILENAMES)
def test_file_age_hours_rejects_malicious_filenames(
    tmp_path: Path, bad_name: str
) -> None:
    """`file_age_hours` never stats a path outside the repository root."""
    manager = StorageManager([_local_repo("inbound", tmp_path)], None)

    with pytest.raises(InvalidFilenameError):
        manager.file_age_hours("inbound", bad_name)


@pytest.mark.parametrize("bad_name", PATH_TRAVERSAL_FILENAMES)
def test_move_to_trash_rejects_malicious_filenames(
    tmp_path: Path, bad_name: str
) -> None:
    """`move_to_trash` sanitizes the filename before touching source or trash."""
    inbound = tmp_path / "inbound"
    trash = tmp_path / "trash"
    inbound.mkdir()
    manager = StorageManager([_local_repo("inbound", inbound)], None)

    with pytest.raises(InvalidFilenameError):
        manager.move_to_trash("inbound", bad_name, str(trash))

    assert not trash.exists() or list(trash.iterdir()) == []


def test_write_file_rejects_filename_even_for_sharepoint_repository(
    monkeypatch,
) -> None:
    """Basename sanitization applies regardless of backend type."""
    fake_backend = _FakeBackend()
    monkeypatch.setattr(
        storage_manager, "_SharePointBackend", lambda sharepoint: fake_backend
    )
    manager = StorageManager([_sharepoint_repo("sp_docs")], _sharepoint_config())

    with pytest.raises(InvalidFilenameError):
        manager.write_file("sp_docs", "../evil.txt", b"data")

    assert fake_backend.calls == []


# ---------------------------------------------------------------------------
# move_to_trash (happy path)
# ---------------------------------------------------------------------------


def test_move_to_trash_moves_content_and_deletes_source(tmp_path: Path) -> None:
    """The file ends up in `trash_path` with identical content and is gone from source."""
    inbound = tmp_path / "inbound"
    trash = tmp_path / "trash"
    inbound.mkdir()
    manager = StorageManager([_local_repo("inbound", inbound)], None)
    manager.write_file("inbound", "orphan.bin", b"orphan media")

    manager.move_to_trash("inbound", "orphan.bin", str(trash))

    assert not (inbound / "orphan.bin").exists()
    assert (trash / "orphan.bin").read_bytes() == b"orphan media"


# ---------------------------------------------------------------------------
# compress_trash / purge_old_trash_archives
# ---------------------------------------------------------------------------


def test_compress_trash_archives_and_removes_originals(tmp_path: Path) -> None:
    """Loose files are zipped into one archive and removed afterwards."""
    (tmp_path / "a.json").write_bytes(b"content-a")
    (tmp_path / "b.bin").write_bytes(b"content-b")
    manager = StorageManager([], None)

    manager.compress_trash(str(tmp_path))

    remaining = list(tmp_path.iterdir())
    assert len(remaining) == 1
    archive_path = remaining[0]
    assert archive_path.suffix == ".zip"
    with zipfile.ZipFile(archive_path) as archive:
        assert sorted(archive.namelist()) == ["a.json", "b.bin"]
        assert archive.read("a.json") == b"content-a"


def test_compress_trash_noop_when_directory_empty(tmp_path: Path) -> None:
    """An empty (or missing) trash folder produces no archive."""
    manager = StorageManager([], None)

    manager.compress_trash(str(tmp_path))

    assert list(tmp_path.iterdir()) == []


def test_compress_trash_noop_when_directory_missing(tmp_path: Path) -> None:
    """`compress_trash` never creates the trash directory just to find it empty."""
    missing = tmp_path / "does_not_exist"
    manager = StorageManager([], None)

    manager.compress_trash(str(missing))

    assert not missing.exists()


def test_compress_trash_does_not_rezip_existing_archives(tmp_path: Path) -> None:
    """A previous archive is left alone; only newly loose files are zipped."""
    old_archive = tmp_path / "trash_20200101_000000_000000.zip"
    with zipfile.ZipFile(old_archive, "w") as archive:
        archive.writestr("already_archived.txt", "old content")
    (tmp_path / "new_loose_file.txt").write_bytes(b"new content")
    manager = StorageManager([], None)

    manager.compress_trash(str(tmp_path))

    assert old_archive.exists()
    with zipfile.ZipFile(old_archive) as archive:
        assert archive.namelist() == ["already_archived.txt"]
    new_archives = [p for p in tmp_path.glob("*.zip") if p != old_archive]
    assert len(new_archives) == 1
    with zipfile.ZipFile(new_archives[0]) as archive:
        assert archive.namelist() == ["new_loose_file.txt"]


def test_purge_old_trash_archives_removes_only_old_ones(tmp_path: Path) -> None:
    """Only archives older than `older_than_days` are deleted."""
    old_archive = tmp_path / "old.zip"
    recent_archive = tmp_path / "recent.zip"
    for archive_path in (old_archive, recent_archive):
        with zipfile.ZipFile(archive_path, "w") as archive:
            archive.writestr("file.txt", "content")
    now = datetime.now(UTC).timestamp()
    os.utime(old_archive, (now - 10 * 86400, now - 10 * 86400))
    os.utime(recent_archive, (now - 1 * 86400, now - 1 * 86400))
    manager = StorageManager([], None)

    manager.purge_old_trash_archives(str(tmp_path), older_than_days=7)

    assert not old_archive.exists()
    assert recent_archive.exists()


def test_purge_old_trash_archives_ignores_non_zip_files(tmp_path: Path) -> None:
    """Only `.zip` archives are purged; other old files are left untouched."""
    old_text_file = tmp_path / "old.txt"
    old_text_file.write_bytes(b"content")
    now = datetime.now(UTC).timestamp()
    os.utime(old_text_file, (now - 10 * 86400, now - 10 * 86400))
    manager = StorageManager([], None)

    manager.purge_old_trash_archives(str(tmp_path), older_than_days=7)

    assert old_text_file.exists()


def test_purge_old_trash_archives_noop_when_directory_missing(tmp_path: Path) -> None:
    """A missing trash directory is not an error."""
    missing = tmp_path / "does_not_exist"
    manager = StorageManager([], None)

    manager.purge_old_trash_archives(str(missing), older_than_days=7)

    assert not missing.exists()


# ---------------------------------------------------------------------------
# SharePoint repository selection / delegation (fake backend, no network)
# ---------------------------------------------------------------------------


class _FakeBackend:
    """Fake `StorageBackend` used to test `StorageManager` delegation without office365."""

    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []
        self.files: dict[str, bytes] = {}

    def list_files(self, path: str) -> list[str]:
        self.calls.append(("list_files", path))
        return sorted(self.files)

    def read_file(self, path: str, filename: str) -> bytes:
        self.calls.append(("read_file", path, filename))
        return self.files[filename]

    def write_file(self, path: str, filename: str, content: bytes) -> None:
        self.calls.append(("write_file", path, filename, content))
        self.files[filename] = content

    def delete_file(self, path: str, filename: str) -> None:
        self.calls.append(("delete_file", path, filename))
        del self.files[filename]

    def file_age_hours(self, path: str, filename: str) -> float:
        self.calls.append(("file_age_hours", path, filename))
        return 1.5


def test_storage_manager_delegates_to_sharepoint_backend(monkeypatch) -> None:
    """`StorageManager` routes `type: "sharepoint"` repositories to the SharePoint backend."""
    fake_backend = _FakeBackend()
    monkeypatch.setattr(
        storage_manager, "_SharePointBackend", lambda sharepoint: fake_backend
    )
    manager = StorageManager([_sharepoint_repo("sp_docs")], _sharepoint_config())

    manager.write_file("sp_docs", "report.json", b"data")
    content = manager.read_file("sp_docs", "report.json")

    assert content == b"data"
    assert (
        "write_file",
        "/sites/Dev/Docs",
        "report.json",
        b"data",
    ) in fake_backend.calls
    assert ("read_file", "/sites/Dev/Docs", "report.json") in fake_backend.calls


def test_storage_manager_construction_does_not_require_sharepoint_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Building `StorageManager` with a real `_SharePointBackend` never touches the network."""
    monkeypatch.delenv("SCARAB_TEST_SP_SECRET", raising=False)

    manager = StorageManager([_sharepoint_repo("sp_docs")], _sharepoint_config())

    assert isinstance(manager, StorageManager)


def test_sharepoint_repository_without_config_raises_on_use(tmp_path: Path) -> None:
    """A `type: "sharepoint"` repository without a `SharePointConfig` fails clearly, on use."""
    manager = StorageManager([_sharepoint_repo("sp_docs")], None)

    with pytest.raises(SharePointNotConfiguredError):
        manager.list_files("sp_docs")


# ---------------------------------------------------------------------------
# _SharePointBackend: lazy context, and error wrapping (no real network)
# ---------------------------------------------------------------------------


def test_sharepoint_backend_context_is_built_lazily_and_cached() -> None:
    """Constructing the backend does no I/O; `_get_context()` caches the result."""
    backend = _SharePointBackend(_sharepoint_config())

    context_1 = backend._get_context()
    context_2 = backend._get_context()

    assert context_1 is context_2


class _FakeSPFile:
    """Minimal stand-in for an `office365` `File` object."""

    def __init__(self, name: str, time_last_modified: datetime | None = None) -> None:
        self.name = name
        self.time_last_modified = time_last_modified
        self.deleted = False

    def delete_object(self) -> None:
        """Mark this fake file as deleted, mirroring `File.delete_object()`."""
        self.deleted = True


class _FakeSPFolder:
    """Minimal stand-in for an `office365` `Folder` object."""

    def __init__(self, files: list[_FakeSPFile]) -> None:
        self.files = files


class _FakeSPWeb:
    """Minimal stand-in for `ClientContext.web`."""

    def __init__(
        self, folder: _FakeSPFolder | None = None, file: _FakeSPFile | None = None
    ) -> None:
        self._folder = folder
        self._file = file

    def get_folder_by_server_relative_path(self, path: str) -> _FakeSPFolder:
        """Mimic `Web.get_folder_by_server_relative_path()`."""
        assert self._folder is not None
        return self._folder

    def get_file_by_server_relative_path(self, url: str) -> _FakeSPFile:
        """Mimic `Web.get_file_by_server_relative_path()`."""
        assert self._file is not None
        return self._file


class _FakeSPContext:
    """Minimal stand-in for `office365`'s `ClientContext`."""

    def __init__(
        self, web: _FakeSPWeb, execute_query_exc: Exception | None = None
    ) -> None:
        self.web = web
        self.execute_query_exc = execute_query_exc
        self.loaded: list[tuple[Any, Any]] = []
        self.execute_count = 0

    def load(
        self, client_object: Any, properties_to_retrieve: Any = None
    ) -> "_FakeSPContext":
        """Mimic `ClientContext.load()`."""
        self.loaded.append((client_object, properties_to_retrieve))
        return self

    def execute_query(self) -> "_FakeSPContext":
        """Mimic `ClientContext.execute_query()`, optionally raising a canned error."""
        self.execute_count += 1
        if self.execute_query_exc is not None:
            raise self.execute_query_exc
        return self


def _raise_request_exception(*_args: object, **_kwargs: object) -> None:
    """Raise `RequestException`, standing in for a broken SharePoint call."""
    raise RequestException("boom")


def test_sharepoint_backend_list_files(monkeypatch: pytest.MonkeyPatch) -> None:
    """`list_files` loads the folder's files and returns their names."""
    folder = _FakeSPFolder([_FakeSPFile("a.json"), _FakeSPFile("b.json")])
    ctx = _FakeSPContext(_FakeSPWeb(folder=folder))
    backend = _SharePointBackend(_sharepoint_config())
    monkeypatch.setattr(backend, "_get_context", lambda: ctx)

    result = backend.list_files("/sites/Dev/Docs")

    assert result == ["a.json", "b.json"]
    assert ctx.execute_count == 1


def test_sharepoint_backend_list_files_wraps_network_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed request while listing files is reported as `SharePointOperationError`."""
    ctx = _FakeSPContext(
        _FakeSPWeb(folder=_FakeSPFolder([])), execute_query_exc=RequestException("boom")
    )
    backend = _SharePointBackend(_sharepoint_config())
    monkeypatch.setattr(backend, "_get_context", lambda: ctx)

    with pytest.raises(SharePointOperationError):
        backend.list_files("/sites/Dev/Docs")


def test_sharepoint_backend_delete_file(monkeypatch: pytest.MonkeyPatch) -> None:
    """`delete_file` calls `delete_object()` on the resolved file and executes the query."""
    file_obj = _FakeSPFile("a.json")
    ctx = _FakeSPContext(_FakeSPWeb(file=file_obj))
    backend = _SharePointBackend(_sharepoint_config())
    monkeypatch.setattr(backend, "_get_context", lambda: ctx)

    backend.delete_file("/sites/Dev/Docs", "a.json")

    assert file_obj.deleted is True
    assert ctx.execute_count == 1


def test_sharepoint_backend_delete_file_wraps_network_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed request while deleting is reported as `SharePointOperationError`."""
    ctx = _FakeSPContext(
        _FakeSPWeb(file=_FakeSPFile("a.json")),
        execute_query_exc=RequestException("boom"),
    )
    backend = _SharePointBackend(_sharepoint_config())
    monkeypatch.setattr(backend, "_get_context", lambda: ctx)

    with pytest.raises(SharePointOperationError):
        backend.delete_file("/sites/Dev/Docs", "a.json")


def test_sharepoint_backend_file_age_hours(monkeypatch: pytest.MonkeyPatch) -> None:
    """`file_age_hours` reads `TimeLastModified` and converts it to elapsed hours."""
    modified = datetime.now(UTC) - timedelta(hours=3)
    file_obj = _FakeSPFile("a.json", time_last_modified=modified)
    ctx = _FakeSPContext(_FakeSPWeb(file=file_obj))
    backend = _SharePointBackend(_sharepoint_config())
    monkeypatch.setattr(backend, "_get_context", lambda: ctx)

    age = backend.file_age_hours("/sites/Dev/Docs", "a.json")

    assert age == pytest.approx(3.0, abs=0.01)


def test_sharepoint_backend_file_age_hours_raises_when_no_timestamp(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A file with no reported `TimeLastModified` is a clear error, not a crash."""
    file_obj = _FakeSPFile("a.json", time_last_modified=None)
    ctx = _FakeSPContext(_FakeSPWeb(file=file_obj))
    backend = _SharePointBackend(_sharepoint_config())
    monkeypatch.setattr(backend, "_get_context", lambda: ctx)

    with pytest.raises(SharePointOperationError):
        backend.file_age_hours("/sites/Dev/Docs", "a.json")


def test_sharepoint_backend_read_file_returns_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`read_file` returns the response body from `File.open_binary`."""

    class _FakeResponse:
        def __init__(self, content: bytes) -> None:
            self.content = content

    backend = _SharePointBackend(_sharepoint_config())
    monkeypatch.setattr(backend, "_get_context", lambda: object())
    monkeypatch.setattr(
        storage_manager.File, "open_binary", lambda ctx, url: _FakeResponse(b"hello")
    )

    content = backend.read_file("/sites/Dev/Docs", "a.json")

    assert content == b"hello"


def test_sharepoint_backend_read_file_wraps_network_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed download is reported as `SharePointOperationError`, chaining the cause."""
    backend = _SharePointBackend(_sharepoint_config())
    monkeypatch.setattr(backend, "_get_context", lambda: object())
    monkeypatch.setattr(storage_manager.File, "open_binary", _raise_request_exception)

    with pytest.raises(SharePointOperationError):
        backend.read_file("/sites/Dev/Docs", "a.json")


def test_sharepoint_backend_write_file_calls_save_binary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`write_file` uploads via `File.save_binary` with the joined server-relative URL."""
    calls: list[tuple[str, bytes]] = []

    def _fake_save_binary(ctx: object, url: str, content: bytes) -> None:
        calls.append((url, content))

    backend = _SharePointBackend(_sharepoint_config())
    monkeypatch.setattr(backend, "_get_context", lambda: object())
    monkeypatch.setattr(storage_manager.File, "save_binary", _fake_save_binary)

    backend.write_file("/sites/Dev/Docs", "a.json", b"hello")

    assert calls == [("/sites/Dev/Docs/a.json", b"hello")]


def test_sharepoint_backend_write_file_wraps_network_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed upload is reported as `SharePointOperationError`, not left to crash the loop."""
    backend = _SharePointBackend(_sharepoint_config())
    monkeypatch.setattr(backend, "_get_context", lambda: object())
    monkeypatch.setattr(storage_manager.File, "save_binary", _raise_request_exception)

    with pytest.raises(SharePointOperationError):
        backend.write_file("/sites/Dev/Docs", "a.json", b"data")
