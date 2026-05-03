"""`slicer-cli exec ...` — run Python in Slicer's interpreter (Phase 3, gated)."""

from __future__ import annotations

import typer

from slicer_cli.cli._internal.stub import stub

app = typer.Typer(
    no_args_is_help=True,
    help="Run Python in Slicer's interpreter (gated by config.exec.enabled).",
)


@app.callback(invoke_without_command=True)
def exec_command(ctx: typer.Context) -> None:
    """POST /slicer/exec — gated remote shell (Phase 3)."""
    if ctx.invoked_subcommand is None:
        stub(ctx, "exec", phase="Phase 3")
