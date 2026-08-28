"""Ingestion pipeline for the Scarab rewrite.

Scans every `role: "input"` repository, classifies each file as a JSON
descriptor or as media, validates and hashes descriptors into deterministic
UUIDv5 identifiers, hands them to `processar_operacao_json` through
`src.database.Database`, and moves the associated media to the
`role: "storage_media"` repositories. Invalid files and failed operations are
moved to the trash folder; media that stays unclaimed for longer than
`prazos.orphaned_media_hours` is trashed as well.

Every filename that originates from a JSON payload is untrusted: this module
never builds filesystem paths on its own, it always goes through
`StorageManager`, which owns filename sanitization and root containment.
"""

import json
import logging
import re
import uuid
from collections.abc import Sequence
from typing import Any

from src.config_loader import AppConfig
from src.database import Database
from src.storage_manager import InvalidFilenameError, StorageError, StorageManager

logger = logging.getLogger(__name__)

CONTROL_FIELDS: frozenset[str] = frozenset({"operacao", "propriedade", "id"})
"""Root JSON keys that are never part of the business content used to compute the UUIDv5."""

VALID_OPERATIONS: frozenset[str] = frozenset(
    {"INSERT", "UPDATE", "DELETE_REGISTRO", "REMOVER_PROPRIEDADE"}
)
"""The only accepted values of the payload's `"operacao"` key."""

JSON_EXTENSION: str = ".json"
"""Extension that identifies a descriptor file; every other file is treated as media."""

DEFAULT_MAX_FILE_SIZE_BYTES: int = 50 * 1024 * 1024
"""Compatibility fallback for configurations created before Module 06."""


class PipelineError(Exception):
    """Base class for all `pipeline` errors."""


class InvalidPayloadError(PipelineError):
    """Raised when a descriptor file is unusable and must be trashed without touching the database."""


class BusinessKeyError(InvalidPayloadError):
    """Raised when the configured business key is missing, null, or empty after cleaning."""


def clean_business_key(value: str, field_name: str) -> str:
    """Normalize a business key value according to the field it came from.

    Args:
        value: Raw value read from the payload.
    Returns:
        Digits only when the field is `cpf`, otherwise the value stripped of
        surrounding whitespace and lower-cased.
    """
    if field_name.rsplit(".", 1)[-1].casefold() == "cpf":
        return re.sub(r"\D", "", value)
    return value.strip().lower()


def _resolve_dot_path(payload: dict[str, Any], dot_path: str) -> Any:
    """Walk a dot-separated path inside a nested mapping.

    Args:
        payload: Parsed JSON payload.
        dot_path: Path such as `"midia.arquivo"`.

    Returns:
        The value found at `dot_path`, or `None` if any segment is missing or
        traverses a non-mapping value.
    """
    current: Any = payload
    for segment in dot_path.split("."):
        if not isinstance(current, dict) or segment not in current:
            return None
        current = current[segment]
    return current


def resolve_business_key_source(
    payload: dict,
    business_key_field: str,
    null_string_values: Sequence[str] | None = None,
) -> str:
    """Build the deterministic string used as the UUIDv5 source for `payload`.

    When `business_key_field` is empty (the default), there is no fixed
    business key: the whole data content of the payload takes part in the
    hash, excluding only `CONTROL_FIELDS`. The remaining mapping is
    serialized with sorted keys and no whitespace, so two payloads with the
    same content always produce the same string, regardless of key order.

    When `business_key_field` is set, the value is resolved by dot-path and
    normalized by `clean_business_key()`.

    Args:
        payload: Parsed JSON payload.
        business_key_field: Configured business key field name, or `""`.
        null_string_values: Strings that must be treated as null values when
            a business key field is configured.

    Returns:
        The deterministic hash source string.

    Raises:
        BusinessKeyError: If the payload carries no business content, or the
            configured business key is missing, not a scalar, null, or empty
            after cleaning.
    """
    null_values = list(null_string_values) if null_string_values is not None else []

    if not business_key_field:
        content = {
            key: value for key, value in payload.items() if key not in CONTROL_FIELDS
        }
        if not content:
            raise BusinessKeyError(
                "payload carries no business content outside the control fields"
            )
        return json.dumps(
            content, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )

    raw_value = _resolve_dot_path(payload, business_key_field)
    if raw_value is None or isinstance(raw_value, dict | list | bool):
        raise BusinessKeyError(
            f"business key field {business_key_field!r} is missing or not a scalar value"
        )

    text = raw_value if isinstance(raw_value, str) else str(raw_value)
    if text.strip() in null_values:
        raise BusinessKeyError(
            f"business key field {business_key_field!r} holds a null value"
        )

    cleaned = clean_business_key(text, business_key_field)
    if not cleaned or cleaned in null_values:
        raise BusinessKeyError(
            f"business key field {business_key_field!r} is empty after cleaning"
        )
    return cleaned


def compute_uuid5(source: str, namespace: uuid.UUID) -> uuid.UUID:
    """Compute the deterministic UUIDv5 of `source` within `namespace`.

    Args:
        source: String returned by `resolve_business_key_source()`.
        namespace: Fixed namespace read from `config.uuid_namespace`.

    Returns:
        The UUIDv5 identifier used as `clientes_docs.id`.
    """
    return uuid.uuid5(namespace, source)


class IngestionPipeline:
    """Single-cycle orchestrator over `StorageManager` and `Database`.

    The trash folder and maximum file size come from `AppConfig`, with
    optional constructor overrides retained for tests and special deployments.
    """

    def __init__(
        self,
        config: AppConfig,
        storage: StorageManager,
        db: Database,
        trash_path: str | None = None,
        max_file_size_bytes: int | None = None,
    ) -> None:
        """Prepare the pipeline for repeated `run_once()` cycles.

        Args:
            config: Validated application configuration.
            storage: Facade over the configured repositories.
            db: PostgreSQL access layer.
            trash_path: Optional local folder receiving rejected files. The
                configured `AppConfig.trash_path` is used when omitted.
            max_file_size_bytes: Optional size override. The configured
                `AppConfig.max_file_size_bytes` is used when omitted.

        Raises:
            ValueError: If `config.uuid_namespace` is not a valid UUID.
        """
        self._config = config
        self._storage = storage
        self._db = db
        self._trash_path = trash_path or getattr(
            config, "trash_path", "/mnt/share01/trash"
        )
        self._max_file_size_bytes = max_file_size_bytes or getattr(
            config, "max_file_size_bytes", DEFAULT_MAX_FILE_SIZE_BYTES
        )
        if self._max_file_size_bytes <= 0:
            raise ValueError("max_file_size_bytes must be greater than zero")
        self._namespace = uuid.UUID(config.uuid_namespace)
        self._input_repositories = [
            repository.name
            for repository in config.repositories
            if repository.role == "input"
        ]
        self._media_repositories = [
            repository.name
            for repository in config.repositories
            if repository.role == "storage_media"
        ]

    def run_once(self) -> None:
        """Run one full scan/processing cycle over every input repository.

        Failures affecting a single file are logged and skipped, so the rest
        of the batch is still processed. Infrastructure failures while
        listing a repository are propagated to the caller, which owns the
        consecutive error count.

        Raises:
            StorageError: If a repository cannot be listed.
            OSError: If the underlying filesystem cannot be read.
        """
        for repository_name in self._input_repositories:
            filenames = self._storage.list_files(repository_name)
            self._process_repository(repository_name, filenames)

    def run_trash_maintenance(self) -> None:
        """Compress loose trash files and purge archives past their retention."""
        self._storage.compress_trash(self._trash_path)
        self._storage.purge_old_trash_archives(
            self._trash_path, self._config.prazos.trash_cleanup_days
        )

    def _process_repository(self, repository_name: str, filenames: list[str]) -> None:
        """Process one batch of files listed in a single input repository."""
        descriptors = [
            name for name in filenames if name.casefold().endswith(JSON_EXTENSION)
        ]
        media_files = [
            name for name in filenames if not name.casefold().endswith(JSON_EXTENSION)
        ]
        referenced_media: set[str] = set()

        for descriptor in descriptors:
            try:
                self._process_descriptor(
                    repository_name, descriptor, media_files, referenced_media
                )
            except Exception:
                logger.exception(
                    "Unexpected error while processing descriptor %r from %r",
                    descriptor,
                    repository_name,
                )

        self._handle_orphaned_media(repository_name, media_files, referenced_media)

    def _process_descriptor(
        self,
        repository_name: str,
        filename: str,
        media_files: list[str],
        referenced_media: set[str],
    ) -> None:
        """Validate, hash, and submit one descriptor file.

        Args:
            repository_name: Input repository holding the descriptor.
            filename: Descriptor file name, as listed by the repository.
            media_files: Media file names currently present in the same
                repository, used to resolve the media reference.
            referenced_media: Set collecting every media file claimed by a
                descriptor in this batch, so it is never treated as orphaned
                in the same cycle.
        """
        try:
            file_size = self._storage.file_size_bytes(repository_name, filename)
            if file_size > self._max_file_size_bytes:
                raise InvalidPayloadError(
                    f"file exceeds the {self._max_file_size_bytes} byte limit"
                )
            content = self._storage.read_file(repository_name, filename)
        except InvalidPayloadError as exc:
            logger.error(
                "Rejecting descriptor %r from %r: %s", filename, repository_name, exc
            )
            self._move_to_trash(repository_name, filename)
            return
        except InvalidFilenameError:
            logger.error(
                "Descriptor name %r in %r failed validation; moving it to trash",
                filename,
                repository_name,
            )
            self._move_to_trash(repository_name, filename)
            return
        except (StorageError, OSError):
            logger.exception(
                "Could not read descriptor %r from %r; leaving it for the next cycle",
                filename,
                repository_name,
            )
            return

        try:
            payload = self._parse_descriptor(filename, content)
            self._validate_operation(payload)
            payload["id"] = str(self._build_identifier(payload))
            media_name = self._resolve_media_name(
                repository_name, filename, payload, media_files
            )
        except InvalidPayloadError as exc:
            logger.error(
                "Rejecting descriptor %r from %r: %s", filename, repository_name, exc
            )
            self._move_to_trash(repository_name, filename)
            return

        if media_name is not None:
            referenced_media.add(media_name)

        result = self._db.call_processar_operacao_json(filename, payload)

        if result.status != "SUCESSO":
            logger.error(
                "Database rejected descriptor %r from %r: %s",
                filename,
                repository_name,
                result.message,
            )
            self._move_to_trash(repository_name, filename)
            if media_name is not None:
                self._move_to_trash(repository_name, media_name)
            return

        if media_name is not None and not self._dispatch_media(
            repository_name, media_name
        ):
            logger.error(
                "Descriptor %r was stored, but media %r could not be dispatched; "
                "keeping both files for the next cycle",
                filename,
                media_name,
            )
            return

        self._delete_source_file(repository_name, filename)

    def _parse_descriptor(self, filename: str, content: bytes) -> dict[str, Any]:
        """Decode and parse the raw bytes of a descriptor file.

        Raises:
            InvalidPayloadError: If the file is too large, is not valid UTF-8
                JSON, or does not hold a JSON object at its root.
        """
        if len(content) > self._max_file_size_bytes:
            raise InvalidPayloadError(
                f"file exceeds the {self._max_file_size_bytes} byte limit"
            )
        try:
            payload = json.loads(content.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise InvalidPayloadError(f"not valid UTF-8 JSON ({exc})") from exc
        if not isinstance(payload, dict):
            raise InvalidPayloadError("root JSON value is not an object")
        logger.debug("Parsed descriptor %r: %r", filename, payload)
        return payload

    @staticmethod
    def _validate_operation(payload: dict[str, Any]) -> None:
        """Confirm the payload declares one of the four supported operations.

        Raises:
            InvalidPayloadError: If `"operacao"` is missing or unknown, or a
                `REMOVER_PROPRIEDADE` payload has no `"propriedade"` field.
        """
        operation = payload.get("operacao")
        if operation not in VALID_OPERATIONS:
            raise InvalidPayloadError(f"unknown or missing 'operacao': {operation!r}")
        if operation == "REMOVER_PROPRIEDADE":
            prop = payload.get("propriedade")
            if not isinstance(prop, str) or not prop.strip():
                raise InvalidPayloadError(
                    "'REMOVER_PROPRIEDADE' requires a non-empty 'propriedade' field"
                )

    def _build_identifier(self, payload: dict[str, Any]) -> uuid.UUID:
        """Compute the UUIDv5 identifier of `payload`.

        Raises:
            BusinessKeyError: If the configured business key is unusable.
        """
        source = resolve_business_key_source(
            payload,
            self._config.business_key_field,
            self._config.null_string_values,
        )
        return compute_uuid5(source, self._namespace)

    def _resolve_media_name(
        self,
        repository_name: str,
        filename: str,
        payload: dict[str, Any],
        media_files: list[str],
    ) -> str | None:
        """Return the media file claimed by `payload`, if it is present in the repository.

        The referenced name comes from untrusted JSON: it is only accepted
        when it matches, exactly, a file already listed in the repository.
        Sanitization itself still happens inside `StorageManager` on every
        read/write/delete.
        """
        reference_path = self._config.media_reference_json_path
        if not reference_path:
            return None
        raw_value = _resolve_dot_path(payload, reference_path)
        if raw_value is None:
            return None
        if not isinstance(raw_value, str) or not raw_value.strip():
            logger.warning(
                "Descriptor %r has a non-textual media reference at %r; ignoring it",
                filename,
                reference_path,
            )
            return None
        try:
            self._storage.validate_filename(repository_name, raw_value)
        except AttributeError:
            raise InvalidPayloadError(
                "storage manager does not support filename validation"
            ) from None
        except InvalidFilenameError as exc:
            raise InvalidPayloadError(f"invalid media filename {raw_value!r}") from exc
        if raw_value not in media_files:
            logger.warning(
                "Descriptor %r references media %r, which is not present in the repository",
                filename,
                raw_value,
            )
            return None
        return raw_value

    def _dispatch_media(self, repository_name: str, media_name: str) -> bool:
        """Copy a media file to every storage repository and drop the source copy.

        Returns:
            `True` when the media has been fully handled (dispatched, or
            rejected and trashed), `False` when it should be retried in the
            next cycle.
        """
        if not self._media_repositories:
            logger.error(
                "No 'storage_media' repository is configured; cannot dispatch %r",
                media_name,
            )
            return False
        try:
            media_size = self._storage.file_size_bytes(repository_name, media_name)
            if media_size > self._max_file_size_bytes:
                logger.error(
                    "Media %r exceeds the %d byte limit; moving it to trash",
                    media_name,
                    self._max_file_size_bytes,
                )
                self._move_to_trash(repository_name, media_name)
                return True
            content = self._storage.read_file(repository_name, media_name)
        except InvalidFilenameError:
            logger.error(
                "Media name %r referenced from %r failed validation; moving it to trash",
                media_name,
                repository_name,
            )
            self._move_to_trash(repository_name, media_name)
            return True
        except (StorageError, OSError):
            logger.exception(
                "Could not read media %r from %r", media_name, repository_name
            )
            return False

        try:
            for target_repository in self._media_repositories:
                self._storage.write_file(target_repository, media_name, content)
            self._storage.delete_file(repository_name, media_name)
        except (StorageError, OSError):
            logger.exception(
                "Could not dispatch media %r from %r to the storage repositories",
                media_name,
                repository_name,
            )
            return False
        logger.info("Media %r dispatched to %s", media_name, self._media_repositories)
        return True

    def _handle_orphaned_media(
        self,
        repository_name: str,
        media_files: list[str],
        referenced_media: set[str],
    ) -> None:
        """Trash media files left unclaimed for longer than `orphaned_media_hours`."""
        max_age = self._config.prazos.orphaned_media_hours
        for media_name in media_files:
            if media_name in referenced_media:
                continue
            try:
                age_hours = self._storage.file_age_hours(repository_name, media_name)
            except (StorageError, OSError):
                logger.exception(
                    "Could not read the age of media %r in %r",
                    media_name,
                    repository_name,
                )
                continue
            if age_hours > max_age:
                logger.info(
                    "Media %r has been orphaned in %r for %.1f h; moving it to trash",
                    media_name,
                    repository_name,
                    age_hours,
                )
                self._move_to_trash(repository_name, media_name)

    def _move_to_trash(self, repository_name: str, filename: str) -> None:
        """Move `filename` to the trash folder, logging (never raising) on failure."""
        try:
            self._storage.move_to_trash(repository_name, filename, self._trash_path)
        except (StorageError, OSError):
            logger.exception(
                "Could not move %r from %r to trash", filename, repository_name
            )

    def _delete_source_file(self, repository_name: str, filename: str) -> None:
        """Delete a successfully processed file, logging (never raising) on failure."""
        try:
            self._storage.delete_file(repository_name, filename)
        except (StorageError, OSError):
            logger.exception(
                "Could not delete processed file %r from %r", filename, repository_name
            )
