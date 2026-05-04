"""DICOMweb domain — QIDO + WADO-RS wrappers + DICOM JSON tag helpers.

Public re-exports: callers should `from slicer_cli.client.dicom import ...`
unchanged from before the bundling. Tag helpers and constants live in
`tags.py` (formerly `client/_internal/dicom_tags.py`).
"""

from __future__ import annotations

from slicer_cli.client.dicom.mixin import DicomMixin
from slicer_cli.client.dicom.models import InstanceRef, SeriesRef, StudyRef

__all__ = ["DicomMixin", "InstanceRef", "SeriesRef", "StudyRef"]
