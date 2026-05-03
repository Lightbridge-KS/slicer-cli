"""`slicer-cli markup ...` — fiducials, lines, etc. (Phase 3)."""

from __future__ import annotations

import typer

from slicer_cli.cli._internal.stub import stub

app = typer.Typer(no_args_is_help=True, help="Markup operations (fiducials, lines).")


@app.command("list")
def list_command(ctx: typer.Context) -> None:
    """List markup nodes (Phase 3)."""
    stub(ctx, "markup list", phase="Phase 3")


@app.command("fiducial-set")
def fiducial_set_command(ctx: typer.Context) -> None:
    """Set position of a fiducial control point (Phase 3)."""
    stub(ctx, "markup fiducial-set", phase="Phase 3")


@app.command("line")
def line_command(ctx: typer.Context) -> None:
    """Create a line markup between two RAS points (Phase 3)."""
    stub(ctx, "markup line", phase="Phase 3")
