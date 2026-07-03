"""SQL safety classification — the security core of mydb.

⚠️  This module is a *foot-gun guard*, NOT an injection boundary. It parses
only the leading keyword via regex and cannot understand arbitrary SQL. The
hard read-only guarantee must come from a least-privilege MySQL account
(``GRANT SELECT``). Defense in depth here:

  1. least-privilege account (hard boundary — enforced by the server)
  2. connection-level ``SET SESSION TRANSACTION READ ONLY`` (client.py)
  3. this keyword classifier (blocks obvious agent slip-ups)

The client also refuses multi-statement execution (no CLIENT.MULTI_STATEMENTS),
so ``SELECT 1; DROP TABLE x`` is rejected by the driver, not smuggled past here.
"""

from __future__ import annotations

import re

from .exceptions import NeedsConfirm, WriteNotAllowed

# Classification results.
READONLY = "READONLY"
WRITE = "WRITE"
DANGER = "DANGER"

_READONLY_HEADS = frozenset({"SELECT", "SHOW", "DESCRIBE", "DESC", "EXPLAIN", "WITH"})
_DANGER_HEADS = frozenset({"DROP", "TRUNCATE", "ALTER"})
_NO_WHERE_HEADS = frozenset({"UPDATE", "DELETE"})
_LIMIT_INJECTABLE_HEADS = frozenset({"SELECT", "WITH"})

_COMMENT_BLOCK = re.compile(r"/\*.*?\*/", re.S)
_COMMENT_LINE = re.compile(r"(--|#)[^\n]*")
_FIRST_WORD = re.compile(r"\s*(\w+)")
_HAS_WHERE = re.compile(r"\bWHERE\b", re.I)
_HAS_LIMIT = re.compile(r"\bLIMIT\b", re.I)


def _strip_comments(sql: str) -> str:
    """Remove block/line comments so the leading keyword is reachable."""
    sql = _COMMENT_BLOCK.sub(" ", sql)
    sql = _COMMENT_LINE.sub(" ", sql)
    return sql.strip()


def _head(sql: str) -> str:
    """Return the leading keyword (uppercased) of a comment-stripped statement."""
    m = _FIRST_WORD.match(_strip_comments(sql))
    return m.group(1).upper() if m else ""


def classify(sql: str) -> str:
    """Classify a statement as READONLY, WRITE, or DANGER.

    Unrecognized/empty statements are treated as WRITE (conservative: they will
    be blocked unless writes are explicitly enabled).
    """
    s = _strip_comments(sql)
    head = _head(s)
    if not head:
        return WRITE
    if head in _READONLY_HEADS:
        return READONLY
    if head in _DANGER_HEADS:
        return DANGER
    if head in _NO_WHERE_HEADS:
        return WRITE if _HAS_WHERE.search(s) else DANGER
    return WRITE


def guard(sql: str, *, allow_write: bool, yes: bool, readonly_locked: bool) -> str:
    """Enforce the write policy for a statement; return its classification.

    Raises WriteNotAllowed or NeedsConfirm when the statement is not permitted.
    """
    kind = classify(sql)

    if readonly_locked and kind != READONLY:
        raise WriteNotAllowed(
            "This profile is locked read-only; write statements are always rejected."
        )
    if kind in (WRITE, DANGER) and not allow_write:
        raise WriteNotAllowed(
            f"Write statement blocked ({kind}). Re-run with --allow-write to enable writes."
        )
    if kind == DANGER and allow_write and not yes:
        raise NeedsConfirm(
            "Dangerous statement (DROP/TRUNCATE/ALTER, or UPDATE/DELETE without WHERE). "
            "Re-run with -y to confirm."
        )
    return kind


def inject_limit(sql: str, limit: int) -> str:
    """Append ``LIMIT n`` to a bare SELECT/WITH query; idempotent otherwise.

    Only SELECT and WITH are touched — SHOW/DESCRIBE/EXPLAIN reject a trailing
    LIMIT clause in MySQL, so injecting one would break them.
    """
    s = _strip_comments(sql)
    if _head(s) not in _LIMIT_INJECTABLE_HEADS:
        return sql
    if _HAS_LIMIT.search(s):
        return sql
    return sql.rstrip().rstrip(";").rstrip() + f" LIMIT {limit}"
