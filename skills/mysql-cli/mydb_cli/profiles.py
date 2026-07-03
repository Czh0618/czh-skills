"""Connection profiles and password resolution.

Profiles live in ``~/.mydb-cli/profiles.yaml`` (0600) and store only
non-sensitive fields (host/port/user/db). Passwords are NEVER written to
disk — they are resolved per-db from environment variables, optionally
seeded from ``~/.mydb-cli/.env``. Set ``MYDB_CONFIG_DIR`` to override the
config directory (used by tests).
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml

from .exceptions import NotConnected, PasswordNotSet, ProfileNotFound

_NON_ALNUM = re.compile(r"[^A-Z0-9]")


def _config_dir() -> Path:
    override = os.environ.get("MYDB_CONFIG_DIR")
    return Path(override) if override else Path.home() / ".mydb-cli"


def _profiles_path() -> Path:
    return _config_dir() / "profiles.yaml"


def _dotenv_path() -> Path:
    return _config_dir() / ".env"


def _normalize(name: str) -> str:
    """Uppercase and replace non-alphanumeric chars with underscores."""
    return _NON_ALNUM.sub("_", name.upper())


# ─── profile store ─────────────────────────────────────────────────────────


def load_profiles() -> dict[str, Any]:
    """Load the profile store, returning an empty skeleton if absent."""
    path = _profiles_path()
    if not path.exists():
        return {"current": None, "profiles": {}}
    data = yaml.safe_load(path.read_text()) or {}
    data.setdefault("current", None)
    data.setdefault("profiles", {})
    return data


def save_profiles(data: dict[str, Any]) -> None:
    """Persist the profile store with locked-down permissions (dir 0700, file 0600)."""
    directory = _config_dir()
    directory.mkdir(parents=True, exist_ok=True)
    directory.chmod(0o700)
    path = _profiles_path()
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False))
    path.chmod(0o600)


def add_profile(
    name: str,
    *,
    host: str,
    user: str,
    port: int = 3306,
    db: str | None = None,
    password_env: str | None = None,
    readonly_locked: bool = False,
    make_current: bool = True,
) -> dict[str, Any]:
    """Create or overwrite a profile; make it current by default."""
    data = load_profiles()
    profile: dict[str, Any] = {"host": host, "port": port, "user": user}
    if db:
        profile["db"] = db
    if password_env:
        profile["password_env"] = password_env
    if readonly_locked:
        profile["readonly_locked"] = True
    data["profiles"][name] = profile
    if make_current or data.get("current") is None:
        data["current"] = name
    save_profiles(data)
    return profile


def remove_profile(name: str) -> None:
    """Delete a profile; clear the current pointer if it referenced it."""
    data = load_profiles()
    if name not in data.get("profiles", {}):
        raise ProfileNotFound(name)
    del data["profiles"][name]
    if data.get("current") == name:
        data["current"] = None
    save_profiles(data)


def use_profile(name: str) -> None:
    """Set the current/default profile."""
    data = load_profiles()
    if name not in data.get("profiles", {}):
        raise ProfileNotFound(name)
    data["current"] = name
    save_profiles(data)


def get_profile(name: str) -> dict[str, Any]:
    """Return a profile by name or raise ProfileNotFound."""
    profiles = load_profiles().get("profiles", {})
    if name not in profiles:
        raise ProfileNotFound(name)
    return profiles[name]


def get_current() -> tuple[str, dict[str, Any]]:
    """Return (name, profile) of the current profile or raise NotConnected."""
    data = load_profiles()
    name = data.get("current")
    if not name or name not in data.get("profiles", {}):
        raise NotConnected()
    return name, data["profiles"][name]


def resolve(name: str | None) -> tuple[str, dict[str, Any]]:
    """Resolve a profile by explicit name, else fall back to the current one."""
    if name:
        return name, get_profile(name)
    return get_current()


# ─── password resolution (env / .env) ──────────────────────────────────────


def env_name_for(name: str, profile: dict[str, Any]) -> str:
    """Return the environment variable name a profile's password reads from."""
    return profile.get("password_env") or f"MYDB_PWD_{_normalize(name)}"


def _load_dotenv() -> None:
    """Seed os.environ from ~/.mydb-cli/.env without overriding existing vars."""
    path = _dotenv_path()
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, val)


def resolve_password(name: str, profile: dict[str, Any]) -> str:
    """Resolve a profile's password from the environment (or .env)."""
    _load_dotenv()
    env_name = env_name_for(name, profile)
    password = os.environ.get(env_name)
    if password is None:
        raise PasswordNotSet(env_name)
    return password
