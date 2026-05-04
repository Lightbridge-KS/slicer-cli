"""Volume-specific endpoints — `/slicer/volume(s)`.

Note: volume *load* uses POST /slicer/mrml?filetype=VolumeFile, which lives
in `MrmlMixin.load_file` because the entry point is mrml-shaped. This file
covers only the dedicated volume endpoints.

Flat domain: the response model `Volume` is defined inline below.
"""

from __future__ import annotations

from slicer_cli.client._internal.http import _HttpClient
from slicer_cli.client._internal.models_base import _SlicerModel
from slicer_cli.client.errors import (
    SlicerBadInputError,
    SlicerBadResponseError,
)


class Volume(_SlicerModel):
    """Element of GET /slicer/volumes — confirmed live: `{name, id}` only.

    Note that Slicer does not return a `class` field on this endpoint; callers
    that need class info should derive it from `id` via `mrml.id_helpers.id_to_class`.
    """

    id: str
    name: str


class VolumeMixin(_HttpClient):
    """`/slicer/volumes` (list) and `/slicer/volume` (NRRD download)."""

    def list_volumes(self) -> list[Volume]:
        """GET /slicer/volumes → list[Volume].

        Live response shape is `[{name, id}, …]` — no class field. Callers that
        need class info should derive via `_id_helpers.id_to_class`.
        """
        endpoint = "/slicer/volumes"
        data = self._get_json(endpoint)
        if not isinstance(data, list):
            raise SlicerBadResponseError(
                f"Expected a JSON array from {endpoint}, got {type(data).__name__}",
                endpoint=endpoint,
            )
        return [self._validate(Volume, item, endpoint=endpoint) for item in data]

    def download_volume(self, node_id: str) -> bytes:
        """GET /slicer/volume?id=… → raw NRRD bytes (octet-stream).

        Returns the response body as bytes; the caller decides whether to write
        to disk or stream to stdout.
        """
        if not node_id.strip():
            raise SlicerBadInputError("node_id must not be empty")
        endpoint = "/slicer/volume"
        response = self._request("GET", endpoint, params={"id": node_id})
        return response.content
