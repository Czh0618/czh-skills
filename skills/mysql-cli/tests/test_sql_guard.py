"""Tests for the SQL safety classifier — the security core (T2)."""

from __future__ import annotations

import pytest

from mydb_cli import sql_guard as g
from mydb_cli.exceptions import NeedsConfirm, WriteNotAllowed


# ─── classify ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("sql", "expected"),
    [
        ("SELECT 1", g.READONLY),
        ("  select * from t", g.READONLY),
        ("SHOW TABLES", g.READONLY),
        ("DESCRIBE orders", g.READONLY),
        ("EXPLAIN SELECT 1", g.READONLY),
        ("WITH c AS (SELECT 1) SELECT * FROM c", g.READONLY),
        ("UPDATE t SET a=1 WHERE id=1", g.WRITE),
        ("INSERT INTO t VALUES (1)", g.WRITE),
        ("UPDATE t SET a=1", g.DANGER),
        ("DELETE FROM t", g.DANGER),
        ("DROP TABLE t", g.DANGER),
        ("TRUNCATE t", g.DANGER),
        ("ALTER TABLE t ADD c INT", g.DANGER),
        ("", g.WRITE),
        ("-- just a comment\nSELECT 1", g.READONLY),
        ("/* c */ DELETE FROM t", g.DANGER),
    ],
)
def test_classify(sql, expected):
    assert g.classify(sql) == expected


# ─── guard ─────────────────────────────────────────────────────────────────


def test_guard_readonly_always_passes():
    assert g.guard("SELECT 1", allow_write=False, yes=False, readonly_locked=True) == g.READONLY


def test_guard_write_blocked_without_allow_write():
    with pytest.raises(WriteNotAllowed):
        g.guard("UPDATE t SET a=1 WHERE id=1", allow_write=False, yes=False, readonly_locked=False)


def test_guard_write_passes_with_allow_write():
    assert g.guard("UPDATE t SET a=1 WHERE id=1", allow_write=True, yes=False, readonly_locked=False) == g.WRITE


def test_guard_danger_needs_confirm():
    with pytest.raises(NeedsConfirm):
        g.guard("DROP TABLE t", allow_write=True, yes=False, readonly_locked=False)


def test_guard_danger_passes_with_yes():
    assert g.guard("DROP TABLE t", allow_write=True, yes=True, readonly_locked=False) == g.DANGER


def test_guard_readonly_locked_rejects_any_write():
    with pytest.raises(WriteNotAllowed):
        g.guard("UPDATE t SET a=1 WHERE id=1", allow_write=True, yes=True, readonly_locked=True)


# ─── inject_limit ──────────────────────────────────────────────────────────


def test_inject_limit_appends_to_bare_select():
    assert g.inject_limit("SELECT * FROM t", 100) == "SELECT * FROM t LIMIT 100"


def test_inject_limit_strips_trailing_semicolon():
    assert g.inject_limit("SELECT * FROM t;", 50) == "SELECT * FROM t LIMIT 50"


def test_inject_limit_idempotent_when_limit_present():
    sql = "SELECT * FROM t LIMIT 5"
    assert g.inject_limit(sql, 100) == sql


def test_inject_limit_skips_show():
    # SHOW ... LIMIT n is a syntax error in MySQL — must not be touched.
    assert g.inject_limit("SHOW TABLES", 100) == "SHOW TABLES"


def test_inject_limit_skips_non_readonly():
    assert g.inject_limit("DELETE FROM t", 100) == "DELETE FROM t"


def test_inject_limit_touches_with():
    assert g.inject_limit("WITH c AS (SELECT 1) SELECT * FROM c", 10).endswith("LIMIT 10")
