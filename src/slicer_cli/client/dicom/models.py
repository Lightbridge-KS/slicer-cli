"""Models for DICOMweb (QIDO + WADO-RS) responses.

Each model flattens the most-useful DICOM tags into Pythonic fields while
preserving the full DICOM JSON Model blob in `raw` — power-tool callers
can read `.raw["00100010"]` etc. for exotic tags.
"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from slicer_cli.client._internal.models_base import _SlicerModel


class StudyRef(_SlicerModel):
    """One row of QIDO `GET /dicom/studies` — common DICOM tags flattened."""

    study_uid: str
    patient_id: str | None = None
    patient_name: str | None = None
    study_date: str | None = None  # DICOM "YYYYMMDD"
    study_description: str | None = None
    accession_number: str | None = None
    modalities_in_study: list[str] = Field(default_factory=list)
    raw: dict[str, Any]


class SeriesRef(_SlicerModel):
    """One row of QIDO `GET /dicom/studies/{studyUID}/series`."""

    series_uid: str
    study_uid: str
    modality: str | None = None
    series_number: int | None = None
    series_description: str | None = None
    raw: dict[str, Any]


class InstanceRef(_SlicerModel):
    """One row of QIDO `GET /dicom/studies/.../series/.../instances`."""

    sop_uid: str
    series_uid: str
    study_uid: str
    instance_number: int | None = None
    raw: dict[str, Any]
