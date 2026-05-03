"""Pydantic response models.

Shapes are derived from the surface report (`docs/3d-slicer-webserver-surface-report.md`)
and verified against live Slicer where possible. All models inherit `_SlicerModel` which
tolerates unknown fields — schema drift is a documented risk (PRD §14.1 R1).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class _SlicerModel(BaseModel):
    """Base for all Slicer response models — tolerant of unknown fields."""

    model_config = ConfigDict(extra="ignore", frozen=True, populate_by_name=True)


class SystemVersion(_SlicerModel):
    """Response of GET /slicer/system/version (PRD Appendix A)."""

    application_name: str = Field(alias="applicationName")
    application_version: str = Field(alias="applicationVersion")
    application_display_name: str | None = Field(default=None, alias="applicationDisplayName")
    release_type: str | None = Field(default=None, alias="releaseType")
    revision: str | None = None
    arch: str | None = None
    os: str | None = None
    major_version: int | None = Field(default=None, alias="majorVersion")
    minor_version: int | None = Field(default=None, alias="minorVersion")


class Volume(_SlicerModel):
    """Element of GET /slicer/volumes — confirmed live: `{name, id}` only.

    Note that Slicer does not return a `class` field on this endpoint; callers
    that need class info should derive it from `id` via `mrml._helpers.id_to_class`.
    """

    id: str
    name: str


class NodeRef(_SlicerModel):
    """A minimal MRML node reference. `class_` is optional because most
    listing endpoints don't return it directly — we derive it from `id`."""

    id: str
    name: str
    class_: str | None = Field(default=None, alias="class")


class LoadResult(_SlicerModel):
    """Response of POST /slicer/mrml — file load returning the new node IDs."""

    success: bool
    loaded_node_ids: list[str] = Field(default_factory=list, alias="loadedNodeIDs")


class DeleteResult(_SlicerModel):
    """Response of DELETE /slicer/mrml (and friends)."""

    success: bool
