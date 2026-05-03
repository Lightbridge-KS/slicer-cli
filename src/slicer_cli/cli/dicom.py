"""`slicer-cli dicom ...` — DICOMweb QIDO/WADO + Orthanc pull (Phase 2)."""

from __future__ import annotations

import typer

from slicer_cli.cli._internal.stub import stub

app = typer.Typer(no_args_is_help=True, help="DICOMweb operations and Orthanc pull.")


@app.command("studies")
def studies_command(ctx: typer.Context) -> None:
    """List DICOM studies in Slicer's local DB (Phase 2)."""
    stub(ctx, "dicom studies", phase="Phase 2")


@app.command("series")
def series_command(ctx: typer.Context) -> None:
    """List series for a study (Phase 2)."""
    stub(ctx, "dicom series", phase="Phase 2")


@app.command("instances")
def instances_command(ctx: typer.Context) -> None:
    """List instances for a series (Phase 2)."""
    stub(ctx, "dicom instances", phase="Phase 2")


@app.command("instance")
def instance_command(ctx: typer.Context) -> None:
    """WADO-RS retrieve a single instance (Phase 2)."""
    stub(ctx, "dicom instance", phase="Phase 2")


@app.command("meta")
def meta_command(ctx: typer.Context) -> None:
    """QIDO/WADO metadata for study/series/instance (Phase 2)."""
    stub(ctx, "dicom meta", phase="Phase 2")


@app.command("pull")
def pull_command(ctx: typer.Context) -> None:
    """Tell Slicer to pull a study from a DICOMweb server (Phase 2)."""
    stub(ctx, "dicom pull", phase="Phase 2")
