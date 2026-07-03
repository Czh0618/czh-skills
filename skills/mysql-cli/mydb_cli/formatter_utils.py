"""Base formatting utilities: the agent-friendly output envelope.

Migrated from xiaohongshu-cli's formatter_utils. Provides the shared
`{ok, schema_version, data|error}` envelope plus output-format resolution
(explicit flag > OUTPUT env > TTY detection; non-TTY defaults to JSON).
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

import click
import yaml
from rich.console import Console

console = Console(stderr=True)
error_console = Console(stderr=True)
_stdout = Console()
_OUTPUT_ENV = "OUTPUT"
_SCHEMA_VERSION = "1"


# ─── Output format resolution ──────────────────────────────────────────────


def resolve_output_format(*, as_json: bool, as_yaml: bool) -> str | None:
    """Resolve explicit flags first, then env override, then TTY default.

    Returns "json", "yaml", or None (None means render human/rich output).
    """
    if as_json and as_yaml:
        raise click.UsageError("Use only one of --json or --yaml.")
    if as_yaml:
        return "yaml"
    if as_json:
        return "json"

    output_mode = os.getenv(_OUTPUT_ENV, "auto").strip().lower()
    if output_mode == "yaml":
        return "yaml"
    if output_mode == "json":
        return "json"
    if output_mode == "rich":
        return None

    if not sys.stdout.isatty():
        return "json"
    return None


# ─── Structured output ─────────────────────────────────────────────────────


def print_json(data: Any) -> None:
    """Print raw JSON output to stdout."""
    click.echo(json.dumps(data, ensure_ascii=False, indent=2))


def print_yaml(data: Any) -> None:
    """Print raw YAML output to stdout."""
    click.echo(
        yaml.safe_dump(
            data,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
        )
    )


def success_payload(data: Any) -> dict[str, Any]:
    """Wrap structured success data in the shared agent schema."""
    return {
        "ok": True,
        "schema_version": _SCHEMA_VERSION,
        "data": data,
    }


def error_payload(code: str, message: str, *, details: Any | None = None) -> dict[str, Any]:
    """Wrap structured error data in the shared agent schema."""
    error: dict[str, Any] = {
        "code": code,
        "message": message,
    }
    if details is not None:
        error["details"] = details
    return {
        "ok": False,
        "schema_version": _SCHEMA_VERSION,
        "error": error,
    }


def _normalize_success_payload(data: Any) -> Any:
    """Wrap plain structured data in the shared agent success schema."""
    if isinstance(data, dict) and data.get("schema_version") == _SCHEMA_VERSION and "ok" in data:
        return data
    return success_payload(data)


def maybe_print_structured(data: Any, *, as_json: bool, as_yaml: bool) -> bool:
    """Print structured output when requested or when stdout is non-TTY.

    Returns True if structured output was printed (caller should skip rich rendering).
    """
    fmt = resolve_output_format(as_json=as_json, as_yaml=as_yaml)
    if not fmt:
        return False
    payload = _normalize_success_payload(data)
    if fmt == "json":
        print_json(payload)
    else:
        print_yaml(payload)
    return True


def emit_error(
    code: str,
    message: str,
    *,
    as_json: bool | None = None,
    as_yaml: bool | None = None,
    details: Any | None = None,
) -> bool:
    """Emit a structured error when the active output mode is machine-readable.

    Returns True if a structured error was printed.
    """
    if as_json is None or as_yaml is None:
        ctx = click.get_current_context(silent=True)
        params = ctx.params if ctx is not None else {}
        as_json = bool(params.get("as_json", False)) if as_json is None else as_json
        as_yaml = bool(params.get("as_yaml", False)) if as_yaml is None else as_yaml

    fmt = resolve_output_format(as_json=bool(as_json), as_yaml=bool(as_yaml))
    if fmt is None:
        return False

    payload = error_payload(code, message, details=details)
    if fmt == "json":
        print_json(payload)
    else:
        print_yaml(payload)
    return True


# ─── UI helpers (human output goes to stderr) ──────────────────────────────


def print_error(message: str) -> None:
    """Print an error message (structured if machine-readable, else red text)."""
    if emit_error("db_error", message):
        return
    error_console.print(f"[red]✗[/red] {message}")


def print_success(message: str) -> None:
    """Print a success message to stderr."""
    console.print(f"[green]✓[/green] {message}")


def print_info(message: str) -> None:
    """Print an info message to stderr."""
    console.print(f"[dim]ℹ[/dim] {message}")
