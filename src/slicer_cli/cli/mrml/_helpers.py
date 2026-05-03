"""CLI-layer helpers for MRML-flavored commands.

Protocol-level helpers (id_to_class, attach_class_to_refs) live in
`client/_id_helpers.py` per the architecture rule (CLI depends on client,
not the reverse). This module holds CLI-input parsing and rich rendering.
"""

from __future__ import annotations

from collections.abc import Sequence

from rich.table import Table

# Re-export so `cli/mrml/*.py` modules have a single import point for
# the helpers they need, without reaching across into `client/_id_helpers`.
from slicer_cli.client._id_helpers import (
    attach_class_to_refs as attach_class_to_refs,
    id_to_class as id_to_class,
)
from slicer_cli.client.models import NodeRef


def parse_class_filter(value: str | None) -> str | None:
    """Pass-through validator for `--class` filter values (locked Q-C: no aliases).

    Empty/whitespace becomes None so callers can drop the query parameter.
    """
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def format_node_table(rows: Sequence[NodeRef]) -> Table:
    """Build a rich Table for `scene nodes` / `volume list` pretty output.

    Centralises column headers and styling so all node-listing commands share
    the same visual shape.
    """
    table = Table(show_header=True, header_style="bold")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Name")
    table.add_column("Class", style="dim")
    for ref in rows:
        table.add_row(ref.id, ref.name, ref.class_ or "—")
    return table
