"""Tests for the agent envelope output layer and error-code mapping (T1)."""

from __future__ import annotations

import sys

from mydb_cli import exceptions as ex
from mydb_cli import formatter_utils as fu
from mydb_cli.error_codes import error_code_for_exception


def _force_non_tty(monkeypatch):
    monkeypatch.delenv("OUTPUT", raising=False)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: False)


# ─── envelope shape ────────────────────────────────────────────────────────


def test_success_payload_shape():
    p = fu.success_payload({"columns": ["id"], "rows": [[1]], "row_count": 1, "truncated": False})
    assert p == {
        "ok": True,
        "schema_version": "1",
        "data": {"columns": ["id"], "rows": [[1]], "row_count": 1, "truncated": False},
    }


def test_error_payload_shape():
    p = fu.error_payload("query_error", "bad sql")
    assert p["ok"] is False
    assert p["schema_version"] == "1"
    assert p["error"] == {"code": "query_error", "message": "bad sql"}


# ─── non-TTY defaults to JSON ──────────────────────────────────────────────


def test_non_tty_defaults_to_json(monkeypatch, capsys):
    _force_non_tty(monkeypatch)
    printed = fu.maybe_print_structured({"row_count": 3}, as_json=False, as_yaml=False)
    assert printed is True
    out = capsys.readouterr().out
    assert '"ok": true' in out
    assert '"schema_version":' in out
    assert '"row_count": 3' in out


def test_emit_error_non_tty_json(monkeypatch, capsys):
    _force_non_tty(monkeypatch)
    printed = fu.emit_error("write_not_allowed", "writes disabled", as_json=False, as_yaml=False)
    assert printed is True
    out = capsys.readouterr().out
    assert '"ok": false' in out
    assert '"write_not_allowed"' in out


def test_json_flag_overrides(monkeypatch, capsys):
    monkeypatch.delenv("OUTPUT", raising=False)
    printed = fu.maybe_print_structured({"x": 1}, as_json=True, as_yaml=False)
    assert printed is True
    out = capsys.readouterr().out
    assert '"ok"' in out and "true" in out


def test_tty_without_flags_renders_human(monkeypatch):
    monkeypatch.delenv("OUTPUT", raising=False)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    # No flag + TTY → None means "render human/rich output", so not structured.
    assert fu.maybe_print_structured({"x": 1}, as_json=False, as_yaml=False) is False


# ─── error-code mapping ────────────────────────────────────────────────────


def test_error_code_mapping():
    assert error_code_for_exception(ex.WriteNotAllowed("x")) == "write_not_allowed"
    assert error_code_for_exception(ex.PasswordNotSet("MYDB_PWD_PROD")) == "password_not_set"
    assert error_code_for_exception(ex.ProfileNotFound("prod")) == "profile_not_found"
    assert error_code_for_exception(ex.DbConnectionError("x")) == "connection_error"
    assert error_code_for_exception(ex.MyDbError("uncategorized")) == "db_error"
    assert error_code_for_exception(ValueError("boom")) == "unknown_error"
