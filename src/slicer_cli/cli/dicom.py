"""`slicer-cli dicom ...` — QIDO + WADO-RS commands.

Phase 2 batch 2 lands the read side:
- `dicom studies / series / instances`  — QIDO listing
- `dicom instance ... --out`            — WADO-RS retrieve (raw DICOM bytes)
- `dicom meta`                          — variadic metadata dispatch

Phase 2 batch 3 will add `dicom pull`. The CLI surface stays flat — this
file just wires onto `DicomMixin` methods on `SlicerClient`.
"""

from __future__ import annotations

import sys
from pathlib import Path

import typer

from slicer_cli.cli._internal.context import CliContext
from slicer_cli.client.errors import SlicerError, exit_code_for
from slicer_cli.client.models import InstanceRef, SeriesRef, StudyRef
from slicer_cli.output import render_error, render_meta_to_stderr, render_success

app = typer.Typer(no_args_is_help=True, help="DICOMweb operations and Orthanc pull.")


@app.command("studies")
def studies_command(
    ctx: typer.Context,
    patient: str | None = typer.Option(None, "--patient", "-p", help="Filter by PatientID."),
    limit: int | None = typer.Option(None, "--limit", help="QIDO limit."),
    offset: int | None = typer.Option(None, "--offset", help="QIDO offset."),
) -> None:
    """List studies in Slicer's DICOM database (QIDO)."""
    cli_ctx: CliContext = ctx.obj
    try:
        with cli_ctx.make_client() as client:
            studies = client.list_studies(patient_id=patient, limit=limit, offset=offset)
    except SlicerError as error:
        render_error(error, mode=cli_ctx.output_mode)
        raise typer.Exit(code=exit_code_for(error.code)) from error

    payload = {"studies": [_study_payload(s) for s in studies]}
    render_success(payload, mode=cli_ctx.output_mode, renderer="studies")


@app.command("series")
def series_command(
    ctx: typer.Context,
    study_uid: str = typer.Argument(..., help="Study Instance UID."),
) -> None:
    """List series in a study (QIDO)."""
    cli_ctx: CliContext = ctx.obj
    try:
        with cli_ctx.make_client() as client:
            series = client.list_series(study_uid)
    except SlicerError as error:
        render_error(error, mode=cli_ctx.output_mode)
        raise typer.Exit(code=exit_code_for(error.code)) from error

    payload = {"series": [_series_payload(s) for s in series]}
    render_success(payload, mode=cli_ctx.output_mode, renderer="series")


@app.command("instances")
def instances_command(
    ctx: typer.Context,
    study_uid: str = typer.Argument(...),
    series_uid: str = typer.Argument(...),
) -> None:
    """List instances in a series (QIDO)."""
    cli_ctx: CliContext = ctx.obj
    try:
        with cli_ctx.make_client() as client:
            instances = client.list_instances(study_uid, series_uid)
    except SlicerError as error:
        render_error(error, mode=cli_ctx.output_mode)
        raise typer.Exit(code=exit_code_for(error.code)) from error

    payload = {"instances": [_instance_payload(i) for i in instances]}
    render_success(payload, mode=cli_ctx.output_mode, renderer="instances")


@app.command("instance")
def instance_command(
    ctx: typer.Context,
    study_uid: str = typer.Argument(...),
    series_uid: str = typer.Argument(...),
    sop_uid: str = typer.Argument(...),
    out: str = typer.Option(..., "--out", help="Output path or '-' for stdout."),
) -> None:
    """Retrieve raw DICOM bytes for one instance (WADO-RS)."""
    cli_ctx: CliContext = ctx.obj
    try:
        with cli_ctx.make_client() as client:
            data = client.download_instance(study_uid, series_uid, sop_uid)
    except SlicerError as error:
        render_error(error, mode=cli_ctx.output_mode)
        raise typer.Exit(code=exit_code_for(error.code)) from error

    meta: dict[str, object] = {
        "study_uid": study_uid,
        "series_uid": series_uid,
        "sop_uid": sop_uid,
        "format": "dicom",
    }
    if out == "-":
        sys.stdout.buffer.write(data)
        sys.stdout.buffer.flush()
        if cli_ctx.output_mode == "json":
            render_meta_to_stderr({"out": "-", "bytes": len(data), **meta}, mode="json")
        return
    path = Path(out)
    path.write_bytes(data)
    render_success(
        {"out": str(path), "bytes": len(data), **meta},
        mode=cli_ctx.output_mode,
        renderer=None,
    )


@app.command("meta")
def meta_command(
    ctx: typer.Context,
    study_uid: str = typer.Argument(..., help="Study Instance UID."),
    series_uid: str | None = typer.Argument(None, help="Optional Series Instance UID."),
    sop_uid: str | None = typer.Argument(None, help="Optional SOP Instance UID."),
) -> None:
    """Fetch DICOM metadata for a study, series, or instance (variadic dispatch).

    Pass UIDs hierarchically — series before sop. Skipping series while
    providing sop is rejected.
    """
    cli_ctx: CliContext = ctx.obj
    if sop_uid is not None and series_uid is None:
        from slicer_cli.client.errors import SlicerBadInputError

        error = SlicerBadInputError(
            "sop_uid was provided but series_uid was not",
            hint="Pass series before sop: `dicom meta <study> <series> <sop>`.",
        )
        render_error(error, mode=cli_ctx.output_mode)
        raise typer.Exit(code=exit_code_for(error.code))

    try:
        with cli_ctx.make_client() as client:
            if series_uid is None:
                meta = client.get_study_metadata(study_uid)
                level = "study"
            elif sop_uid is None:
                meta = client.get_series_metadata(study_uid, series_uid)
                level = "series"
            else:
                meta = client.get_instance_metadata(study_uid, series_uid, sop_uid)
                level = "instance"
    except SlicerError as error:
        render_error(error, mode=cli_ctx.output_mode)
        raise typer.Exit(code=exit_code_for(error.code)) from error

    render_success(
        {
            "level": level,
            "study_uid": study_uid,
            "series_uid": series_uid,
            "sop_uid": sop_uid,
            "meta": meta,
        },
        mode=cli_ctx.output_mode,
        renderer="dicom-meta",
    )


@app.command("pull")
def pull_command(
    ctx: typer.Context,
    orthanc: str = typer.Option(
        ..., "--orthanc", help="DICOMweb peer base URL (e.g., http://localhost:8042)."
    ),
    study: str = typer.Option(..., "--study", help="Study Instance UID to pull."),
    store: str = typer.Option(
        "dicom-web",
        "--store",
        help="DICOMweb store path appended to --orthanc (default 'dicom-web').",
    ),
    token: str = typer.Option("", "--token", help="Optional bearer token for the DICOMweb peer."),
) -> None:
    """Pull a study from a DICOMweb peer into Slicer's DICOM database.

    Routes through `/slicer/exec` (the native `/slicer/accessDICOMwebStudy`
    endpoint has a Slicer-side Python bug — see `api routes` for details).
    Requires `/slicer/exec` to be enabled on Slicer (the YOLO default; check
    via `slicer-cli doctor`).
    """
    cli_ctx: CliContext = ctx.obj
    try:
        with cli_ctx.make_client() as client:
            result = client.pull_from_dicomweb(
                prefix=orthanc,
                study_uid=study,
                store=store,
                access_token=token,
            )
    except SlicerError as error:
        render_error(error, mode=cli_ctx.output_mode)
        raise typer.Exit(code=exit_code_for(error.code)) from error

    payload = {
        "imported_count": result.get("imported_count"),
        "study_uid": result.get("study_uid", study),
        "endpoint": result.get("endpoint"),
        "raw": result,
    }
    render_success(payload, mode=cli_ctx.output_mode, renderer=None)


# --------------------------------------------------------------- payload helpers


def _study_payload(s: StudyRef) -> dict[str, object]:
    return {
        "study_uid": s.study_uid,
        "patient_id": s.patient_id,
        "patient_name": s.patient_name,
        "study_date": s.study_date,
        "study_description": s.study_description,
        "accession_number": s.accession_number,
        "modalities_in_study": s.modalities_in_study,
    }


def _series_payload(s: SeriesRef) -> dict[str, object]:
    return {
        "series_uid": s.series_uid,
        "study_uid": s.study_uid,
        "modality": s.modality,
        "series_number": s.series_number,
        "series_description": s.series_description,
    }


def _instance_payload(i: InstanceRef) -> dict[str, object]:
    return {
        "sop_uid": i.sop_uid,
        "series_uid": i.series_uid,
        "study_uid": i.study_uid,
        "instance_number": i.instance_number,
    }
