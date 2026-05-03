"""`slicer-cli node ...` — single-node operations."""

from __future__ import annotations

import typer

from slicer_cli.cli._internal.context import CliContext
from slicer_cli.cli._internal.safety import require_nonempty_id
from slicer_cli.client.errors import SlicerError, exit_code_for
from slicer_cli.output import render_error, render_success

app = typer.Typer(no_args_is_help=True, help="Per-node MRML operations.")


@app.command("show")
def show_command(
    ctx: typer.Context,
    node_id: str = typer.Argument(..., help="MRML node id"),
) -> None:
    """Show full property dict for one MRML node."""
    cli_ctx: CliContext = ctx.obj
    try:
        cleaned = require_nonempty_id(node_id)
        with cli_ctx.make_client() as client:
            properties = client.get_node_properties(cleaned)
    except SlicerError as error:
        render_error(error, mode=cli_ctx.output_mode)
        raise typer.Exit(code=exit_code_for(error.code)) from error

    render_success(
        {"node": {"id": cleaned, "properties": properties}},
        mode=cli_ctx.output_mode,
        renderer="node-properties",
    )


@app.command("delete")
def delete_command(
    ctx: typer.Context,
    node_id: str = typer.Argument(..., help="MRML node id"),
) -> None:
    """Delete one node by id (DELETE /slicer/mrml?id=…). Rejects empty ids."""
    cli_ctx: CliContext = ctx.obj
    try:
        cleaned = require_nonempty_id(node_id)
        with cli_ctx.make_client() as client:
            result = client.delete_node(cleaned)
    except SlicerError as error:
        render_error(error, mode=cli_ctx.output_mode)
        raise typer.Exit(code=exit_code_for(error.code)) from error

    render_success(
        {"node_id": cleaned, "deleted": result.success},
        mode=cli_ctx.output_mode,
        renderer=None,
    )


@app.command("reload")
def reload_command(
    ctx: typer.Context,
    node_id: str = typer.Argument(..., help="MRML node id"),
) -> None:
    """Reload node from its original file (PUT /slicer/mrml?id=…)."""
    cli_ctx: CliContext = ctx.obj
    try:
        cleaned = require_nonempty_id(node_id)
        with cli_ctx.make_client() as client:
            result = client.reload_node(cleaned)
    except SlicerError as error:
        render_error(error, mode=cli_ctx.output_mode)
        raise typer.Exit(code=exit_code_for(error.code)) from error

    render_success(
        {"node_id": cleaned, "result": result},
        mode=cli_ctx.output_mode,
        renderer=None,
    )
