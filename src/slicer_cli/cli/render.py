"""`slicer-cli render ...` — slice / 3D / screenshot / glTF (Phase 2)."""

from __future__ import annotations

import typer

from slicer_cli.cli._internal.stub import stub

app = typer.Typer(no_args_is_help=True, help="Render slice, 3D, screenshot, glTF.")


@app.command("slice")
def slice_command(ctx: typer.Context) -> None:
    """Render a slice viewer to PNG (Phase 2)."""
    stub(ctx, "render slice", phase="Phase 2")


@app.command("threed")
def threed_command(ctx: typer.Context) -> None:
    """Render the first 3D view to PNG (Phase 2)."""
    stub(ctx, "render threed", phase="Phase 2")


@app.command("screenshot")
def screenshot_command(ctx: typer.Context) -> None:
    """Grab the main window as PNG (Phase 2)."""
    stub(ctx, "render screenshot", phase="Phase 2")


@app.command("gltf")
def gltf_command(ctx: typer.Context) -> None:
    """Export 3D view as glTF (Phase 2)."""
    stub(ctx, "render gltf", phase="Phase 2")
