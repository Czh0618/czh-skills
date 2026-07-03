"""Short-lived PyMySQL client used by the CLI commands."""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

import pymysql

from .exceptions import DbConnectionError, QueryError
from .profiles import resolve_password


class MyDbClient:
    """Open one MySQL connection for one command, then close it."""

    def __init__(self, name: str, profile: dict[str, Any], *, readonly: bool):
        self.name = name
        self.profile = profile
        self.readonly = readonly
        self._conn: Any | None = None

    def __enter__(self) -> "MyDbClient":
        try:
            self._conn = pymysql.connect(**self._connect_kwargs())
            if self.readonly:
                with self._conn.cursor() as cursor:
                    cursor.execute("SET SESSION TRANSACTION READ ONLY")
        except pymysql.MySQLError as exc:
            self.close()
            raise DbConnectionError(_mysql_error_message(exc)) from exc
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        if exc is not None and self._conn is not None:
            rollback = getattr(self._conn, "rollback", None)
            if callable(rollback):
                rollback()
        self.close()
        return False

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def run(
        self,
        sql: str,
        *,
        args: Any | None = None,
        write: bool = False,
        limit: int | None = 100,
    ) -> dict[str, Any]:
        """Execute a statement and return a compact, JSON-safe result payload."""
        if self._conn is None:
            raise QueryError("Database connection is not open.")

        try:
            with self._conn.cursor() as cursor:
                cursor.execute(sql, args)
                if cursor.description:
                    return self._rows_payload(cursor, limit)

                if write:
                    self._conn.commit()
                return {"affected_rows": cursor.rowcount}
        except pymysql.MySQLError as exc:
            raise QueryError(_mysql_error_message(exc)) from exc

    def _connect_kwargs(self) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "host": self.profile["host"],
            "port": int(self.profile.get("port", 3306)),
            "user": self.profile["user"],
            "password": resolve_password(self.name, self.profile),
            "charset": self.profile.get("charset", "utf8mb4"),
            "autocommit": False,
            "connect_timeout": int(self.profile.get("connect_timeout", 10)),
            "read_timeout": int(self.profile.get("read_timeout", 30)),
            "write_timeout": int(self.profile.get("write_timeout", 30)),
        }
        if self.profile.get("db"):
            kwargs["database"] = self.profile["db"]
        return kwargs

    def _rows_payload(self, cursor: Any, limit: int | None) -> dict[str, Any]:
        columns = [col[0] for col in cursor.description]
        rows, truncated = _fetch_rows(cursor, limit)
        return {
            "columns": columns,
            "rows": [[_json_safe(value) for value in row] for row in rows],
            "row_count": len(rows),
            "truncated": truncated,
        }


def _fetch_rows(cursor: Any, limit: int | None) -> tuple[list[Any], bool]:
    if limit is None or limit <= 0:
        rows = list(cursor.fetchall())
        return rows, False

    if hasattr(cursor, "fetchmany"):
        rows = list(cursor.fetchmany(limit + 1))
        truncated = len(rows) > limit
        return rows[:limit], truncated

    rows = list(cursor.fetchall())
    truncated = len(rows) >= limit
    return rows[:limit], truncated


def _json_safe(value: Any) -> Any:
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (bytes, bytearray)):
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError:
            return "0x" + bytes(value).hex()
    return value


def _mysql_error_message(exc: pymysql.MySQLError) -> str:
    if len(exc.args) >= 2:
        return f"MySQL error {exc.args[0]}: {exc.args[1]}"
    return str(exc)
