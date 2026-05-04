"""Render endpoints — `/slicer/screenshot|slice|threeD|threeDGraphics`.

All four endpoints return binary content. PNG-shaped responses go through
`validate_png` (magic + size + IHDR dims); glTF goes through
`validate_binary` because Slicer may return either binary `.glb` or JSON
`.gltf` (verified live: this build returns JSON glTF at ~10 KB).
"""

from __future__ import annotations

from typing import Any

from slicer_cli.client._internal.http import _HttpClient
from slicer_cli.client._internal.validators import validate_binary, validate_png

_VALID_VIEWS: frozenset[str] = frozenset({"red", "yellow", "green"})
_VALID_ORIENTATIONS: frozenset[str] = frozenset({"axial", "sagittal", "coronal"})
_VALID_LOOK_AXES: frozenset[str] = frozenset({"L", "R", "A", "P", "I", "S"})


class RenderMixin(_HttpClient):
    """Render slice / 3D / screenshot / glTF endpoints."""

    def render_slice(
        self,
        *,
        view: str = "red",
        orientation: str | None = None,
        offset: float | None = None,
        scroll_to: float | None = None,
        size: int | None = None,
        copy_geometry_from: str | None = None,
    ) -> bytes:
        """GET /slicer/slice → validated PNG bytes.

        Query params (all optional except `view` which defaults to `red`):
          - `view`: red | yellow | green (which slice viewer)
          - `orientation`: axial | sagittal | coronal
          - `offset`: slice offset in millimetres
          - `scroll_to`: 0..1 normalized scroll position
          - `size`: render size in pixels (Slicer caps it to viewer size)
          - `copy_geometry_from`: another view id to mirror geometry from
        """
        from slicer_cli.client.errors import SlicerBadInputError

        if view not in _VALID_VIEWS:
            raise SlicerBadInputError(
                f"view={view!r} is not valid",
                hint=f"Expected one of: {', '.join(sorted(_VALID_VIEWS))}",
            )
        if orientation is not None and orientation not in _VALID_ORIENTATIONS:
            raise SlicerBadInputError(
                f"orientation={orientation!r} is not valid",
                hint=f"Expected one of: {', '.join(sorted(_VALID_ORIENTATIONS))}",
            )

        params: dict[str, Any] = {"view": view}
        if orientation is not None:
            params["orientation"] = orientation
        if offset is not None:
            params["offset"] = str(offset)
        if scroll_to is not None:
            params["scrollTo"] = str(scroll_to)
        if size is not None:
            params["size"] = str(size)
        if copy_geometry_from is not None:
            params["copySliceGeometryFrom"] = copy_geometry_from

        endpoint = "/slicer/slice"
        response = self._request("GET", endpoint, params=params)
        return validate_png(response.content, endpoint=endpoint)

    def render_threed(self, *, look_from_axis: str | None = None) -> bytes:
        """GET /slicer/threeD → validated PNG bytes.

        `look_from_axis`: one of L, R, A, P, I, S (left/right/anterior/posterior/inferior/superior).
        """
        from slicer_cli.client.errors import SlicerBadInputError

        if look_from_axis is not None and look_from_axis not in _VALID_LOOK_AXES:
            raise SlicerBadInputError(
                f"look_from_axis={look_from_axis!r} is not valid",
                hint=f"Expected one of: {', '.join(sorted(_VALID_LOOK_AXES))}",
            )
        params: dict[str, Any] = {}
        if look_from_axis is not None:
            params["lookFromAxis"] = look_from_axis

        endpoint = "/slicer/threeD"
        response = self._request("GET", endpoint, params=params or None)
        return validate_png(response.content, endpoint=endpoint)

    def screenshot(self) -> bytes:
        """GET /slicer/screenshot → validated PNG bytes.

        Requires Slicer's main window to be alive (i.e., not strict-headless).
        Slicer calls `slicer.util.mainWindow().grab()` internally.
        """
        endpoint = "/slicer/screenshot"
        response = self._request("GET", endpoint)
        return validate_png(response.content, endpoint=endpoint)

    def render_gltf(self, *, widget_index: int = 0, box_visible: bool = False) -> bytes:
        """GET /slicer/threeDGraphics → glTF bytes.

        Slicer may return JSON glTF (`application/json`) or binary `.glb` —
        we don't gate on magic bytes, only on a >= 1024 byte size threshold.
        """
        params: dict[str, Any] = {
            "widgetIndex": str(widget_index),
            "boxVisible": "true" if box_visible else "false",
        }
        endpoint = "/slicer/threeDGraphics"
        response = self._request("GET", endpoint, params=params)
        return validate_binary(response.content, endpoint=endpoint, min_bytes=1024)
