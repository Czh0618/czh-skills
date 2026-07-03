"""Write/DDL command: mydb exec "..." --allow-write (gated by sql_guard)."""

from __future__ import annotations

import click

from .. import profiles
from ..client import MyDbClient
from ..sql_guard import guard
from ._common import (
    command_profile_option,
    emit_result,
    handle_errors,
    profile_override,
    structured_output_options,
)


@click.command("exec")
@click.argument("sql")
@click.option("--allow-write", is_flag=True, help="Required to run any write/DDL statement")
@click.option("-y", "--yes", is_flag=True, help="Confirm a dangerous statement (DROP/TRUNCATE/no-WHERE)")
@click.option("--limit", default=100, type=int, help="LIMIT for any rows returned")
@command_profile_option
@structured_output_options
@click.pass_context
def exec_(ctx, sql, allow_write, yes, limit, as_json, as_yaml):
    """Execute a write/DDL statement. Read-only by default — needs --allow-write."""

    def _fn():
        name, profile = profiles.resolve(profile_override(ctx))
        # readonly_locked profiles reject writes even with --allow-write.
        guard(sql, allow_write=allow_write, yes=yes, readonly_locked=bool(profile.get("readonly_locked")))
        with MyDbClient(name, profile, readonly=False) as client:
            data = client.run(sql, write=True, limit=limit)
        emit_result(data, as_json=as_json, as_yaml=as_yaml)

    handle_errors(_fn, as_json=as_json, as_yaml=as_yaml, prefix="Exec failed")
