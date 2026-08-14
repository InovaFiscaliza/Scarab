"""Storage backend abstraction for the Scarab rewrite.

Exposes a single `StorageManager` facade over two backends: local filesystem
repositories and SharePoint document libraries (Client Credentials flow via
`office365-rest-python-client`). Every filename accepted by `StorageManager`
is treated as untrusted (it may come straight from a descriptor JSON payload)
and is sanitized here, before any read/write/delete/move is delegated to a
backend.
"""

import logging
import os
import shutil
import time
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from office365.runtime.auth.client_credential import ClientCredential
from office365.sharepoint.client_context import ClientContext
from office365.sharepoint.files.file import File
from requests.exceptions import RequestException

from src.config_loader import RepositoryConfig, SharePointConfig

logger = logging.getLogger(__name__)


class StorageError(Exception):
    """Base class for all `storage_manager` errors."""


class InvalidFilenameError(StorageError):
    """Raised when a filename is empty, not a plain name, or escapes its root.

    Callers (e.g. `pipeline.py`) should treat this as an invalid input file
    (e.g. move it to `/trash`) instead of retrying the operation.
    """


class UnknownRepositoryError(StorageError):
    """Raised when a repository name is not present in the configured list."""


class SharePointNotConfiguredError(StorageError):
    """Raised when a `type: "sharepoint"` repository is used without a `SharePointConfig`."""


class SharePointOperationError(StorageError):
    """Raised when a SharePoint network, authentication, or API call fails.

    Wraps the underlying `requests`/`office365` exception so the caller can
    decide how to proceed instead of the process crashing.
    """


class StorageBackend(Protocol):
    """Structural interface implemented by every storage backend."""

    def list_files(self, path: str) -> list[str]:
        """Return the names of the files directly inside `path`."""
        ...

    def read_file(self, path: str, filename: str) -> bytes:
        """Return the raw content of `filename` inside `path`."""
        ...

    def write_file(self, path: str, filename: str, content: bytes) -> None:
        """Create or overwrite `filename` inside `path` with `content`."""
        ...

    def delete_file(self, path: str, filename: str) -> None:
        """Delete `filename` inside `path`."""
        ...

    def file_age_hours(self, path: str, filename: str) -> float:
        """Return how many hours have passed since `filename` was last modified."""
        ...

    def file_size_bytes(self, path: str, filename: str) -> int:
        """Return the size of `filename` in bytes without reading its content."""
        ...


def _sanitize_filename(filename: str) -> str:
    """Validate that `filename` is a plain file name with no path components.

    Args:
        filename: Untrusted filename, e.g. read from a descriptor JSON payload.

    Returns:
        `filename` itself, unchanged, once validated.

    Raises:
        InvalidFilenameError: If `filename` is empty, contains a null byte, or
            `os.path.basename()` resolves it to anything other than the exact
            original string (i.e. it embeds directory components or a drive
            letter), or it is `"."`/`".."`. The original string is never
            silently rewritten into a different, valid file name.
    """
    if not filename or "\x00" in filename:
        raise InvalidFilenameError(f"Invalid filename: {filename!r}")
    basename = os.path.basename(filename)
    if basename != filename or basename in (".", ".."):
        raise InvalidFilenameError(
            f"Filename {filename!r} is not a plain file name (path traversal attempt?)"
        )
    return basename


def _ensure_within_root(root: str, filename: str) -> Path:
    """Resolve `root/filename` and confirm the result stays inside `root`.

    Args:
        root: Repository or trash root directory.
        filename: Already `_sanitize_filename`-validated file name.

    Returns:
        The resolved absolute path to `filename` inside `root`.

    Raises:
        InvalidFilenameError: If the resolved path is not inside `root`.
    """
    root_path = Path(root).resolve()
    candidate = (root_path / filename).resolve()
    if not candidate.is_relative_to(root_path):
        raise InvalidFilenameError(
            f"Resolved path for {filename!r} escapes repository root {root!r}"
        )
    return candidate


class _LocalBackend:
    """`StorageBackend` implementation for local filesystem repositories."""

    def list_files(self, path: str) -> list[str]:
        """Return the names of the files directly inside `path`.

        Returns an empty list if `path` does not exist yet.
        """
        root = Path(path)
        if not root.is_dir():
            return []
        return sorted(entry.name for entry in root.iterdir() if entry.is_file())

    def read_file(self, path: str, filename: str) -> bytes:
        """Return the raw content of `filename` inside `path`."""
        return (Path(path) / filename).read_bytes()

    def write_file(self, path: str, filename: str, content: bytes) -> None:
        """Create or overwrite `filename` inside `path`, creating `path` if needed."""
        root = Path(path)
        root.mkdir(parents=True, exist_ok=True)
        (root / filename).write_bytes(content)

    def delete_file(self, path: str, filename: str) -> None:
        """Delete `filename` inside `path`."""
        (Path(path) / filename).unlink()

    def file_age_hours(self, path: str, filename: str) -> float:
        """Return how many hours have passed since `filename` was last modified."""
        mtime = (Path(path) / filename).stat().st_mtime
        return (time.time() - mtime) / 3600

    def file_size_bytes(self, path: str, filename: str) -> int:
        """Return the file size without loading the file into memory."""
        return (Path(path) / filename).stat().st_size


class _SharePointBackend:
    """`StorageBackend` implementation for a SharePoint document library.

    Authenticates lazily, via the Client Credentials flow, on the first call
    that actually needs the connection: constructing this class, and calling
    `_get_context()` itself, never perform network I/O (the underlying SDK
    only contacts SharePoint/ACS once a request is actually executed).
    """

    def __init__(self, sharepoint: SharePointConfig) -> None:
        """Store the SharePoint configuration; no connection is opened yet.

        Args:
            sharepoint: Client Credentials settings for the target site.
        """
        self._config = sharepoint
        self._context: ClientContext | None = None

    def _get_context(self) -> ClientContext:
        """Build (once) and return the authenticated `ClientContext`."""
        if self._context is None:
            credentials = ClientCredential(
                self._config.client_id, self._config.client_secret
            )
            self._context = ClientContext(self._config.site_url).with_credentials(
                credentials
            )
        return self._context

    @staticmethod
    def _server_relative_url(path: str, filename: str) -> str:
        """Join a repository-relative folder path and file name into one URL."""
        return f"{path.rstrip('/')}/{filename}"

    def list_files(self, path: str) -> list[str]:
        """Return the names of the files directly inside the `path` folder.

        Raises:
            SharePointOperationError: If the SharePoint request fails.
        """
        try:
            ctx = self._get_context()
            files = ctx.web.get_folder_by_server_relative_path(path).files
            ctx.load(files)
            ctx.execute_query()
        except RequestException:
            logger.exception("Failed to list SharePoint files in %r", path)
            raise SharePointOperationError(
                f"Failed to list files in {path!r}"
            ) from None
        return [file.name for file in files]

    def read_file(self, path: str, filename: str) -> bytes:
        """Return the raw content of `filename` inside the `path` folder.

        Raises:
            SharePointOperationError: If the SharePoint request fails.
        """
        server_relative_url = self._server_relative_url(path, filename)
        try:
            response = File.open_binary(self._get_context(), server_relative_url)
        except RequestException:
            logger.exception("Failed to read SharePoint file %r", server_relative_url)
            raise SharePointOperationError(
                f"Failed to read {server_relative_url!r}"
            ) from None
        return response.content

    def write_file(self, path: str, filename: str, content: bytes) -> None:
        """Create or overwrite `filename` inside the `path` folder with `content`.

        Raises:
            SharePointOperationError: If the SharePoint request fails.
        """
        server_relative_url = self._server_relative_url(path, filename)
        try:
            File.save_binary(self._get_context(), server_relative_url, content)
        except RequestException:
            logger.exception("Failed to write SharePoint file %r", server_relative_url)
            raise SharePointOperationError(
                f"Failed to write {server_relative_url!r}"
            ) from None

    def delete_file(self, path: str, filename: str) -> None:
        """Delete `filename` inside the `path` folder.

        Raises:
            SharePointOperationError: If the SharePoint request fails.
        """
        server_relative_url = self._server_relative_url(path, filename)
        try:
            ctx = self._get_context()
            ctx.web.get_file_by_server_relative_path(
                server_relative_url
            ).delete_object()
            ctx.execute_query()
        except RequestException:
            logger.exception("Failed to delete SharePoint file %r", server_relative_url)
            raise SharePointOperationError(
                f"Failed to delete {server_relative_url!r}"
            ) from None

    def file_age_hours(self, path: str, filename: str) -> float:
        """Return how many hours have passed since `filename` was last modified.

        Raises:
            SharePointOperationError: If the SharePoint request fails, or it
                succeeds but reports no last-modified time.
        """
        server_relative_url = self._server_relative_url(path, filename)
        try:
            ctx = self._get_context()
            file_obj = ctx.web.get_file_by_server_relative_path(server_relative_url)
            ctx.load(file_obj, ["TimeLastModified"])
            ctx.execute_query()
            modified = file_obj.time_last_modified
        except RequestException:
            logger.exception(
                "Failed to read SharePoint metadata for %r", server_relative_url
            )
            raise SharePointOperationError(
                f"Failed to read metadata for {server_relative_url!r}"
            ) from None
        if modified is None:
            raise SharePointOperationError(
                f"SharePoint returned no last-modified time for {server_relative_url!r}"
            )
        if modified.tzinfo is None:
            modified = modified.replace(tzinfo=UTC)
        return (datetime.now(UTC) - modified).total_seconds() / 3600

    def file_size_bytes(self, path: str, filename: str) -> int:
        """Return the remote SharePoint file size without downloading it.

        Raises:
            SharePointOperationError: If the SharePoint request fails or does
                not return a numeric file length.
        """
        server_relative_url = self._server_relative_url(path, filename)
        try:
            ctx = self._get_context()
            file_obj = ctx.web.get_file_by_server_relative_path(server_relative_url)
            ctx.load(file_obj, ["Length"])
            ctx.execute_query()
            size = getattr(file_obj, "length", None)
        except RequestException:
            logger.exception(
                "Failed to read SharePoint size for %r", server_relative_url
            )
            raise SharePointOperationError(
                f"Failed to read size for {server_relative_url!r}"
            ) from None
        if not isinstance(size, int):
            raise SharePointOperationError(
                f"SharePoint returned no numeric size for {server_relative_url!r}"
            )
        return size


class StorageManager:
    """Public facade: selects the right backend per repository and sanitizes filenames."""

    def __init__(
        self, repositories: list[RepositoryConfig], sharepoint: SharePointConfig | None
    ) -> None:
        """Index `repositories` by name and build the backends they may need.

        Args:
            repositories: Input and storage-media repositories to serve.
            sharepoint: Client Credentials settings shared by every
                `type: "sharepoint"` repository, or `None` if none is used.
        """
        self._repositories: dict[str, RepositoryConfig] = {
            repo.name: repo for repo in repositories
        }
        self._local_backend: StorageBackend = _LocalBackend()
        self._sharepoint_backend: StorageBackend | None = (
            _SharePointBackend(sharepoint) if sharepoint is not None else None
        )

    def _get_repository(self, repository_name: str) -> RepositoryConfig:
        """Return the configured repository named `repository_name`.

        Raises:
            UnknownRepositoryError: If no repository with that name exists.
        """
        try:
            return self._repositories[repository_name]
        except KeyError:
            raise UnknownRepositoryError(
                f"Unknown repository: {repository_name!r}"
            ) from None

    def _get_backend(self, repository: RepositoryConfig) -> StorageBackend:
        """Return the backend serving `repository`.

        Raises:
            SharePointNotConfiguredError: If `repository.type` is
                `"sharepoint"` but no `SharePointConfig` was provided.
        """
        if repository.type == "local":
            return self._local_backend
        if self._sharepoint_backend is None:
            raise SharePointNotConfiguredError(
                f"Repository {repository.name!r} requires SharePoint, "
                "but no SharePointConfig was provided"
            )
        return self._sharepoint_backend

    def _safe_filename(self, repository: RepositoryConfig, filename: str) -> str:
        """Sanitize `filename`, plus root containment for local repositories.

        Raises:
            InvalidFilenameError: If `filename` fails sanitization, or (for
                local repositories) resolves outside `repository.path`.
        """
        safe_name = _sanitize_filename(filename)
        if repository.type == "local":
            _ensure_within_root(repository.path, safe_name)
        return safe_name

    def validate_filename(self, repository_name: str, filename: str) -> str:
        """Validate and return a filename without performing storage I/O."""
        repository = self._get_repository(repository_name)
        return self._safe_filename(repository, filename)

    def list_files(self, repository_name: str) -> list[str]:
        """List the file names currently present in `repository_name`."""
        repository = self._get_repository(repository_name)
        backend = self._get_backend(repository)
        return backend.list_files(repository.path)

    def read_file(self, repository_name: str, filename: str) -> bytes:
        """Return the raw content of `filename` inside `repository_name`."""
        repository = self._get_repository(repository_name)
        backend = self._get_backend(repository)
        safe_name = self._safe_filename(repository, filename)
        return backend.read_file(repository.path, safe_name)

    def write_file(self, repository_name: str, filename: str, content: bytes) -> None:
        """Create or overwrite `filename` inside `repository_name` with `content`."""
        repository = self._get_repository(repository_name)
        backend = self._get_backend(repository)
        safe_name = self._safe_filename(repository, filename)
        backend.write_file(repository.path, safe_name, content)

    def delete_file(self, repository_name: str, filename: str) -> None:
        """Delete `filename` from `repository_name`."""
        repository = self._get_repository(repository_name)
        backend = self._get_backend(repository)
        safe_name = self._safe_filename(repository, filename)
        backend.delete_file(repository.path, safe_name)

    def move_to_trash(
        self, repository_name: str, filename: str, trash_path: str
    ) -> None:
        """Move `filename` from `repository_name` into the local `trash_path` folder.

        The trash directory is always local, regardless of the source
        repository's backend: the file is read from its source backend and
        written to disk via the local backend, before being deleted from the
        source.
        """
        repository = self._get_repository(repository_name)
        backend = self._get_backend(repository)
        safe_name = self._safe_filename(repository, filename)
        source_path = (
            _ensure_within_root(repository.path, safe_name)
            if repository.type == "local"
            else None
        )
        target_path = _ensure_within_root(trash_path, safe_name)
        if source_path is not None:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            if target_path.exists():
                target_path.unlink()
            shutil.move(str(source_path), str(target_path))
            return
        content = backend.read_file(repository.path, safe_name)
        self._local_backend.write_file(trash_path, safe_name, content)
        backend.delete_file(repository.path, safe_name)

    def file_age_hours(self, repository_name: str, filename: str) -> float:
        """Return how many hours have passed since `filename` was last modified."""
        repository = self._get_repository(repository_name)
        backend = self._get_backend(repository)
        safe_name = self._safe_filename(repository, filename)
        return backend.file_age_hours(repository.path, safe_name)

    def file_size_bytes(self, repository_name: str, filename: str) -> int:
        """Return a file size without reading its content into memory."""
        repository = self._get_repository(repository_name)
        backend = self._get_backend(repository)
        safe_name = self._safe_filename(repository, filename)
        return backend.file_size_bytes(repository.path, safe_name)

    def compress_trash(self, trash_path: str) -> None:
        """Compress every loose file directly inside `trash_path` into one archive.

        Uses a `.zip` archive (via `zipfile.ZipFile`), named
        `trash_<YYYYmmdd_HHMMSS_ffffff>.zip`, so no extra dependency beyond
        the standard library is needed. Files already ending in `.zip` are
        treated as previous archives and left untouched (their age is
        handled by `purge_old_trash_archives()`); if no other loose file
        remains, this is a no-op. Originals are only deleted once the
        archive has been written successfully.
        """
        root = Path(trash_path)
        if not root.is_dir():
            return
        loose_files = [
            entry
            for entry in root.iterdir()
            if entry.is_file() and entry.suffix != ".zip"
        ]
        if not loose_files:
            return
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S_%f")
        archive_path = root / f"trash_{timestamp}.zip"
        with zipfile.ZipFile(
            archive_path, mode="w", compression=zipfile.ZIP_DEFLATED
        ) as archive:
            for file_path in loose_files:
                archive.write(file_path, arcname=file_path.name)
        for file_path in loose_files:
            file_path.unlink()

    def purge_old_trash_archives(self, trash_path: str, older_than_days: int) -> None:
        """Delete `.zip` archives inside `trash_path` older than `older_than_days`.

        Age is measured from each archive's last-modified time (`st_mtime`).
        """
        root = Path(trash_path)
        if not root.is_dir():
            return
        cutoff_seconds = older_than_days * 86400
        now = time.time()
        for archive_path in root.glob("*.zip"):
            if (
                archive_path.is_file()
                and (now - archive_path.stat().st_mtime) > cutoff_seconds
            ):
                archive_path.unlink()
