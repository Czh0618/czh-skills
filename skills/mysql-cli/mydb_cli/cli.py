"""CLI entry point for mydb — an agent-first MySQL CLI (read-only by default).

Usage:
    mydb conn add <name> --host H --user U [--db D] [--readonly-locked]
    mydb conn list / use <name> / test [name] / remove <name>
    mydb databases
    mydb tables [--db D]
    mydb describe <table>
    mydb indexes <table>
    mydb sample <table> [--limit N]
    mydb query "SELECT ..." [--limit N]
    mydb exec "UPDATE ..." --allow-write [-y]
"""

from __future__ import annotations

import logging

import click

from . import __version__
from .commands import connection, mutate, query, schema


@click.group()
@click.version_option(version=__version__, prog_name="mydb")
@click.option("-v", "--verbose", is_flag=True, help="Enable debug logging")
@click.option("--profile", default=None, help="Override the current profile for this command")
@click.pass_context
def cli(ctx, verbose: bool, profile: str | None):
    """mydb — an agent-first MySQL CLI (read-only by default) 🐬"""
    ctx.ensure_object(dict)
    ctx.obj["profile"] = profile
    logging.basicConfig(level=logging.DEBUG if verbose else logging.WARNING)


# ─── Connection commands ─────────────────────────────────────────────────────

cli.add_command(connection.conn)

# ─── Schema exploration (read-only) ──────────────────────────────────────────

cli.add_command(schema.databases)
cli.add_command(schema.tables)
cli.add_command(schema.describe)
cli.add_command(schema.indexes)
cli.add_command(schema.sample)

# ─── Query (read-only) ───────────────────────────────────────────────────────

cli.add_command(query.query)

# ─── Mutation (gated) ────────────────────────────────────────────────────────

cli.add_command(mutate.exec_)


if __name__ == "__main__":
    cli()
