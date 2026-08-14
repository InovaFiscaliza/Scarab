"""Tests for `src.database`."""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Self

import psycopg
import pytest
from psycopg.types.json import Jsonb

from src.config_loader import DatabaseConfig, SecretNotFoundError
from src.database import Database, ProcessResult


class _FakeCursor:
    """Minimal stand-in for a `psycopg.Cursor` used inside a `with` block."""

    def __init__(
        self,
        fetchone_result: tuple | None = None,
        execute_exc: Exception | None = None,
    ) -> None:
        self.fetchone_result = fetchone_result
        self.execute_exc = execute_exc
        self.executed: list[tuple[str, tuple | None]] = []

    def execute(self, query: str, params: tuple | None = None) -> None:
        """Record the call, or raise, like a broken connection/query would."""
        if self.execute_exc is not None:
            raise self.execute_exc
        self.executed.append((query, params))

    def fetchone(self) -> tuple | None:
        """Return the canned row configured for this fake."""
        return self.fetchone_result

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info: object) -> bool:
        return False


class _FakeConnection:
    """Minimal stand-in for a pooled `psycopg.Connection`."""

    def __init__(self, cursor: _FakeCursor) -> None:
        self._cursor = cursor

    def cursor(self) -> _FakeCursor:
        """Return the fake cursor, mirroring `psycopg.Connection.cursor()`."""
        return self._cursor

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info: object) -> bool:
        return False


class _FakePool:
    """Minimal stand-in for `psycopg_pool.ConnectionPool`."""

    def __init__(
        self, connection: _FakeConnection, open_exc: Exception | None = None
    ) -> None:
        self._connection = connection
        self.open_exc = open_exc
        self.opened = False
        self.closed = False

    def open(self, wait: bool = False, timeout: float = 30.0) -> None:
        """Mimic `ConnectionPool.open()`, optionally raising a canned error."""
        if self.open_exc is not None:
            raise self.open_exc
        self.opened = True

    @contextmanager
    def connection(self, timeout: float | None = None) -> Iterator[_FakeConnection]:
        """Mimic `ConnectionPool.connection()`'s context-manager behaviour."""
        yield self._connection

    def close(self, timeout: float = 5.0) -> None:
        """Mimic `ConnectionPool.close()`."""
        self.closed = True


def _make_config(**overrides: object) -> DatabaseConfig:
    """Build a valid `DatabaseConfig` for tests, with `overrides` applied."""
    base: dict[str, object] = {
        "host": "localhost",
        "port": 5432,
        "dbname": "scarab_test",
        "user": "scarab_app",
        "password_env": "SCARAB_TEST_DB_PASSWORD",
        "sslmode": "prefer",
        "min_pool_size": 1,
        "max_pool_size": 5,
    }
    base.update(overrides)
    return DatabaseConfig(**base)  # type: ignore[arg-type]


@pytest.fixture(autouse=True)
def _password_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure the test database password is resolvable unless a test removes it."""
    monkeypatch.setenv("SCARAB_TEST_DB_PASSWORD", "s3cr3t")


def _wire_fake_pool(
    db: Database,
    *,
    fetchone_result: tuple | None = None,
    execute_exc: Exception | None = None,
    open_exc: Exception | None = None,
) -> tuple[_FakePool, _FakeCursor]:
    """Replace `db`'s real connection pool with an in-memory fake and return both."""
    cursor = _FakeCursor(fetchone_result=fetchone_result, execute_exc=execute_exc)
    pool = _FakePool(_FakeConnection(cursor), open_exc=open_exc)
    db._pool = pool  # type: ignore[assignment]
    return pool, cursor


def test_init_does_not_open_a_real_connection() -> None:
    """Constructing `Database` must never attempt a real network connection."""
    # 203.0.113.0/24 (TEST-NET-3, RFC 5737) is reserved for documentation and never routable.
    config = _make_config(host="203.0.113.1", port=54329)

    db = Database(config)

    assert db._pool.closed is True
    db.close()


def test_init_raises_when_password_env_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """`Database.__init__` propagates `SecretNotFoundError` instead of connecting blindly."""
    monkeypatch.delenv("SCARAB_TEST_DB_PASSWORD", raising=False)
    config = _make_config()

    with pytest.raises(SecretNotFoundError):
        Database(config)


def test_call_processar_operacao_json_sends_parameterized_query() -> None:
    """The stored function is called with bound parameters, payload wrapped in `Jsonb`."""
    db = Database(_make_config())
    client_id = uuid.uuid4()
    pool, cursor = _wire_fake_pool(db, fetchone_result=("SUCESSO", None, client_id))
    payload = {"operacao": "INSERT", "id": str(client_id), "nome": "Ana"}

    result = db.call_processar_operacao_json("arquivo.json", payload)

    assert result == ProcessResult(status="SUCESSO", message=None, client_id=client_id)
    assert pool.opened is True
    [(query, params)] = cursor.executed
    assert query == "SELECT status, mensagem, id FROM processar_operacao_json(%s, %s)"
    assert params[0] == "arquivo.json"
    assert isinstance(params[1], Jsonb)
    assert params[1].obj == payload


def test_call_processar_operacao_json_does_not_interpolate_payload_into_sql() -> None:
    """Even a payload/filename crafted to look like SQL never reaches the query text."""
    db = Database(_make_config())
    _, cursor = _wire_fake_pool(db, fetchone_result=("SUCESSO", None, uuid.uuid4()))
    malicious_payload = {"operacao": "INSERT", "id": "1); DROP TABLE clientes_docs; --"}

    db.call_processar_operacao_json(
        "'; DROP TABLE clientes_docs; --.json", malicious_payload
    )

    [(query, _params)] = cursor.executed
    assert "DROP TABLE" not in query
    assert query == "SELECT status, mensagem, id FROM processar_operacao_json(%s, %s)"


def test_call_processar_operacao_json_returns_erro_when_no_row_returned() -> None:
    """A missing row is treated as an application-level error, not a crash."""
    db = Database(_make_config())
    _wire_fake_pool(db, fetchone_result=None)

    result = db.call_processar_operacao_json(
        "arquivo.json", {"operacao": "INSERT", "id": "x"}
    )

    assert result.status == "ERRO"
    assert result.client_id is None


@pytest.mark.parametrize("failure_point", ["open", "execute"])
def test_call_processar_operacao_json_returns_erro_on_database_error(
    failure_point: str,
) -> None:
    """Connection and query failures are converted to a `ProcessResult`, never raised."""
    db = Database(_make_config())
    error = psycopg.OperationalError("connection refused")
    if failure_point == "open":
        _wire_fake_pool(db, open_exc=error)
    else:
        _wire_fake_pool(db, execute_exc=error)

    result = db.call_processar_operacao_json(
        "arquivo.json", {"operacao": "INSERT", "id": "x"}
    )

    assert result.status == "ERRO"
    assert result.client_id is None
    assert result.message is not None


def test_health_check_returns_true_on_successful_query() -> None:
    """`health_check` returns `True` when the trivial query succeeds."""
    db = Database(_make_config())
    _wire_fake_pool(db, fetchone_result=(1,))

    assert db.health_check() is True


@pytest.mark.parametrize("failure_point", ["open", "execute"])
def test_health_check_returns_false_on_database_error(failure_point: str) -> None:
    """`health_check` swallows connection/database errors and returns `False`, never raises."""
    db = Database(_make_config())
    error = psycopg.OperationalError("connection refused")
    if failure_point == "open":
        _wire_fake_pool(db, open_exc=error)
    else:
        _wire_fake_pool(db, execute_exc=error)

    assert db.health_check() is False


def test_close_closes_the_connection_pool() -> None:
    """`close()` delegates to the pool's own `close()`."""
    db = Database(_make_config())
    pool, _cursor = _wire_fake_pool(db)

    db.close()

    assert pool.closed is True
