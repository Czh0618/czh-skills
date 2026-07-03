"""Stable error-code mapping for structured CLI output.

Every user-facing failure is funnelled through here so the agent envelope's
``error.code`` field stays stable and machine-checkable.
"""

from __future__ import annotations

from .exceptions import MyDbError

# Codes documented in SKILL.md; kept in sync with exceptions.py.
_KNOWN_CODES = frozenset(
    {
        "not_connected",
        "profile_not_found",
        "password_not_set",
        "write_not_allowed",
        "confirmation_required",
        "connection_error",
        "query_error",
    }
)


def error_code_for_exception(exc: Exception) -> str:
    """Map an exception to a stable structured error code."""
    if isinstance(exc, MyDbError):
        if exc.code in _KNOWN_CODES:
            return exc.code
        return "db_error"
    return "unknown_error"
