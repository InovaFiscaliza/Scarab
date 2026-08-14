"""Process entry point for the Scarab ingestion service.

Wires `config_loader`, `storage_manager`, `database`, and `pipeline` together
into the long-running service loop: load configuration, configure logging,
register shutdown signal handlers, then repeatedly call
`IngestionPipeline.run_once()` until a shutdown signal arrives or too many
consecutive errors occur. All file classification, validation, and
persistence logic lives in those other modules; this module only owns the
process lifecycle (signals, logging setup, the scan/sleep loop, and the
consecutive-error count).
"""

import logging
import signal
import sys
import time
from pathlib import Path
from types import FrameType

from src.config_loader import AppConfig, get_config
from src.database import Database
from src.pipeline import IngestionPipeline
from src.storage_manager import StorageError, StorageManager

logger = logging.getLogger(__name__)

keep_running: bool = True
"""Flag polled by the main loop; cleared by a signal handler, or once
`_record_error()` reports `config.maximum_errors_before_exit` was exceeded,
to request a graceful shutdown after the current cycle finishes."""

MAINTENANCE_INTERVAL_SECONDS: float = 3600.0
"""Minimum time between `IngestionPipeline.run_trash_maintenance()` runs.

There is no dedicated config field for this cadence (see
`docs/rewrite/CONTRACTS.md`, section 1.2): trash compression/purge is
comparatively expensive and only meaningful on a much slower cadence than the
ingestion scan, so it is scheduled with its own fixed elapsed-time check
(`_maintenance_due()`) instead of reusing `check_period_seconds` or
`prazos.trash_cleanup_days` (which bounds archive *retention*, not how often
maintenance itself runs).
"""


def _request_shutdown(signum: int, frame: FrameType | None) -> None:
    """Signal handler for SIGINT/SIGTERM/SIGBREAK: request a graceful shutdown.

    Args:
        signum: Number of the received signal.
        frame: Current stack frame; unused, required by the `signal` API.
    """
    global keep_running
    logger.critical(
        "Received %s; finishing the current cycle before shutting down...",
        signal.Signals(signum).name,
    )
    keep_running = False


def _register_signal_handlers() -> None:
    """Register `_request_shutdown` for SIGINT, SIGTERM, and SIGBREAK if present.

    `SIGBREAK` only exists on Windows, so it is looked up with `getattr`
    instead of referenced directly, keeping this function (and importing
    this module) safe on every platform.
    """
    signal.signal(signal.SIGINT, _request_shutdown)
    signal.signal(signal.SIGTERM, _request_shutdown)
    sigbreak = getattr(signal, "SIGBREAK", None)
    if sigbreak is not None:
        signal.signal(sigbreak, _request_shutdown)


def _configure_logging(config: AppConfig) -> None:
    """Configure the `"src"` package logger tree from `config.log`.

    Handlers are attached to the `"src"` logger -- the common ancestor of
    every module logger in this package (`src.database`, `src.pipeline`,
    `src.storage_manager`, `src.main`) -- instead of the root logger, so
    third-party dependencies keep their own default verbosity instead of
    inheriting this configuration.

    Args:
        config: Validated application configuration.
    """
    package_logger = logging.getLogger("src")
    package_logger.handlers.clear()
    package_logger.propagate = False
    package_logger.setLevel(getattr(logging, config.log.level.upper(), logging.INFO))

    formatter = logging.Formatter(config.log.separator.join(config.log.format))

    if config.log.screen_output:
        screen_handler = logging.StreamHandler(sys.stdout)
        screen_handler.setFormatter(formatter)
        package_logger.addHandler(screen_handler)

    if config.log.file_output and config.log.file_path:
        log_file = Path(*config.log.file_path)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        package_logger.addHandler(file_handler)

    if not package_logger.handlers:
        package_logger.addHandler(logging.NullHandler())


def _record_error(consecutive_errors: int, threshold: int) -> tuple[int, bool]:
    """Increment the consecutive-error counter and check it against `threshold`.

    Kept free of globals and logging so it can be unit-tested in isolation.

    Args:
        consecutive_errors: Errors observed so far, back-to-back.
        threshold: `config.maximum_errors_before_exit`.

    Returns:
        A `(new_count, exceeded)` pair; `exceeded` is `True` once `new_count`
        surpasses `threshold`.
    """
    new_count = consecutive_errors + 1
    return new_count, new_count > threshold


def _maintenance_due(last_run: float, now: float, interval_seconds: float) -> bool:
    """Return whether at least `interval_seconds` elapsed since `last_run`.

    `now` and `last_run` are both caller-supplied (typically from
    `time.monotonic()`) rather than read internally, so this scheduling
    decision can be unit-tested without mocking the `time` module.

    Args:
        last_run: Timestamp of the last maintenance run.
        now: Current timestamp, in the same clock as `last_run`.
        interval_seconds: Minimum interval between runs.

    Returns:
        `True` if maintenance should run now.
    """
    return (now - last_run) >= interval_seconds


def main(config_dir: str) -> None:
    """Run the Scarab ingestion service until shutdown or too many errors.

    Loads configuration, configures logging, registers shutdown signal
    handlers, then repeatedly calls `IngestionPipeline.run_once()` every
    `config.check_period_seconds`, running `run_trash_maintenance()` on its
    own slower cadence (see `MAINTENANCE_INTERVAL_SECONDS`). The loop stops
    on `SIGINT`/`SIGTERM`/`SIGBREAK`, or once `config.maximum_errors_before_exit`
    consecutive cycles fail.

    Args:
        config_dir: Directory holding `default_config.json` and, optionally,
            `config.json`. Forwarded to `config_loader.get_config()`.
    """
    global keep_running
    keep_running = True

    config = get_config(config_dir)
    _configure_logging(config)
    _register_signal_handlers()

    logger.critical("Scarab (%s) is starting...", config.name)

    storage = StorageManager(config.repositories, config.sharepoint)
    db = Database(config.database)
    try:
        pipeline = IngestionPipeline(config, storage, db)
        consecutive_errors = 0
        last_maintenance_at = time.monotonic()

        def _handle_cycle_failure() -> None:
            """Bump the consecutive-error counter, stopping the loop past the threshold."""
            nonlocal consecutive_errors
            global keep_running
            consecutive_errors, exceeded = _record_error(
                consecutive_errors, config.maximum_errors_before_exit
            )
            if exceeded:
                logger.critical(
                    "Too many consecutive errors (%d); exiting...", consecutive_errors
                )
                keep_running = False

        while keep_running:
            try:
                pipeline.run_once()
                consecutive_errors = 0
            except (StorageError, OSError) as exc:
                logger.critical("Error accessing repositories or files: %s", exc)
                _handle_cycle_failure()
            except Exception:
                logger.exception("Unhandled error in the main loop")
                _handle_cycle_failure()

            if not keep_running:
                break

            now = time.monotonic()
            if _maintenance_due(last_maintenance_at, now, MAINTENANCE_INTERVAL_SECONDS):
                try:
                    pipeline.run_trash_maintenance()
                except Exception:
                    logger.exception("Trash maintenance failed")
                last_maintenance_at = now

            time.sleep(config.check_period_seconds)

        logger.info("Scarab (%s) is shutting down...", config.name)
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python -m src.main <config_dir>")
        sys.exit(1)

    main(sys.argv[1])
