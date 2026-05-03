"""Helpers for not-yet-implemented commands.

Phase 0 ships the full command surface visible via --help, but most groups
return E_NOT_IMPLEMENTED with a phase pointer. This avoids the agent
discovering missing groups (and lets us tick them on as phases land).
"""

from __future__ import annotations

import typer

from slicer_cli.cli._internal.context import CliContext
from slicer_cli.client.errors import SlicerNotImplementedError, exit_code_for
from slicer_cli.output import render_error


def stub(ctx: typer.Context, what: str, *, phase: str) -> None:
    """Render an E_NOT_IMPLEMENTED error and exit."""
    cli_ctx: CliContext = ctx.obj
    error = SlicerNotImplementedError(what, phase=phase)
    render_error(error, mode=cli_ctx.output_mode)
    raise typer.Exit(code=exit_code_for(error.code))
