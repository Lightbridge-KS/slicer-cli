"""`slicer-cli render ...` — slice / 3D / screenshot / glTF.

All four commands write binary content (PNG or glTF) to the path given by
`--out`, or to stdout if `--out -`. Following the Phase-1 `volume export`
contract: `--out` is required (no surprise binary on TTY); the JSON
success envelope goes to stderr in `--json` mode whenever stdout is
holding bytes.
"""

from __future__ import annotations

import sys
from pathlib import Path

import typer

from slicer_cli.cli._internal.context import CliContext
from slicer_cli.client.errors import SlicerError, exit_code_for
from slicer_cli.output import render_error, render_meta_to_stderr, render_success

app = typer.Typer(no_args_is_help=True, help="Render slice, 3D, screenshot, glTF.")


@app.command("slice")
def slice_command(
    ctx: typer.Context,
    out: str = typer.Option(..., "--out", help="Output path or '-' for stdout."),
    view: str = typer.Option("red", "--view", "-v", help="Slice viewer: red | yellow | green."),
    orientation: str | None = typer.Option(
        None, "--orientation", "-o", help="axial | sagittal | coronal."
    ),
    offset: float | None = typer.Option(None, "--offset", help="Slice offset in millimetres."),
    scroll_to: float | None = typer.Option(
        None, "--scroll-to", help="Normalized 0..1 scroll position."
    ),
    size: int | None = typer.Option(None, "--size", "-s", help="Render size in pixels."),
) -> None:
    """Render a slice viewer to PNG."""
    cli_ctx: CliContext = ctx.obj
    try:
        with cli_ctx.make_client() as client:
            data = client.render_slice(
                view=view,
                orientation=orientation,
                offset=offset,
                scroll_to=scroll_to,
                size=size,
            )
    except SlicerError as error:
        render_error(error, mode=cli_ctx.output_mode)
        raise typer.Exit(code=exit_code_for(error.code)) from error

    _emit_binary(cli_ctx, out=out, data=data, format_="png", meta={"view": view})


@app.command("threed")
def threed_command(
    ctx: typer.Context,
    out: str = typer.Option(..., "--out", help="Output path or '-' for stdout."),
    look: str | None = typer.Option(
        None, "--look", "-l", help="Camera axis: A | P | L | R | I | S."
    ),
) -> None:
    """Render the first 3D view to PNG."""
    cli_ctx: CliContext = ctx.obj
    try:
        with cli_ctx.make_client() as client:
            data = client.render_threed(look_from_axis=look)
    except SlicerError as error:
        render_error(error, mode=cli_ctx.output_mode)
        raise typer.Exit(code=exit_code_for(error.code)) from error

    _emit_binary(cli_ctx, out=out, data=data, format_="png", meta={"look": look})


@app.command("screenshot")
def screenshot_command(
    ctx: typer.Context,
    out: str = typer.Option(..., "--out", help="Output path or '-' for stdout."),
) -> None:
    """Grab Slicer's main window as PNG. Requires the GUI to be alive."""
    cli_ctx: CliContext = ctx.obj
    try:
        with cli_ctx.make_client() as client:
            data = client.screenshot()
    except SlicerError as error:
        render_error(error, mode=cli_ctx.output_mode)
        raise typer.Exit(code=exit_code_for(error.code)) from error

    _emit_binary(cli_ctx, out=out, data=data, format_="png", meta={})


@app.command("gltf")
def gltf_command(
    ctx: typer.Context,
    out: str = typer.Option(..., "--out", help="Output path or '-' for stdout."),
    widget: int = typer.Option(0, "--widget", help="3D widget index (default 0)."),
) -> None:
    """Export the 3D view as glTF (binary `.glb` or JSON `.gltf` depending on Slicer build)."""
    cli_ctx: CliContext = ctx.obj
    try:
        with cli_ctx.make_client() as client:
            data = client.render_gltf(widget_index=widget)
    except SlicerError as error:
        render_error(error, mode=cli_ctx.output_mode)
        raise typer.Exit(code=exit_code_for(error.code)) from error

    _emit_binary(cli_ctx, out=out, data=data, format_="gltf", meta={"widget": widget})


# --------------------------------------------------------------- shared output helper


def _emit_binary(
    cli_ctx: CliContext,
    *,
    out: str,
    data: bytes,
    format_: str,
    meta: dict[str, object],
) -> None:
    """Write `data` to `out` (or stdout if '-') and surface the right envelope.

    Identical contract to `volume export` (cli/mrml/volume.py): in JSON mode,
    binary on stdout sends the success envelope to stderr; binary to a file
    sends the envelope to stdout normally.
    """
    base_payload: dict[str, object] = {
        "out": out,
        "bytes": len(data),
        "format": format_,
        **meta,
    }

    if out == "-":
        sys.stdout.buffer.write(data)
        sys.stdout.buffer.flush()
        if cli_ctx.output_mode == "json":
            render_meta_to_stderr(base_payload, mode="json")
        return

    path = Path(out)
    path.write_bytes(data)
    base_payload["out"] = str(path)
    render_success(base_payload, mode=cli_ctx.output_mode, renderer=None)
