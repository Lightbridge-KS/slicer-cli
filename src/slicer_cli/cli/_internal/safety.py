"""Safety guards shared across destructive CLI commands.

These helpers raise the canonical `SlicerError` subclasses so the CLI's top-level
error handler maps them to the right exit code (PRD §6.5):
- `SlicerDestructiveError`  → exit 6
- `SlicerEmptySelectorError` → exit 6

The helpers are intentionally `client/`-layer agnostic: they only wrap argument
validation. The actual destructive HTTP calls live on `SlicerClient`.
"""

from __future__ import annotations

from slicer_cli.client.errors import (
    SlicerDestructiveError,
    SlicerEmptySelectorError,
)


def require_confirm(value: bool, op: str, *, flag: str = "--confirm") -> None:
    """Raise SlicerDestructiveError unless `value` is True.

    Used by `scene clear`, `system shutdown`, and `api raw` against
    destructive endpoints.
    """
    if not value:
        raise SlicerDestructiveError(op, confirm_flag=flag)


def require_nonempty_id(node_id: str | None) -> str:
    """Trim whitespace and reject empty ids.

    Returns the cleaned id on success. Raises SlicerEmptySelectorError if the
    input is None or empty/whitespace — this prevents accidentally sending
    `DELETE /slicer/mrml?id=` (which Slicer interprets as "delete all").
    """
    cleaned = (node_id or "").strip()
    if not cleaned:
        raise SlicerEmptySelectorError()
    return cleaned
