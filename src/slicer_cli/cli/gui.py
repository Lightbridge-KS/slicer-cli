"""`slicer-cli gui ...` — switch viewer layout / GUI chrome (Phase 3).

Surface:
- `gui layout fourup [--contents full|viewers]`

Layout names are pass-through to Slicer (version-dependent: `fourup`,
`oneup3d`, `conventionalwidescreen`, `compareview`, etc.). Slicer returns
`{"success": true}` on success or 4xx/5xx if the layout name is invalid.
"""

from __future__ import annotations

import typer

from slicer_cli.cli._internal.context import CliContext
from slicer_cli.cli.output import render_error, render_success
from slicer_cli.client.errors import SlicerError, exit_code_for

app = typer.Typer(no_args_is_help=True, help="GUI layout / chrome control.")


@app.command("layout")
def layout_command(
    ctx: typer.Context,
    layout: str = typer.Argument(
        ...,
        help="Slicer layout name (e.g. fourup, oneup3d, conventionalwidescreen).",
    ),
    contents: str = typer.Option(
        "full",
        "--contents",
        help="GUI contents mode: 'full' (chrome + viewers) or 'viewers' (viewers only).",
    ),
) -> None:
    """Switch the Slicer viewer layout (and optionally hide GUI chrome)."""
    cli_ctx: CliContext = ctx.obj
    try:
        with cli_ctx.make_client() as client:
            result = client.set_layout(layout=layout, contents=contents)
    except SlicerError as error:
        render_error(error, mode=cli_ctx.output_mode)
        raise typer.Exit(code=exit_code_for(error.code)) from error

    render_success(
        {"layout": layout, "contents": contents, "result": result},
        mode=cli_ctx.output_mode,
        renderer="gui-layout",
    )
