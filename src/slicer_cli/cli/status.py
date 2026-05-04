"""`slicer-cli status` — liveness probe + version."""

from __future__ import annotations

import typer

from slicer_cli.cli._internal.context import CliContext
from slicer_cli.cli.output import render_error, render_success
from slicer_cli.client.errors import SlicerError, exit_code_for


def status_command(ctx: typer.Context) -> None:
    """Probe Slicer at the configured URL and report version."""
    cli_ctx: CliContext = ctx.obj
    try:
        with cli_ctx.make_client() as client:
            version = client.system_version()
    except SlicerError as error:
        render_error(error, mode=cli_ctx.output_mode)
        raise typer.Exit(code=exit_code_for(error.code)) from error

    render_success(
        {
            "url": cli_ctx.config.server.url,
            "applicationName": version.application_name,
            "applicationVersion": version.application_version,
            "releaseType": version.release_type,
            "arch": version.arch,
            "os": version.os,
        },
        mode=cli_ctx.output_mode,
        renderer="status",
    )
