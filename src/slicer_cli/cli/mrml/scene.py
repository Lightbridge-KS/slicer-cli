"""`slicer-cli scene ...` — MRML scene-level operations."""

from __future__ import annotations

import typer

from slicer_cli.cli._internal.context import CliContext
from slicer_cli.cli._internal.safety import require_confirm
from slicer_cli.cli.mrml._helpers import parse_class_filter
from slicer_cli.cli.output import render_error, render_success
from slicer_cli.client.errors import SlicerError, exit_code_for

app = typer.Typer(no_args_is_help=True, help="MRML scene operations.")


@app.command("nodes")
def nodes_command(
    ctx: typer.Context,
    class_: str | None = typer.Option(
        None,
        "--class",
        "-c",
        help="Filter by VTK class (e.g. vtkMRMLScalarVolumeNode).",
    ),
    name: str | None = typer.Option(None, "--name", "-n", help="Filter by node name."),
) -> None:
    """List MRML nodes with id+name+class."""
    cli_ctx: CliContext = ctx.obj
    cleaned_class = parse_class_filter(class_)
    try:
        with cli_ctx.make_client() as client:
            nodes = client.list_nodes(class_=cleaned_class, name=name)
    except SlicerError as error:
        render_error(error, mode=cli_ctx.output_mode)
        raise typer.Exit(code=exit_code_for(error.code)) from error

    payload = {
        "nodes": [{"id": n.id, "name": n.name, "class": n.class_} for n in nodes],
    }
    render_success(payload, mode=cli_ctx.output_mode, renderer="nodes")


@app.command("ids")
def ids_command(
    ctx: typer.Context,
    class_: str | None = typer.Option(None, "--class", "-c"),
    name: str | None = typer.Option(None, "--name", "-n"),
) -> None:
    """List MRML node IDs only (terse, for piping)."""
    cli_ctx: CliContext = ctx.obj
    cleaned_class = parse_class_filter(class_)
    try:
        with cli_ctx.make_client() as client:
            ids = client.list_node_ids(class_=cleaned_class, name=name)
    except SlicerError as error:
        render_error(error, mode=cli_ctx.output_mode)
        raise typer.Exit(code=exit_code_for(error.code)) from error

    render_success({"ids": ids}, mode=cli_ctx.output_mode, renderer="ids")


@app.command("clear")
def clear_command(
    ctx: typer.Context,
    confirm: bool = typer.Option(False, "--confirm", help="Required to actually wipe the scene."),
) -> None:
    """Wipe the entire MRML scene (DELETE /slicer/mrml with no params).

    Without `--confirm`, returns E_DESTRUCTIVE and never makes the HTTP call.
    """
    cli_ctx: CliContext = ctx.obj
    try:
        require_confirm(confirm, "scene clear")
        with cli_ctx.make_client() as client:
            result = client.clear_scene()
    except SlicerError as error:
        render_error(error, mode=cli_ctx.output_mode)
        raise typer.Exit(code=exit_code_for(error.code)) from error

    render_success({"cleared": result.success}, mode=cli_ctx.output_mode, renderer=None)


@app.command("save")
def save_command(
    ctx: typer.Context,
    path: str = typer.Argument(..., help="Server-side path; .mrb (bundle) or .mrml (XML)."),
) -> None:
    """Save the entire scene to disk.

    Implementation note: Slicer has no native HTTP "save scene" endpoint, so
    we send a templated payload to /slicer/exec calling slicer.util.saveScene
    (locked Q-A: implement now via templated payload, migrate in Phase 3).
    """
    cli_ctx: CliContext = ctx.obj
    try:
        with cli_ctx.make_client() as client:
            result = client.save_scene(path)
    except SlicerError as error:
        render_error(error, mode=cli_ctx.output_mode)
        raise typer.Exit(code=exit_code_for(error.code)) from error

    render_success(
        {"path": path, "result": result},
        mode=cli_ctx.output_mode,
        renderer=None,
    )


@app.command("load")
def load_command(
    ctx: typer.Context,
    path: str = typer.Argument(..., help="Server-side path to a .mrb / .mrml scene file."),
) -> None:
    """Load a scene file (POST /slicer/mrml?filetype=SceneFile)."""
    cli_ctx: CliContext = ctx.obj
    try:
        with cli_ctx.make_client() as client:
            result = client.load_file(filetype="SceneFile", localfile=path)
    except SlicerError as error:
        render_error(error, mode=cli_ctx.output_mode)
        raise typer.Exit(code=exit_code_for(error.code)) from error

    render_success(
        {"path": path, "loaded_node_ids": result.loaded_node_ids},
        mode=cli_ctx.output_mode,
        renderer=None,
    )
