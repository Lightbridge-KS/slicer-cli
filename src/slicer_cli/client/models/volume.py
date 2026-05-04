"""Models for `/slicer/volume(s)` responses."""

from __future__ import annotations

from slicer_cli.client.models._base import _SlicerModel


class Volume(_SlicerModel):
    """Element of GET /slicer/volumes — confirmed live: `{name, id}` only.

    Note that Slicer does not return a `class` field on this endpoint; callers
    that need class info should derive it from `id` via
    `client._internal.id_helpers.id_to_class`.
    """

    id: str
    name: str
