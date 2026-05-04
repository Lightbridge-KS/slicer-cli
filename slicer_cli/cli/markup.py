"""`slicer-cli markup ...` — fiducials, lines, segmentations.

Surface:
- `markup list [--type fiducial|segmentation]`  default: merged view of both
- `markup fiducial-set --id ID --index N --r R --a A --s S`
- `markup line --p1 R,A,S --p2 R,A,S [--name N]`  (templated /exec; audited)
"""

from __future__ import annotations

from typing import Any

import typer

from slicer_cli.cli._internal.context import CliContext
from slicer_cli.cli.output import render_error, render_success
from slicer_cli.client.errors import SlicerBadInputError, SlicerError, exit_code_for
from slicer_cli.client.models import (
    FiducialNode,
    MarkupRef,
    SegmentationNode,
)

app = typer.Typer(no_args_is_help=True, help="Markup operations (fiducials, segmentations, lines).")


@app.command("list")
def list_command(
    ctx: typer.Context,
    type_: str | None = typer.Option(
        None, "--type", "-t", help="Filter by markup type: fiducial | segmentation."
    ),
) -> None:
    """List markup nodes. With no `--type`, returns merged fiducials + segmentations."""
    cli_ctx: CliContext = ctx.obj
    try:
        with cli_ctx.make_client() as client:
            if type_ is None:
                rows = client.list_all_markup()
                payload = {"markups": [_ref_payload(r) for r in rows]}
            elif type_ == "fiducial":
                fids = client.list_fiducials()
                payload = {"markups": [_fiducial_payload(f) for f in fids]}
            elif type_ == "segmentation":
                segs = client.list_segmentations()
                payload = {"markups": [_segmentation_payload(s) for s in segs]}
            else:
                raise SlicerBadInputError(
                    f"Unknown markup type: {type_!r}",
                    hint="Use --type fiducial or --type segmentation, or omit for both.",
                )
    except SlicerError as error:
        render_error(error, mode=cli_ctx.output_mode)
        raise typer.Exit(code=exit_code_for(error.code)) from error

    render_success(payload, mode=cli_ctx.output_mode, renderer="markup-list")


@app.command("fiducial-set")
def fiducial_set_command(
    ctx: typer.Context,
    node_id: str = typer.Option(..., "--id", help="Fiducial MRML node id."),
    index: int = typer.Option(..., "--index", "-n", help="Control point index (0-based)."),
    r: float = typer.Option(..., "--r", help="R coordinate (mm)."),
    a: float = typer.Option(..., "--a", help="A coordinate (mm)."),
    s: float = typer.Option(..., "--s", help="S coordinate (mm)."),
) -> None:
    """Set the position of one fiducial control point."""
    cli_ctx: CliContext = ctx.obj
    try:
        with cli_ctx.make_client() as client:
            result = client.set_fiducial_position(node_id=node_id, index=index, r=r, a=a, s=s)
    except SlicerError as error:
        render_error(error, mode=cli_ctx.output_mode)
        raise typer.Exit(code=exit_code_for(error.code)) from error

    render_success(
        {"id": node_id, "index": index, "position": [r, a, s], "result": result},
        mode=cli_ctx.output_mode,
        renderer=None,
    )


@app.command("line")
def line_command(
    ctx: typer.Context,
    p1: str = typer.Option(..., "--p1", help="First endpoint as 'R,A,S' (mm)."),
    p2: str = typer.Option(..., "--p2", help="Second endpoint as 'R,A,S' (mm)."),
    name: str = typer.Option("AgentLine_1", "--name", help="MRML node name."),
) -> None:
    """Create a line markup between two RAS points (templated /exec, audited)."""
    cli_ctx: CliContext = ctx.obj
    try:
        point1 = _parse_ras(p1, flag="--p1")
        point2 = _parse_ras(p2, flag="--p2")
        with cli_ctx.make_client() as client:
            result = client.add_line(p1=point1, p2=point2, name=name)
    except SlicerError as error:
        render_error(error, mode=cli_ctx.output_mode)
        raise typer.Exit(code=exit_code_for(error.code)) from error

    render_success(
        {
            "id": result.id,
            "length_mm": result.length_mm,
            "name": name,
            "p1": list(point1),
            "p2": list(point2),
        },
        mode=cli_ctx.output_mode,
        renderer=None,
    )


# --------------------------------------------------------------- payload + parsing helpers


def _parse_ras(value: str, *, flag: str) -> tuple[float, float, float]:
    parts = [p.strip() for p in value.split(",")]
    if len(parts) != 3:
        raise SlicerBadInputError(
            f"{flag} must be 'R,A,S' (three comma-separated numbers); got {value!r}",
        )
    try:
        return (float(parts[0]), float(parts[1]), float(parts[2]))
    except ValueError as exc:
        raise SlicerBadInputError(
            f"{flag} components must be numbers; got {value!r}",
        ) from exc


def _ref_payload(r: MarkupRef) -> dict[str, Any]:
    return {"kind": r.kind, "id": r.id, "name": r.name, "extra": r.extra}


def _fiducial_payload(f: FiducialNode) -> dict[str, Any]:
    return {
        "kind": "fiducial",
        "id": f.id,
        "name": f.name,
        "scale": f.scale,
        "color": f.color,
        "point_count": len(f.markups),
        "points": [
            {"label": p.label, "position": p.position, "visible": p.visible} for p in f.markups
        ],
    }


def _segmentation_payload(s: SegmentationNode) -> dict[str, Any]:
    return {
        "kind": "segmentation",
        "id": s.id,
        "name": s.name,
        "segment_count": len(s.segment_ids),
        "segment_ids": s.segment_ids,
    }
