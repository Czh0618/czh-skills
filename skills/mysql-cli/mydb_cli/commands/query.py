"""Read-only query command: mydb query "SELECT ..." (auto LIMIT if absent)."""

from __future__ import annotations

import click

from .. import profiles
from ..client import MyDbClient
from ..sql_guard import guard, inject_limit
from ._common import (
    command_profile_option,
    emit_result,
    handle_errors,
    profile_override,
    structured_output_options,
)


@click.command()
@click.argument("sql")
@click.option("--limit", default=100, type=int, show_default=True, help="Auto-injected LIMIT for bare SELECTs")
@command_profile_option
@structured_output_options
@click.pass_context
def query(ctx, sql, limit, as_json, as_yaml):
    """Run a read-only SELECT. Bare SELECTs get a LIMIT injected automatically."""

    def _fn():
        name, profile = profiles.resolve(profile_override(ctx))
        # Read-only command: reject any non-readonly statement (points user to `exec`).
        guard(sql, allow_write=False, yes=False, readonly_locked=bool(profile.get("readonly_locked")))
        final_sql = inject_limit(sql, limit)
        with MyDbClient(name, profile, readonly=True) as client:
            data = client.run(final_sql, limit=limit)
        emit_result(data, as_json=as_json, as_yaml=as_yaml)

    handle_errors(_fn, as_json=as_json, as_yaml=as_yaml, prefix="Query failed")
