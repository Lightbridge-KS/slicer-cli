"""`slicer-cli volume ...` — scalar / labelmap volume operations."""

from __future__ import annotations

import sys
from pathlib import Path

import typer

from slicer_cli.cli._internal.context import CliContext
from slicer_cli.cli._internal.safety import require_nonempty_id
from slicer_cli.cli.mrml._helpers import id_to_class
from slicer_cli.cli.output import render_error, render_meta_to_stderr, render_success
from slicer_cli.client.errors import SlicerError, exit_code_for

app = typer.Typer(no_args_is_help=True, help="Volume node operations.")


@app.command("list")
def list_command(ctx: typer.Context) -> None:
    """List scalar + labelmap volumes (id, name, class)."""
    cli_ctx: CliContext = ctx.obj
    try:
        with cli_ctx.make_client() as client:
            volumes = client.list_volumes()
    except SlicerError as error:
        render_error(error, mode=cli_ctx.output_mode)
        raise typer.Exit(code=exit_code_for(error.code)) from error

    payload = {
        "volumes": [{"id": v.id, "name": v.name, "class": id_to_class(v.id)} for v in volumes],
    }
    render_success(payload, mode=cli_ctx.output_mode, renderer="volumes")


@app.command("show")
def show_command(
    ctx: typer.Context,
    node_id: str = typer.Argument(..., help="MRML node id (e.g. vtkMRMLScalarVolumeNode1)"),
) -> None:
    """Show full property dict for one volume node."""
    cli_ctx: CliContext = ctx.obj
    try:
        with cli_ctx.make_client() as client:
            properties = client.get_node_properties(node_id)
    except SlicerError as error:
        render_error(error, mode=cli_ctx.output_mode)
        raise typer.Exit(code=exit_code_for(error.code)) from error

    render_success(
        {"node": {"id": node_id, "properties": properties}},
        mode=cli_ctx.output_mode,
        renderer="node-properties",
    )


@app.command("export")
def export_command(
    ctx: typer.Context,
    node_id: str = typer.Argument(..., help="MRML node id"),
    out: str = typer.Option(
        ...,
        "--out",
        help="Output path or '-' for stdout (required — locked Q-D).",
    ),
) -> None:
    """Stream a volume as NRRD bytes to file or stdout."""
    cli_ctx: CliContext = ctx.obj
    try:
        cleaned = require_nonempty_id(node_id)
        with cli_ctx.make_client() as client:
            data = client.download_volume(cleaned)
    except SlicerError as error:
        render_error(error, mode=cli_ctx.output_mode)
        raise typer.Exit(code=exit_code_for(error.code)) from error

    if out == "-":
        sys.stdout.buffer.write(data)
        sys.stdout.buffer.flush()
        if cli_ctx.output_mode == "json":
            render_meta_to_stderr(
                {"out": "-", "bytes": len(data), "node_id": cleaned, "format": "nrrd"},
                mode="json",
            )
    else:
        path = Path(out)
        path.write_bytes(data)
        # Even in JSON mode this goes to stdout — file is on disk, no binary on stdout.
        render_success(
            {"out": str(path), "bytes": len(data), "node_id": cleaned, "format": "nrrd"},
            mode=cli_ctx.output_mode,
            renderer=None,
        )


@app.command("import")
def import_command(
    ctx: typer.Context,
    path: str = typer.Argument(..., help="Server-side file path Slicer can read."),
    name: str | None = typer.Option(None, "--name", help="Optional name for the new node."),
) -> None:
    """Load a file as a volume node (POST /slicer/mrml?filetype=VolumeFile)."""
    cli_ctx: CliContext = ctx.obj
    extra = {"name": name} if name else None
    try:
        with cli_ctx.make_client() as client:
            result = client.load_file(filetype="VolumeFile", localfile=path, extra_params=extra)
    except SlicerError as error:
        render_error(error, mode=cli_ctx.output_mode)
        raise typer.Exit(code=exit_code_for(error.code)) from error

    render_success(
        {"path": path, "loaded_node_ids": result.loaded_node_ids},
        mode=cli_ctx.output_mode,
        renderer=None,
    )


@app.command("delete")
def delete_command(
    ctx: typer.Context,
    node_id: str = typer.Argument(..., help="MRML volume node id"),
) -> None:
    """Delete a volume node by id (DELETE /slicer/mrml?id=…). Rejects empty ids."""
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
