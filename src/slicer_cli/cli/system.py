"""`slicer-cli system ...` — version + shutdown."""

from __future__ import annotations

import typer

from slicer_cli.cli._internal.context import CliContext
from slicer_cli.cli._internal.safety import require_confirm
from slicer_cli.client.errors import SlicerError, exit_code_for
from slicer_cli.output import render_error, render_success

app = typer.Typer(no_args_is_help=True, help="Application-level operations.")


@app.command("version")
def version_command(ctx: typer.Context) -> None:
    """Show Slicer's application identity (GET /slicer/system/version)."""
    cli_ctx: CliContext = ctx.obj
    try:
        with cli_ctx.make_client() as client:
            version = client.system_version()
    except SlicerError as error:
        render_error(error, mode=cli_ctx.output_mode)
        raise typer.Exit(code=exit_code_for(error.code)) from error

    render_success(
        version.model_dump(by_alias=True, exclude_none=True),
        mode=cli_ctx.output_mode,
        renderer="version",
    )


@app.command("shutdown")
def shutdown_command(
    ctx: typer.Context,
    confirm: bool = typer.Option(False, "--confirm", help="Required to actually shut down."),
) -> None:
    """DELETE /slicer/system — schedules a 1 s deferred quit.

    Without `--confirm`, returns E_DESTRUCTIVE and never makes the HTTP call.
    """
    cli_ctx: CliContext = ctx.obj
    try:
        require_confirm(confirm, "system shutdown")
        with cli_ctx.make_client() as client:
            result = client.shutdown()
    except SlicerError as error:
        render_error(error, mode=cli_ctx.output_mode)
        raise typer.Exit(code=exit_code_for(error.code)) from error

    render_success({"shutdown": result}, mode=cli_ctx.output_mode, renderer=None)
