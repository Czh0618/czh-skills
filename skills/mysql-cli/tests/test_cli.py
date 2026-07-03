"""CLI-level checks for agent-facing JSON behavior."""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from mydb_cli.cli import cli


@pytest.fixture(autouse=True)
def _isolated_config(monkeypatch, tmp_path):
    monkeypatch.setenv("MYDB_CONFIG_DIR", str(tmp_path))


def _payload(result):
    return json.loads(result.output)


def test_conn_add_and_list_emit_json_envelopes():
    runner = CliRunner()

    added = runner.invoke(
        cli,
        [
            "conn",
            "add",
            "prod",
            "--host",
            "db.example.test",
            "--user",
            "readonly",
            "--db",
            "shop",
            "--readonly-locked",
            "--json",
        ],
    )
    assert added.exit_code == 0
    assert _payload(added)["data"] == {
        "added": "prod",
        "password_env": "MYDB_PWD_PROD",
        "readonly_locked": True,
    }

    listed = runner.invoke(cli, ["conn", "list", "--json"])
    assert listed.exit_code == 0
    payload = _payload(listed)
    assert payload["ok"] is True
    assert payload["data"]["current"] == "prod"
    assert payload["data"]["profiles"]["prod"]["readonly_locked"] is True


def test_root_profile_option_is_accepted_for_agent_commands():
    runner = CliRunner()
    result = runner.invoke(cli, ["--profile", "missing", "databases", "--json"])

    assert result.exit_code == 1
    payload = _payload(result)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "profile_not_found"


def test_query_blocks_writes_before_password_or_connection():
    runner = CliRunner()
    runner.invoke(
        cli,
        ["conn", "add", "prod", "--host", "h", "--user", "u", "--readonly-locked", "--json"],
    )

    result = runner.invoke(
        cli,
        ["query", "UPDATE users SET enabled = 0", "--profile", "prod", "--json"],
    )

    assert result.exit_code == 1
    payload = _payload(result)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "write_not_allowed"
