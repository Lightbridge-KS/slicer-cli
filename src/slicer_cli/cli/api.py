"""`slicer-cli api ...` — route table introspection + raw escape hatch.

Two commands here:

- `api routes` — pure offline command, reads the `client/routes.py` data file
  and prints the inventory. Useful for agents to discover the underlying HTTP
  surface without keeping a separate map.
- `api raw <method> <path>` — fires an arbitrary HTTP request to Slicer and
  surfaces the response. Destructive `(method, path)` pairs (per
  `client.routes.DESTRUCTIVE_RAW`) require `--confirm`.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated, Any

import typer

from slicer_cli.cli._internal.context import CliContext
from slicer_cli.cli._internal.safety import require_confirm
from slicer_cli.cli.output import render_error, render_meta_to_stderr, render_success
from slicer_cli.client.errors import SlicerBadInputError, SlicerError, exit_code_for
from slicer_cli.client.routes import DESTRUCTIVE_RAW, ROUTES

app = typer.Typer(no_args_is_help=True, help="Route inventory + raw escape hatch.")

_VALID_METHODS: frozenset[str] = frozenset({"GET", "POST", "PUT", "DELETE"})


@app.command("routes")
def routes_command(
    ctx: typer.Context,
    method: str | None = typer.Option(None, "--method", "-m", help="Filter by HTTP method."),
    destructive_only: bool = typer.Option(
        False, "--destructive", help="Show only destructive endpoints."
    ),
    phase: str | None = typer.Option(None, "--phase", help="Filter by phase tag, e.g. 'Phase 1'."),
) -> None:
    """List known Slicer endpoints (offline — reads package data)."""
    cli_ctx: CliContext = ctx.obj
    method_upper = method.upper() if method else None

    rows: list[dict[str, Any]] = []
    for r in ROUTES:
        if method_upper and r.method != method_upper:
            continue
        if destructive_only and not r.destructive:
            continue
        if phase and r.phase != phase:
            continue
        rows.append(
            {
                "method": r.method,
                "path": r.path,
                "purpose": r.purpose,
                "cli_command": r.cli_command,
                "destructive": r.destructive,
                "stub": r.stub,
                "phase": r.phase,
                "note": r.note,
            }
        )

    render_success({"routes": rows}, mode=cli_ctx.output_mode, renderer="routes")


@app.command("raw")
def raw_command(
    ctx: typer.Context,
    method: str = typer.Argument(..., help="HTTP method (GET/POST/PUT/DELETE)."),
    path: str = typer.Argument(..., help="Slicer-side path, e.g. /slicer/volumes."),
    query: Annotated[
        list[str] | None,
        typer.Option(
            "--query",
            "-q",
            help="Query param as KEY=VALUE; repeat for multiple.",
        ),
    ] = None,
    body: str | None = typer.Option(
        None,
        "--body",
        help="Request body. Use '@path' to read from a file; otherwise sent as-is.",
    ),
    out: str | None = typer.Option(
        None,
        "--out",
        help="Write response body to this path (or '-' for stdout). Required for non-JSON bodies.",
    ),
    confirm: bool = typer.Option(
        False,
        "--confirm",
        help="Required when (method, path) is destructive (per routes table).",
    ),
) -> None:
    """Issue an arbitrary HTTP call to Slicer.

    Destructive `(method, path)` pairs require `--confirm`. Non-JSON responses
    require `--out` (so binary doesn't garble the terminal).
    """
    cli_ctx: CliContext = ctx.obj
    method_upper = method.upper()

    try:
        if method_upper not in _VALID_METHODS:
            raise SlicerBadInputError(
                f"Unknown HTTP method: {method!r}",
                hint=f"Expected one of: {', '.join(sorted(_VALID_METHODS))}",
            )
        if (method_upper, path) in DESTRUCTIVE_RAW:
            require_confirm(confirm, f"raw {method_upper} {path}")

        params = _parse_query(query or [])
        body_bytes = _read_body(body) if body is not None else None

        with cli_ctx.make_client() as client:
            response = client.raw(method_upper, path, params=params, body=body_bytes)
    except SlicerError as error:
        render_error(error, mode=cli_ctx.output_mode)
        raise typer.Exit(code=exit_code_for(error.code)) from error

    content_type = response.headers.get("content-type", "")
    is_json = "json" in content_type.lower()

    if is_json:
        try:
            parsed = response.json()
        except ValueError:
            parsed = response.text
        payload: dict[str, Any] = {
            "method": method_upper,
            "path": path,
            "http_status": response.status_code,
            "response": parsed,
        }
        if out is not None:
            _write_bytes(out, response.content)
            payload["out"] = out
            payload["bytes"] = len(response.content)
        render_success(payload, mode=cli_ctx.output_mode, renderer=None)
        return

    # Non-JSON body — must have --out (binary or unstructured text).
    if out is None:
        try:
            raise SlicerBadInputError(
                f"Response is {content_type or 'non-JSON'}; --out is required to capture it.",
                hint="Pass --out <path> or --out - for stdout.",
            )
        except SlicerError as error:
            render_error(error, mode=cli_ctx.output_mode)
            raise typer.Exit(code=exit_code_for(error.code)) from error

    _write_bytes(out, response.content)
    meta = {
        "method": method_upper,
        "path": path,
        "http_status": response.status_code,
        "out": out,
        "bytes": len(response.content),
        "content_type": content_type,
    }
    if out == "-":
        render_meta_to_stderr(meta, mode=cli_ctx.output_mode)
    else:
        render_success(meta, mode=cli_ctx.output_mode, renderer=None)


# ----------------------------------------------------------------- helpers


def _parse_query(items: list[str]) -> dict[str, str] | None:
    """Parse `["key=value", ...]` into a dict; raises on malformed entries."""
    if not items:
        return None
    parsed: dict[str, str] = {}
    for entry in items:
        if "=" not in entry:
            raise SlicerBadInputError(
                f"--query must be KEY=VALUE, got {entry!r}",
            )
        key, _, value = entry.partition("=")
        if not key:
            raise SlicerBadInputError(f"--query missing key in {entry!r}")
        parsed[key] = value
    return parsed


def _read_body(spec: str) -> bytes:
    """`@path` reads bytes from a file; otherwise the literal is encoded as UTF-8."""
    if spec.startswith("@"):
        path = Path(spec[1:])
        if not path.is_file():
            raise SlicerBadInputError(
                f"--body @{path} does not point to a readable file",
            )
        return path.read_bytes()
    return spec.encode()


def _write_bytes(out: str, data: bytes) -> None:
    """`--out -` writes to stdout; otherwise to a file path."""
    if out == "-":
        sys.stdout.buffer.write(data)
        sys.stdout.buffer.flush()
        return
    Path(out).write_bytes(data)
