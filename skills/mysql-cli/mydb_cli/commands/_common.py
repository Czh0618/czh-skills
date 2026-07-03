"""Common helpers for CLI commands: output options, client wiring, error exit."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

import click

from .. import profiles
from ..client import MyDbClient
from ..error_codes import error_code_for_exception
from ..exceptions import MyDbError
from ..formatter import render_rows
from ..formatter_utils import (
    emit_error,
    maybe_print_structured,
    print_error,
    success_payload,
)

T = TypeVar("T")


def structured_output_options(command: Callable) -> Callable:
    """Add --json/--yaml options to a Click command."""
    command = click.option("--yaml", "as_yaml", is_flag=True, help="Output as YAML.")(command)
    command = click.option("--json", "as_json", is_flag=True, help="Output as JSON.")(command)
    return command


def command_profile_option(command: Callable) -> Callable:
    """Add a subcommand-level --profile alias for agent-friendly invocation."""

    def _store_profile(ctx, _param, value):
        if value:
            ctx.ensure_object(dict)
            ctx.obj["profile"] = value
        return value

    return click.option(
        "--profile",
        expose_value=False,
        callback=_store_profile,
        help="Override the current profile for this command",
    )(command)


def profile_override(ctx) -> str | None:
    """Return the --profile override from the root context, if any."""
    return ctx.obj.get("profile") if ctx.obj else None


def get_client(ctx, *, readonly: bool) -> MyDbClient:
    """Build a client for the resolved (override or current) profile."""
    name, profile = profiles.resolve(profile_override(ctx))
    return MyDbClient(name, profile, readonly=readonly)


def emit_result(data: dict[str, Any], *, as_json: bool, as_yaml: bool) -> None:
    """Emit a success payload as structured output, else render a human table."""
    if not maybe_print_structured(success_payload(data), as_json=as_json, as_yaml=as_yaml):
        render_rows(data)


def run_readonly(
    ctx,
    action: Callable[[MyDbClient], dict[str, Any]],
    *,
    as_json: bool,
    as_yaml: bool,
    prefix: str | None = None,
) -> None:
    """Run a read-only client action and emit its result (or a structured error)."""

    def _fn():
        with get_client(ctx, readonly=True) as client:
            data = action(client)
        emit_result(data, as_json=as_json, as_yaml=as_yaml)

    handle_errors(_fn, as_json=as_json, as_yaml=as_yaml, prefix=prefix)


def handle_errors(
    fn: Callable[[], T],
    *,
    as_json: bool,
    as_yaml: bool,
    prefix: str | None = None,
) -> T | None:
    """Run command logic, funnelling any MyDbError through exit_for_error."""
    try:
        return fn()
    except MyDbError as exc:
        exit_for_error(exc, as_json=as_json, as_yaml=as_yaml, prefix=prefix)
        return None


def exit_for_error(exc: Exception, *, as_json: bool, as_yaml: bool, prefix: str | None = None) -> None:
    """Emit a structured/plain error and terminate the command with exit code 1."""
    message = str(exc)
    if prefix:
        message = f"{prefix}: {message}"

    if emit_error(error_code_for_exception(exc), message, as_json=as_json, as_yaml=as_yaml):
        raise SystemExit(1)

    print_error(message)
    raise SystemExit(1)
