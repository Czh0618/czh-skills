"""Tests for the PyMySQL short-lived client (T4), with pymysql mocked."""

from __future__ import annotations

import pytest
import pymysql
from pymysql import err

from mydb_cli.client import MyDbClient
from mydb_cli.exceptions import DbConnectionError, QueryError

_PROFILE = {"host": "h", "port": 3306, "user": "u", "db": "shop"}


class FakeCursor:
    def __init__(
        self,
        rows=None,
        description=None,
        rowcount=0,
        raise_on_execute=None,
        raise_on_sql=None,
    ):
        self._rows = rows or []
        self.description = description
        self.rowcount = rowcount
        self._raise = raise_on_execute
        self._raise_on_sql = raise_on_sql
        self.executed: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, args=None):
        if self._raise is not None and (
            self._raise_on_sql is None or self._raise_on_sql in sql
        ):
            raise self._raise
        self.executed.append(sql)

    def fetchall(self):
        return self._rows

    def close(self):
        pass


class FakeConn:
    def __init__(self, cursor):
        self._cursor = cursor
        self.committed = False
        self.closed = False

    def cursor(self):
        return self._cursor

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


@pytest.fixture(autouse=True)
def _isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("MYDB_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("MYDB_PWD_PROD", "pw")


def _patch_connect(monkeypatch, conn):
    monkeypatch.setattr(pymysql, "connect", lambda **kw: conn)


# ─── read-only transaction gating ──────────────────────────────────────────


def test_readonly_sets_transaction_read_only(monkeypatch):
    cur = FakeCursor(description=None)
    _patch_connect(monkeypatch, FakeConn(cur))
    with MyDbClient("prod", _PROFILE, readonly=True):
        pass
    assert "SET SESSION TRANSACTION READ ONLY" in cur.executed


def test_write_mode_does_not_set_read_only(monkeypatch):
    cur = FakeCursor(description=None, rowcount=1)
    _patch_connect(monkeypatch, FakeConn(cur))
    with MyDbClient("prod", _PROFILE, readonly=False) as c:
        c.run("UPDATE t SET a=1 WHERE id=1", write=True)
    assert "SET SESSION TRANSACTION READ ONLY" not in cur.executed


# ─── result envelope shape ─────────────────────────────────────────────────


def test_run_returns_compact_positional_rows(monkeypatch):
    cur = FakeCursor(rows=[(1, "a"), (2, "b")], description=(("id",), ("name",)))
    _patch_connect(monkeypatch, FakeConn(cur))
    with MyDbClient("prod", _PROFILE, readonly=True) as c:
        res = c.run("SELECT id, name FROM t", limit=100)
    assert res["columns"] == ["id", "name"]
    assert res["rows"] == [[1, "a"], [2, "b"]]
    assert res["row_count"] == 2
    assert res["truncated"] is False
    assert "affected_rows" not in res


def test_run_truncated_when_hitting_limit(monkeypatch):
    cur = FakeCursor(rows=[(i,) for i in range(100)], description=(("n",),))
    _patch_connect(monkeypatch, FakeConn(cur))
    with MyDbClient("prod", _PROFILE, readonly=True) as c:
        res = c.run("SELECT n FROM t", limit=100)
    assert res["row_count"] == 100
    assert res["truncated"] is True


def test_run_write_commits_and_reports_affected(monkeypatch):
    cur = FakeCursor(rows=[], description=None, rowcount=3)
    conn = FakeConn(cur)
    _patch_connect(monkeypatch, conn)
    with MyDbClient("prod", _PROFILE, readonly=False) as c:
        res = c.run("UPDATE t SET a=1 WHERE id=1", write=True)
    assert conn.committed is True
    assert res["affected_rows"] == 3


def test_connection_closed_on_exit(monkeypatch):
    conn = FakeConn(FakeCursor(description=None))
    _patch_connect(monkeypatch, conn)
    with MyDbClient("prod", _PROFILE, readonly=True):
        pass
    assert conn.closed is True


# ─── exception mapping ─────────────────────────────────────────────────────


def test_connect_operational_error_maps_to_connection_error(monkeypatch):
    def boom(**kw):
        raise err.OperationalError(2003, "Can't connect to MySQL server")

    monkeypatch.setattr(pymysql, "connect", boom)
    with pytest.raises(DbConnectionError) as exc:
        with MyDbClient("prod", _PROFILE, readonly=True):
            pass
    assert exc.value.code == "connection_error"


def test_run_programming_error_maps_to_query_error(monkeypatch):
    cur = FakeCursor(
        raise_on_execute=err.ProgrammingError(1146, "Table doesn't exist"),
        raise_on_sql="SELECT",
    )
    _patch_connect(monkeypatch, FakeConn(cur))
    with MyDbClient("prod", _PROFILE, readonly=True) as c:
        with pytest.raises(QueryError) as exc:
            c.run("SELECT * FROM nope")
    assert exc.value.code == "query_error"
