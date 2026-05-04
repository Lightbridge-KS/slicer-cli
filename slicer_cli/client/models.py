"""Re-export shim — `from slicer_cli.client.models import …` keeps working.

Models now live next to their domain:

- Bundled domains own `models.py`:
  - `slicer_cli.client.mrml.models` → `NodeRef`, `LoadResult`, `DeleteResult`
  - `slicer_cli.client.dicom.models` → `StudyRef`, `SeriesRef`, `InstanceRef`
  - `slicer_cli.client.markup.models` → `FiducialNode`, `FiducialPoint`,
    `LineMarkupResult`, `MarkupRef`, `MarkupType`, `SegmentationNode`
- Flat domains define the model inline in the mixin file:
  - `slicer_cli.client.system` → `SystemVersion`
  - `slicer_cli.client.volume` → `Volume`

This shim exists so existing call sites (`from slicer_cli.client.models import
NodeRef`) keep working unchanged. New code is encouraged to import from the
domain module directly for clearer intent.
"""

from __future__ import annotations

from slicer_cli.client._internal.models_base import _SlicerModel
from slicer_cli.client.dicom.models import InstanceRef, SeriesRef, StudyRef
from slicer_cli.client.markup.models import (
    FiducialNode,
    FiducialPoint,
    LineMarkupResult,
    MarkupRef,
    MarkupType,
    SegmentationNode,
)
from slicer_cli.client.mrml.models import DeleteResult, LoadResult, NodeRef
from slicer_cli.client.system import SystemVersion
from slicer_cli.client.volume import Volume

__all__ = [
    "DeleteResult",
    "FiducialNode",
    "FiducialPoint",
    "InstanceRef",
    "LineMarkupResult",
    "LoadResult",
    "MarkupRef",
    "MarkupType",
    "NodeRef",
    "SegmentationNode",
    "SeriesRef",
    "StudyRef",
    "SystemVersion",
    "Volume",
    "_SlicerModel",
]
