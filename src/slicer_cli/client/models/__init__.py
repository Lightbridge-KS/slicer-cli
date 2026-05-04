"""Pydantic response models, split per Slicer URL family.

Public re-exports — callers should `from slicer_cli.client.models import ...`
exactly as before. The per-domain split is an implementation detail.

All models inherit `_SlicerModel` which sets
`extra="ignore", frozen=True, populate_by_name=True` — schema drift is a
documented risk (PRD §14.1 R1).
"""

from __future__ import annotations

from slicer_cli.client.models._base import _SlicerModel
from slicer_cli.client.models.dicom import InstanceRef, SeriesRef, StudyRef
from slicer_cli.client.models.mrml import DeleteResult, LoadResult, NodeRef
from slicer_cli.client.models.system import SystemVersion
from slicer_cli.client.models.volume import Volume

__all__ = [
    "DeleteResult",
    "InstanceRef",
    "LoadResult",
    "NodeRef",
    "SeriesRef",
    "StudyRef",
    "SystemVersion",
    "Volume",
    "_SlicerModel",
]
