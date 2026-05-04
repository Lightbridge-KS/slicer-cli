"""`slicer-cli config ...` — show / get / path."""

from __future__ import annotations

import json

import typer

from slicer_cli.cli._internal.context import CliContext
from slicer_cli.cli.output import render_error, render_success
from slicer_cli.client.errors import SlicerBadInputError, exit_code_for
from slicer_cli.config import USER_CONFIG_PATH, config_paths

app = typer.Typer(no_args_is_help=True, help="Inspect merged configuration.")


@app.command("show")
def show_command(ctx: typer.Context) -> None:
    """Print the merged config (after layering env, project, user, defaults)."""
    cli_ctx: CliContext = ctx.obj
    render_success(
        {"config": cli_ctx.config.model_dump()},
        mode=cli_ctx.output_mode,
        renderer=None,
    )


@app.command("get")
def get_command(
    ctx: typer.Context,
    key: str = typer.Argument(..., help="Dotted key, e.g. server.url or exec.enabled"),
) -> None:
    """Print a single config value by dotted key."""
    cli_ctx: CliContext = ctx.obj
    raw = cli_ctx.config.model_dump()
    parts = key.split(".")
    cursor: object = raw
    try:
        for part in parts:
            if not isinstance(cursor, dict) or part not in cursor:
                raise KeyError(part)
            cursor = cursor[part]
    except KeyError as missing:
        error = SlicerBadInputError(
            f"Unknown config key: {key}",
            hint=f"Section or field {missing.args[0]!r} does not exist.",
        )
        render_error(error, mode=cli_ctx.output_mode)
        raise typer.Exit(code=exit_code_for(error.code)) from missing

    if cli_ctx.output_mode == "json":
        render_success({"key": key, "value": cursor}, mode="json")
    else:
        # Print just the value to stdout for shell-friendly piping.
        typer.echo(json.dumps(cursor) if not isinstance(cursor, str) else cursor)


@app.command("path")
def path_command(ctx: typer.Context) -> None:
    """Show which config files were considered and whether they exist."""
    cli_ctx: CliContext = ctx.obj
    paths = config_paths()
    payload = {
        "user_config_path": str(USER_CONFIG_PATH),
        "user_config_exists": paths["user_exists"] == "True",
        "project_config_path": paths["project"],
        "project_config_exists": paths["project_exists"] == "True",
    }
    render_success(payload, mode=cli_ctx.output_mode, renderer=None)
