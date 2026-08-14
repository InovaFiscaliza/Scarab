"""PostgreSQL access layer for the Scarab rewrite.

Wraps a `psycopg_pool.ConnectionPool` and exposes the single stored function
call used by the ingestion pipeline (`processar_operacao_json`), plus a
lightweight connection health check. Every SQL call is parameterized; no
payload or filename content is ever interpolated into a query string.
"""

import logging
import uuid
from dataclasses import dataclass
from typing import Literal, cast

import psycopg
from psycopg.conninfo import make_conninfo
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from src.config_loader import DatabaseConfig

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProcessResult:
    """Outcome of a single `processar_operacao_json` call."""

    status: Literal["SUCESSO", "ERRO"]
    """Exactly as returned by the `processar_operacao_json` stored function."""
    message: str | None
    """Error message from the stored function, or `None` on success."""
    client_id: uuid.UUID | None
    """Primary key of the affected `clientes_docs` row, when known."""


class Database:
    """PostgreSQL access layer backed by a pooled connection.

    The pool is created with `open=False`: no socket is opened at
    construction time, only lazily on the first call to
    `call_processar_operacao_json()` or `health_check()`. This keeps plain
    instantiation safe to use in tests without a live PostgreSQL server.
    """

    def __init__(self, config: DatabaseConfig) -> None:
        """Build the (not-yet-open) connection pool for `config`.

        Args:
            config: PostgreSQL connection settings.

        Raises:
            SecretNotFoundError: If `config.password_env` is not set in the
                environment.
        """
        conninfo = make_conninfo(
            host=config.host,
            port=config.port,
            dbname=config.dbname,
            user=config.user,
            password=config.password,
            sslmode=config.sslmode,
        )
        self._pool: ConnectionPool = ConnectionPool(
            conninfo,
            min_size=config.min_pool_size,
            max_size=config.max_pool_size,
            open=False,
        )

    def call_processar_operacao_json(self, filename: str, payload: dict) -> ProcessResult:
        """Call the `processar_operacao_json` stored function.

        Args:
            filename: Original name of the JSON file being processed. Bound
                as `p_nome_arquivo`; never interpolated into the SQL text.
            payload: Parsed JSON payload. Bound as `p_payload`, wrapped in
                `Jsonb`; never interpolated into the SQL text.

        Returns:
            The status, message, and affected row id reported by the stored
            function. Connection or database errors are caught and reported
            as `ProcessResult(status="ERRO", ...)` instead of being raised,
            so the caller can keep processing other files.
        """
        logger.debug(
            "Calling processar_operacao_json for %r with payload=%r", filename, payload
        )
        try:
            self._pool.open()
            with self._pool.connection() as conn, conn.cursor() as cur:
                cur.execute(
                    "SELECT status, mensagem, id FROM processar_operacao_json(%s, %s)",
                    (filename, Jsonb(payload)),
                )
                row = cur.fetchone()
        except psycopg.Error:
            logger.exception(
                "Database error while calling processar_operacao_json for %r", filename
            )
            return ProcessResult(
                status="ERRO", message="database connection error", client_id=None
            )

        if row is None:
            logger.error("processar_operacao_json returned no row for %r", filename)
            return ProcessResult(
                status="ERRO",
                message="no result returned by processar_operacao_json",
                client_id=None,
            )

        status, message, client_id = row
        logger.info(
            "processar_operacao_json for %r: status=%s id=%s", filename, status, client_id
        )
        return ProcessResult(
            # the stored function only ever returns one of these two literals
            status=cast(Literal["SUCESSO", "ERRO"], status),
            message=message,
            client_id=client_id,
        )

    def health_check(self) -> bool:
        """Check whether the database is reachable.

        Returns:
            `True` if a trivial query succeeds, `False` on any connection or
            database error. Never raises.
        """
        try:
            self._pool.open()
            with self._pool.connection() as conn, conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        except psycopg.Error:
            logger.exception("Database health check failed")
            return False
        return True

    def close(self) -> None:
        """Close the connection pool, releasing all pooled connections."""
        self._pool.close()
