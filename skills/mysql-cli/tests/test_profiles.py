"""Tests for connection profiles and env password resolution (T3)."""

from __future__ import annotations

import os

import pytest

from mydb_cli import profiles
from mydb_cli.exceptions import NotConnected, PasswordNotSet, ProfileNotFound


@pytest.fixture(autouse=True)
def _isolated_config(monkeypatch, tmp_path):
    """Point the config dir at a temp path for every test."""
    monkeypatch.setenv("MYDB_CONFIG_DIR", str(tmp_path))
    return tmp_path


# ─── profile store ─────────────────────────────────────────────────────────


def test_add_and_load_roundtrip():
    profiles.add_profile("prod", host="1.2.3.4", port=3307, user="ro", db="shop")
    data = profiles.load_profiles()
    assert data["current"] == "prod"
    assert data["profiles"]["prod"] == {"host": "1.2.3.4", "port": 3307, "user": "ro", "db": "shop"}


def test_profiles_file_is_0600(_isolated_config):
    profiles.add_profile("prod", host="h", user="u")
    mode = (_isolated_config / "profiles.yaml").stat().st_mode & 0o777
    assert mode == 0o600


def test_password_never_written_to_disk(_isolated_config):
    profiles.add_profile("prod", host="h", user="u", password_env="MYDB_PWD_PROD")
    text = (_isolated_config / "profiles.yaml").read_text()
    assert "password_env" in text
    assert "secret" not in text  # only the env var *name* is stored, never a value


def test_readonly_locked_persisted():
    profiles.add_profile("prod", host="h", user="u", readonly_locked=True)
    assert profiles.get_profile("prod")["readonly_locked"] is True


def test_use_and_remove():
    profiles.add_profile("prod", host="h", user="u")
    profiles.add_profile("local", host="127.0.0.1", user="root", make_current=False)
    profiles.use_profile("local")
    assert profiles.load_profiles()["current"] == "local"
    profiles.remove_profile("local")
    assert profiles.load_profiles()["current"] is None
    assert "local" not in profiles.load_profiles()["profiles"]


def test_get_current_raises_when_none():
    with pytest.raises(NotConnected):
        profiles.get_current()


def test_get_profile_missing_raises():
    with pytest.raises(ProfileNotFound):
        profiles.get_profile("nope")


def test_resolve_falls_back_to_current():
    profiles.add_profile("prod", host="h", user="u")
    name, prof = profiles.resolve(None)
    assert name == "prod" and prof["host"] == "h"


# ─── normalization ─────────────────────────────────────────────────────────


def test_normalize():
    assert profiles._normalize("prod-db") == "PROD_DB"
    assert profiles._normalize("prod.1") == "PROD_1"


def test_env_name_default_and_custom():
    assert profiles.env_name_for("prod-db", {}) == "MYDB_PWD_PROD_DB"
    assert profiles.env_name_for("prod", {"password_env": "MY_PW"}) == "MY_PW"


# ─── password resolution ───────────────────────────────────────────────────


def test_resolve_password_from_env(monkeypatch):
    monkeypatch.setenv("MYDB_PWD_PROD", "secret")
    assert profiles.resolve_password("prod", {"host": "h", "user": "u"}) == "secret"


def test_resolve_password_missing_raises(monkeypatch):
    monkeypatch.delenv("MYDB_PWD_PROD", raising=False)
    with pytest.raises(PasswordNotSet) as exc:
        profiles.resolve_password("prod", {"host": "h", "user": "u"})
    assert exc.value.code == "password_not_set"


def test_resolve_password_custom_env_name(monkeypatch):
    monkeypatch.setenv("MY_CUSTOM_PW", "s3cr3t")
    assert profiles.resolve_password("prod", {"password_env": "MY_CUSTOM_PW"}) == "s3cr3t"


def test_load_dotenv_does_not_override_exported(monkeypatch, _isolated_config):
    (_isolated_config / ".env").write_text('MYDB_PWD_X=fromfile\nMYDB_PWD_Y="yval"\n# comment\n\n')
    monkeypatch.setenv("MYDB_PWD_X", "fromenv")
    profiles._load_dotenv()
    assert os.environ["MYDB_PWD_X"] == "fromenv"  # exported var wins
    assert os.environ["MYDB_PWD_Y"] == "yval"  # loaded from file, quotes stripped
