"""`slicer-cli exec` — run Python in Slicer's interpreter (gated + audited).

Surface:
- `exec --code 'print("hi"); __execResult = 1'`
- `exec --file path/to/script.py`
- `--no-audit-log`            skip writing to ~/.local/state/slicer-cli/exec.log
                              (emits a stderr warning)
- `--i-understand-the-risk`   required if `config.exec.enabled = false`

The remote source MUST set `__execResult` to a JSON-serializable value;
Slicer returns that as the response body. The audit-log writer
(`client._internal.audit.AuditLogger`) records every invocation; see that
module for the line format.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from slicer_cli.cli._internal.context import CliContext
from slicer_cli.cli._internal.safety import require_exec_enabled
from slicer_cli.cli.output import render_error, render_success, render_warning
from slicer_cli.client.errors import SlicerBadInputError, SlicerError, exit_code_for

app = typer.Typer(
    no_args_is_help=False,
    help="Run Python in Slicer's interpreter (gated by config.exec.enabled).",
)


@app.callback(invoke_without_command=True)
def exec_command(
    ctx: typer.Context,
    code: Annotated[
        str | None,
        typer.Option("--code", "-c", help="Python source string."),
    ] = None,
    file: Annotated[
        Path | None,
        typer.Option(
            "--file",
            "-f",
            help="Path to a .py file whose contents will be POSTed to /slicer/exec.",
        ),
    ] = None,
    no_audit_log: Annotated[
        bool,
        typer.Option(
            "--no-audit-log",
            help="Skip writing the audit log line. Emits a stderr warning.",
        ),
    ] = False,
    override: Annotated[
        bool,
        typer.Option(
            "--i-understand-the-risk",
            help="Required when config.exec.enabled is false.",
        ),
    ] = False,
) -> None:
    """POST /slicer/exec — gated, audited remote-Python."""
    if ctx.invoked_subcommand is not None:
        return  # subcommand will handle (none currently registered)
    cli_ctx: CliContext = ctx.obj

    try:
        # XOR validation: exactly one of --code or --file required.
        if (code is None) == (file is None):
            raise SlicerBadInputError(
                "supply exactly one of --code or --file",
                hint="`--code 'print(1)'` or `--file path/to/script.py`",
            )

        require_exec_enabled(cli_ctx.config.exec, override=override)

        source = code if code is not None else _read_source_file(file)

        if no_audit_log:
            render_warning("audit log skipped (--no-audit-log)", mode=cli_ctx.output_mode)
        with cli_ctx.make_client(disable_audit=no_audit_log) as client:
            result = client.run_python(source, op_label="cli.exec")
    except SlicerError as error:
        render_error(error, mode=cli_ctx.output_mode)
        raise typer.Exit(code=exit_code_for(error.code)) from error

    payload: dict[str, object] = {"result": result}
    render_success(payload, mode=cli_ctx.output_mode, renderer="exec-result")


def _read_source_file(path: Path | None) -> str:
    """Read the script file or raise a clean E_BAD_INPUT error."""
    assert path is not None  # guarded by XOR check above
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SlicerBadInputError(
            f"Could not read --file {path}: {exc}",
            hint="Check the path exists and is readable.",
        ) from exc
