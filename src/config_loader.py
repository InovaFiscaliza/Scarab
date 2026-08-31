"""Configuration loader for the Scarab PostgreSQL/Podman rewrite.

Loads `default_config.json` from a configuration directory and, if a
`config.json` file is also present there, overrides the default values with
it using a shallow (one level deep, per top-level section) merge. The merged
mapping is validated into a tree of immutable `pydantic` models rooted at
`AppConfig`.
"""

import functools
import json
import os
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationError

DEFAULT_CONFIG_FILENAME: str = "default_config.json"
"""Name of the file that ships with the repository and holds default values."""
OVERRIDE_CONFIG_FILENAME: str = "config.json"
"""Name of the optional, gitignored file that overrides default values."""

RepositoryType = Literal["local", "sharepoint"]
RepositoryRole = Literal["input", "storage_media"]


class ConfigError(Exception):
    """Raised when the configuration cannot be read, parsed, or validated."""


class SecretNotFoundError(ConfigError):
    """Raised when a secret's environment variable is not set."""


class _Frozen(BaseModel):
    """Base class for immutable (`frozen=True`) configuration models."""

    model_config = ConfigDict(frozen=True)


class RepositoryConfig(_Frozen):
    """A single input or storage-media repository."""

    name: str
    """Unique repository name, referenced by `storage_manager.py`."""
    type: RepositoryType
    """Backend used to access the repository: `"local"` or `"sharepoint"`."""
    path: str
    """Filesystem path (`type: "local"`) or SharePoint-relative path (`type: "sharepoint"`)."""
    role: RepositoryRole
    """`"input"` for monitored inbound folders, `"storage_media"` for final media storage."""


class DeadlinesConfig(_Frozen):
    """Time-based housekeeping thresholds (`"prazos"` in the JSON config)."""

    orphaned_media_hours: int
    """Hours to wait for a matching JSON descriptor before treating media as orphaned."""
    trash_cleanup_days: int
    """Maximum age, in days, of compressed archives kept in the trash folder."""


class DatabaseConfig(_Frozen):
    """PostgreSQL connection settings."""

    host: str
    """Database server hostname."""
    port: int
    """Database server port."""
    dbname: str
    """Database name."""
    user: str
    """Database role used by the application."""
    password_env: str
    """Name of the environment variable holding the database password (never the password itself)."""
    sslmode: str
    """`psycopg` `sslmode` connection parameter."""
    min_pool_size: int
    """Minimum number of pooled connections."""
    max_pool_size: int
    """Maximum number of pooled connections."""

    @property
    def password(self) -> str:
        """Read the database password from the environment on demand.

        Returns:
            The value stored in the `password_env` environment variable.

        Raises:
            SecretNotFoundError: If the environment variable is not set.
        """
        return _read_secret_env(self.password_env)


class SharePointConfig(_Frozen):
    """SharePoint Client Credentials settings."""

    tenant_id: str
    """Azure AD tenant identifier."""
    client_id: str
    """Azure AD application (client) identifier."""
    client_secret_env: str
    """Name of the environment variable holding the client secret (never the secret itself)."""
    site_url: str
    """Base URL of the SharePoint site."""

    @property
    def client_secret(self) -> str:
        """Read the SharePoint client secret from the environment on demand.

        Returns:
            The value stored in the `client_secret_env` environment variable.

        Raises:
            SecretNotFoundError: If the environment variable is not set.
        """
        return _read_secret_env(self.client_secret_env)


class LogConfig(_Frozen):
    """Logging configuration, same philosophy as the legacy Scarab service."""

    level: str
    """Logging level name (e.g. `"DEBUG"`, `"INFO"`)."""
    screen_output: bool
    """Whether to emit log records to the terminal."""
    file_output: bool
    """Whether to emit log records to a file."""
    file_path: list[str]
    """Log file path segments, joined by the logger setup."""
    format: list[str]
    """Log record format fields, joined together with `separator`."""
    separator: str
    """Separator used to join the `format` fields."""


class AppConfig(_Frozen):
    """Top-level, immutable application configuration."""

    name: str
    """Instance name, used in logs."""
    check_period_seconds: int
    """Interval, in seconds, between main loop scans."""
    maximum_errors_before_exit: int
    """Consecutive errors allowed before the service exits."""
    uuid_namespace: str
    """Fixed UUID namespace (as text) used by `pipeline.py` to compute UUIDv5 identifiers."""
    business_key_field: str
    """Business key field name; `""` (default) hashes the whole payload instead of one field."""
    media_reference_json_path: str
    """Dot-notation path, within the descriptor JSON, to the media file name."""
    null_string_values: list[str]
    """Strings treated as null when cleaning the business key."""
    repositories: list[RepositoryConfig]
    """Input and storage-media repositories."""
    prazos: DeadlinesConfig
    """Time-based housekeeping thresholds."""
    database: DatabaseConfig
    """PostgreSQL connection settings."""
    sharepoint: SharePointConfig | None
    """SharePoint Client Credentials settings, or `None` if unused."""
    log: LogConfig
    """Logging configuration."""
    trash_path: str = "/mnt/trash"
    """Local directory receiving rejected files and orphaned media."""
    max_file_size_bytes: int = 50 * 1024 * 1024
    """Maximum file size accepted by the pipeline before reading into memory."""


def _read_secret_env(env_var: str) -> str:
    """Read a secret value from an environment variable.

    Args:
        env_var: Name of the environment variable to read.

    Returns:
        The value stored in `env_var`.

    Raises:
        SecretNotFoundError: If `env_var` is not set in the environment.
    """
    value = os.environ.get(env_var)
    if value is None:
        raise SecretNotFoundError(
            f"Environment variable '{env_var}' is not set; cannot read secret."
        )
    return value


def _read_json_file(path: Path) -> dict[str, Any]:
    """Read and parse a JSON file encoded as UTF-8.

    Args:
        path: Path to the JSON file.

    Returns:
        The parsed JSON content.

    Raises:
        ConfigError: If the file does not exist or is not valid JSON.
    """
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError as exc:
        raise ConfigError(f"Configuration file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(
            f"Configuration file is not valid JSON: {path} ({exc})"
        ) from exc


def _shallow_merge(default: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Merge an override configuration into the default, one level deep per section.

    Scalar and list values in `override` replace the corresponding default
    value. Dict values in `override` are merged with the default dict found
    at the same key (override wins per inner key); inner keys missing from
    the override section inherit their default value. No merge happens
    beyond this single level of nesting.

    Args:
        default: Parsed contents of `default_config.json`.
        override: Parsed contents of `config.json`.

    Returns:
        The merged configuration mapping.
    """
    merged = dict(default)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = {**merged[key], **value}
        else:
            merged[key] = value
    return merged


def load_config(config_dir: str) -> AppConfig:
    """Load, merge, and validate the application configuration.

    Reads `default_config.json` from `config_dir`, then, if a `config.json`
    file also exists in that same directory, overrides the default values
    with a shallow (one level deep, per section) merge.

    Args:
        config_dir: Directory containing `default_config.json` and,
            optionally, `config.json`.

    Returns:
        The fully validated, immutable application configuration.

    Raises:
        ConfigError: If a configuration file is missing/malformed, or a
            field fails validation (e.g. an invalid `repositories[].type`
            or `repositories[].role`).
    """
    directory = Path(config_dir)
    default_path = directory / DEFAULT_CONFIG_FILENAME
    override_path = directory / OVERRIDE_CONFIG_FILENAME

    raw_config = _read_json_file(default_path)
    if override_path.exists():
        raw_config = _shallow_merge(raw_config, _read_json_file(override_path))

    try:
        return AppConfig.model_validate(raw_config)
    except ValidationError as exc:
        raise ConfigError(f"Invalid configuration in '{directory}': {exc}") from exc


def _default_config_dir() -> Path:
    """Return the repository's default configuration directory.

    Returns:
        The `config/` directory, resolved relative to this file's own
        location (`src/config_loader.py` -> repository root -> `config/`).
    """
    return Path(__file__).resolve().parent.parent / "config"


@functools.lru_cache(maxsize=1)
def get_config(config_dir: str | None = None) -> AppConfig:
    """Return the cached, singleton application configuration.

    The first call loads and validates the configuration; subsequent calls
    return the same cached instance without touching the filesystem again.
    Use this instead of `load_config()` from application code.

    Args:
        config_dir: Directory containing the configuration files. Defaults
            to the repository's `config/` directory when omitted.

    Returns:
        The cached application configuration.

    Raises:
        ConfigError: If a configuration file is missing/malformed, or a
            field fails validation.
    """
    directory = config_dir if config_dir is not None else str(_default_config_dir())
    return load_config(directory)
