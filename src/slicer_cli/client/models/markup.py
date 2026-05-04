"""Models for markup-related responses (`/slicer/fiducials`, `/slicer/segmentations`,
templated `/slicer/exec` markup builders).

Both list endpoints return a dict keyed by node ID rather than a flat array;
we normalize to a flat list of refs in the mixin so callers iterate naturally.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from slicer_cli.client.models._base import _SlicerModel

MarkupType = Literal["fiducial", "segmentation", "line"]


class FiducialPoint(_SlicerModel):
    """One control point inside a `vtkMRMLMarkupsFiducialNode`."""

    label: str | None = None
    position: list[float] = Field(default_factory=list)  # [r, a, s] in mm
    visible: bool | None = None


class FiducialNode(_SlicerModel):
    """Element of `GET /slicer/fiducials`."""

    id: str  # MRML node id (the dict key in the raw response)
    name: str
    color: list[float] = Field(default_factory=list)  # RGB 0..1
    scale: float | None = None
    markups: list[FiducialPoint] = Field(default_factory=list)
    raw: dict[str, Any]


class SegmentationNode(_SlicerModel):
    """Element of `GET /slicer/segmentations`."""

    id: str
    name: str
    segment_ids: list[str] = Field(default_factory=list, alias="segmentIDs")
    raw: dict[str, Any]


class MarkupRef(_SlicerModel):
    """Unified row for the merged `markup list` view (no `--type` flag).

    `kind` is the discriminator. `extra` carries the type-specific summary
    (point count for fiducials, segment count for segmentations, length for
    lines) so the table renderer can show one useful field per row.
    """

    kind: MarkupType
    id: str
    name: str
    extra: dict[str, Any] = Field(default_factory=dict)


class LineMarkupResult(_SlicerModel):
    """Result of `markup line` (templated /slicer/exec)."""

    id: str
    length_mm: float | None = None
