"""Helpers for not-yet-implemented commands.

Lets a command appear in `--help` listings while still failing fast at
runtime with a clear `E_NOT_IMPLEMENTED` and a roadmap pointer. The
roadmap pointer is free-form text passed by the caller — see callers
for current conventions.
"""

from __future__ import annotations

import typer

from slicer_cli.cli._internal.context import CliContext
from slicer_cli.cli.output import render_error
from slicer_cli.client.errors import SlicerNotImplementedError, exit_code_for


def stub(ctx: typer.Context, what: str, *, phase: str) -> None:
    """Render an E_NOT_IMPLEMENTED error and exit."""
    cli_ctx: CliContext = ctx.obj
    error = SlicerNotImplementedError(what, phase=phase)
    render_error(error, mode=cli_ctx.output_mode)
    raise typer.Exit(code=exit_code_for(error.code))
