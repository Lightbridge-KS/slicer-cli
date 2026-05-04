"""Models for `/slicer/mrml*` responses."""

from __future__ import annotations

from pydantic import Field

from slicer_cli.client._internal.models_base import _SlicerModel


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
