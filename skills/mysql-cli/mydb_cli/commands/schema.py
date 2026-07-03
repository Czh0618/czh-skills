"""Read-only schema exploration: databases / tables / describe / indexes / sample."""

from __future__ import annotations

import click

from ._common import command_profile_option, run_readonly, structured_output_options


def _ident(name: str) -> str:
    """Quote an identifier as a backtick-delimited name (escaping backticks)."""
    return "`" + name.replace("`", "``") + "`"


@click.command()
@command_profile_option
@structured_output_options
@click.pass_context
def databases(ctx, as_json, as_yaml):
    """List databases (SHOW DATABASES)."""
    run_readonly(ctx, lambda c: c.run("SHOW DATABASES"), as_json=as_json, as_yaml=as_yaml,
                 prefix="Failed to list databases")


@click.command()
@click.option("--db", default=None, help="Database to list tables from")
@command_profile_option
@structured_output_options
@click.pass_context
def tables(ctx, db, as_json, as_yaml):
    """List tables (SHOW TABLES)."""
    sql = f"SHOW TABLES FROM {_ident(db)}" if db else "SHOW TABLES"
    run_readonly(ctx, lambda c: c.run(sql), as_json=as_json, as_yaml=as_yaml,
                 prefix="Failed to list tables")


@click.command()
@click.argument("table")
@command_profile_option
@structured_output_options
@click.pass_context
def describe(ctx, table, as_json, as_yaml):
    """Show a table's columns, types, and comments (SHOW FULL COLUMNS)."""
    run_readonly(ctx, lambda c: c.run(f"SHOW FULL COLUMNS FROM {_ident(table)}"),
                 as_json=as_json, as_yaml=as_yaml, prefix="Failed to describe table")


@click.command()
@click.argument("table")
@command_profile_option
@structured_output_options
@click.pass_context
def indexes(ctx, table, as_json, as_yaml):
    """Show a table's indexes (SHOW INDEX)."""
    run_readonly(ctx, lambda c: c.run(f"SHOW INDEX FROM {_ident(table)}"),
                 as_json=as_json, as_yaml=as_yaml, prefix="Failed to list indexes")


@click.command()
@click.argument("table")
@click.option("--limit", default=10, type=int, show_default=True, help="Rows to sample")
@command_profile_option
@structured_output_options
@click.pass_context
def sample(ctx, table, limit, as_json, as_yaml):
    """Sample a few rows from a table (SELECT * ... LIMIT n)."""
    sql = f"SELECT * FROM {_ident(table)} LIMIT {int(limit)}"
    run_readonly(ctx, lambda c: c.run(sql, limit=limit), as_json=as_json, as_yaml=as_yaml,
                 prefix="Failed to sample table")
