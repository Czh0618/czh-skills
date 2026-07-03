"""Custom exceptions for the mydb CLI.

Each exception carries a stable ``code`` string that maps directly to the
``error.code`` field of the agent envelope (see error_codes.py).
"""

from __future__ import annotations


class MyDbError(Exception):
    """Base exception for all mydb CLI errors."""

    def __init__(self, message: str, code: str | None = None):
        super().__init__(message)
        self.code = code


class NotConnected(MyDbError):
    """No active connection profile is selected."""

    def __init__(self, message: str = "No active connection. Run: mydb conn use <name>"):
        super().__init__(message, code="not_connected")


class ProfileNotFound(MyDbError):
    """Requested connection profile does not exist."""

    def __init__(self, name: str):
        super().__init__(f"Connection profile not found: {name}", code="profile_not_found")
        self.name = name


class PasswordNotSet(MyDbError):
    """Password environment variable is missing for the profile."""

    def __init__(self, env_name: str):
        super().__init__(
            f"Password not set. Export {env_name}=... or add it to ~/.mydb-cli/.env",
            code="password_not_set",
        )
        self.env_name = env_name


class WriteNotAllowed(MyDbError):
    """A write/DDL statement was blocked because writes are not enabled."""

    def __init__(self, message: str):
        super().__init__(message, code="write_not_allowed")


class NeedsConfirm(MyDbError):
    """A dangerous statement requires explicit confirmation (-y)."""

    def __init__(self, message: str):
        super().__init__(message, code="confirmation_required")


class DbConnectionError(MyDbError):
    """Failed to connect to the database (network, auth, timeout)."""

    def __init__(self, message: str):
        super().__init__(message, code="connection_error")


class QueryError(MyDbError):
    """The database rejected the SQL statement."""

    def __init__(self, message: str):
        super().__init__(message, code="query_error")
