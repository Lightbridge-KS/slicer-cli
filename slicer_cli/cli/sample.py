"""`slicer-cli sample ...` — built-in SampleData operations.

`sample list` is offline — it returns a curated allow-list bundled with
the CLI rather than calling Slicer (Slicer's SampleData module discovers
samples at runtime and has no listing endpoint).
`sample load <name>` accepts any string (passthrough — Slicer will 4xx if unknown).
"""

from __future__ import annotations

import typer

from slicer_cli.cli._internal.context import CliContext
from slicer_cli.cli.output import render_error, render_success
from slicer_cli.client.errors import SlicerError, exit_code_for

app = typer.Typer(no_args_is_help=True, help="Built-in sample datasets.")

# Curated subset of Slicer's built-in SampleData. Names verified against live
# Slicer 5.11.0 — `sample load X` for any of these returns 200. Slicer's actual
# catalogue is larger; pass an unknown name and Slicer returns 5xx with
# "sampledata X was not found", which the CLI surfaces as `E_HTTP_5XX`.
CURATED_SAMPLES: tuple[tuple[str, str], ...] = (
    ("MRHead", "T1-weighted MR head (Slicer's canonical example)"),
    ("MRBrainTumor1", "MR brain with tumor, baseline scan"),
    ("MRBrainTumor2", "MR brain with tumor, follow-up scan"),
    ("CTAAbdomenPanoramix", "CTA abdomen (Panoramix dataset)"),
)


@app.command("list")
def list_command(ctx: typer.Context) -> None:
    """List the curated sample datasets (offline; no Slicer call)."""
    cli_ctx: CliContext = ctx.obj
    payload = {
        "samples": [{"name": name, "description": desc} for name, desc in CURATED_SAMPLES],
    }
    render_success(payload, mode=cli_ctx.output_mode, renderer="samples")


@app.command("load")
def load_command(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Sample name (e.g. MRHead). See `sample list`."),
) -> None:
    """Tell Slicer to download/load a built-in SampleData set."""
    cli_ctx: CliContext = ctx.obj
    try:
        with cli_ctx.make_client() as client:
            response_text = client.load_sample(name)
    except SlicerError as error:
        render_error(error, mode=cli_ctx.output_mode)
        raise typer.Exit(code=exit_code_for(error.code)) from error

    render_success(
        {"name": name, "response": response_text},
        mode=cli_ctx.output_mode,
        renderer=None,
    )
