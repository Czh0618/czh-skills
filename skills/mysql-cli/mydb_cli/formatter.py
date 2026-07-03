"""Human-facing rich rendering for result sets.

Structured (envelope) output is handled in formatter_utils; this module only
renders the compact ``{columns, rows, ...}`` payload as a table when a human
is at the terminal.
"""

from __future__ import annotations

from typing import Any

from rich.table import Table

from .formatter_utils import _stdout, console


def _fmt(value: Any) -> str:
    return "NULL" if value is None else str(value)


def render_rows(data: dict[str, Any]) -> None:
    """Render a result payload as a table (or an affected-rows line for writes)."""
    columns = data.get("columns") or []

    if not columns:
        if "affected_rows" in data:
            console.print(f"[green]✓[/green] {data['affected_rows']} row(s) affected")
        else:
            console.print("[dim](no rows)[/dim]")
        return

    table = Table(show_header=True, header_style="bold")
    for col in columns:
        table.add_column(str(col))
    for row in data.get("rows", []):
        table.add_row(*[_fmt(v) for v in row])
    _stdout.print(table)

    meta = f"{data.get('row_count', 0)} row(s)"
    if data.get("truncated"):
        meta += " — truncated, use --limit to see more"
    console.print(f"[dim]{meta}[/dim]")
