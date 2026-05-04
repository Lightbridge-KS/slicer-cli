"""GUI endpoints — `PUT /slicer/gui` for layout + chrome control.

Slicer 5.x layout names are version-dependent (`fourup`, `oneup3d`,
`conventionalwidescreen`, etc.). We pass-through the `layout` string
unchanged rather than encoding a Slicer-version map at the client.
"""

from __future__ import annotations

from typing import Any

from slicer_cli.client._internal.http import _HttpClient
from slicer_cli.client.errors import SlicerBadInputError, SlicerBadResponseError


class GuiMixin(_HttpClient):
    """`/slicer/gui` operations."""

    def set_layout(self, *, layout: str, contents: str = "full") -> dict[str, Any]:
        """PUT /slicer/gui?contents={contents}&viewersLayout={layout}.

        `contents` ∈ {"full", "viewers"}; "viewers" hides the GUI chrome and
        shows only the slice/3D viewers. `layout` is pass-through (Slicer
        decides what's valid for its build).
        """
        cleaned_layout = (layout or "").strip()
        if not cleaned_layout:
            raise SlicerBadInputError("layout must not be empty")
        if contents not in {"full", "viewers"}:
            raise SlicerBadInputError(
                f"contents must be 'full' or 'viewers'; got {contents!r}",
            )
        endpoint = "/slicer/gui"
        params = {"contents": contents, "viewersLayout": cleaned_layout}
        response = self._request("PUT", endpoint, params=params)
        data = self._parse_json(response, endpoint=endpoint)
        if not isinstance(data, dict):
            raise SlicerBadResponseError(
                f"Expected JSON object from {endpoint}, got {type(data).__name__}",
                endpoint=endpoint,
            )
        return data
