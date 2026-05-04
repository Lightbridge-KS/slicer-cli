"""Root Typer app — global flags, context plumbing, subcommand registration."""

from __future__ import annotations

import sys
from typing import Annotated

import typer

from slicer_cli import __version__
from slicer_cli.cli import (
    api as api_cli,
    config as config_cli,
    dicom as dicom_cli,
    doctor as doctor_cli,
    exec_ as exec_cli,
    gui as gui_cli,
    render as render_cli,
    status as status_cli,
    system as system_cli,
)
from slicer_cli.cli._internal.argv import hoist_global_flags
from slicer_cli.cli._internal.context import build_context
from slicer_cli.cli.mrml import (
    markup as markup_cli,
    node as node_cli,
    sample as sample_cli,
    scene as scene_cli,
    volume as volume_cli,
)
from slicer_cli.client.errors import SlicerError, exit_code_for
from slicer_cli.output import render_error

app = typer.Typer(
    name="slicer-cli",
    help="Agent-first CLI for 3D Slicer's HTTP server (port 2016 by default).",
    no_args_is_help=True,
    add_completion=False,
)

# Resource sub-apps (one per group from PRD §5.2). The user-facing surface is flat:
# `slicer-cli scene ...`, `slicer-cli volume ...` — the cli/mrml/ folder is just
# code organisation, not part of the command path.
app.add_typer(system_cli.app, name="system")
app.add_typer(scene_cli.app, name="scene")
app.add_typer(node_cli.app, name="node")
app.add_typer(volume_cli.app, name="volume")
app.add_typer(sample_cli.app, name="sample")
app.add_typer(render_cli.app, name="render")
app.add_typer(markup_cli.app, name="markup")
app.add_typer(dicom_cli.app, name="dicom")
app.add_typer(exec_cli.app, name="exec")
app.add_typer(gui_cli.app, name="gui")
app.add_typer(api_cli.app, name="api")
app.add_typer(config_cli.app, name="config")


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def root(
    ctx: typer.Context,
    url: Annotated[
        str | None,
        typer.Option("--url", help="Slicer base URL (default: http://127.0.0.1:2016)."),
    ] = None,
    json_mode: Annotated[
        bool,
        typer.Option("--json", help="Emit JSON envelope to stdout (agent-friendly)."),
    ] = False,
    pretty_mode: Annotated[
        bool,
        typer.Option("--pretty", help="Force pretty/TTY output (the default)."),
    ] = False,
    quiet: Annotated[
        bool,
        typer.Option("--quiet", help="Suppress non-error output (reserved; partial)."),
    ] = False,
    timeout: Annotated[
        float | None,
        typer.Option("--timeout", help="HTTP timeout in seconds (default: 30)."),
    ] = None,
    version_flag: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=_version_callback,
            is_eager=True,
            help="Show CLI version and exit.",
        ),
    ] = False,
) -> None:
    """Resolve config + output mode and stash them on the context."""
    _ = (quiet, version_flag)
    ctx.obj = build_context(
        url=url,
        json_mode=json_mode,
        pretty_mode=pretty_mode,
        timeout=timeout,
    )


# ---------- top-level commands (no subgroup needed)


@app.command("status")
def status(ctx: typer.Context) -> None:
    """Liveness probe + version (the 'is it on?' command)."""
    status_cli.status_command(ctx)


@app.command("doctor")
def doctor(ctx: typer.Context) -> None:
    """Run a battery of capability probes (Phase 1)."""
    doctor_cli.doctor_command(ctx)


def main() -> None:
    """Console-script entry point with top-level error mapping."""
    argv = hoist_global_flags(sys.argv[1:])
    try:
        app(args=argv, prog_name="slicer-cli")
    except SlicerError as error:
        # Defence in depth: any SlicerError that escaped a command handler.
        render_error(error, mode="pretty")
        sys.exit(exit_code_for(error.code))


if __name__ == "__main__":
    main()
