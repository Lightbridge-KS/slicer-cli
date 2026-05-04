"""Markup endpoints — `/slicer/fiducials`, `/slicer/fiducial`, `/slicer/segmentations`,
plus templated `/slicer/exec` for line markups (no native endpoint per surface §6.5).

Both list endpoints return a dict keyed by node ID rather than a flat array,
so the mixin normalizes them to `list[FiducialNode]` / `list[SegmentationNode]`
for ergonomic iteration. The merged `list_all_markup` runs both GETs serially
(Slicer's WebServer is single-threaded so concurrency wouldn't help anyway).
"""

from __future__ import annotations

from typing import Any

from slicer_cli.client._internal.exec import build_exec_payload
from slicer_cli.client._internal.http import _HttpClient
from slicer_cli.client.errors import SlicerBadInputError, SlicerBadResponseError
from slicer_cli.client.models import (
    FiducialNode,
    FiducialPoint,
    LineMarkupResult,
    MarkupRef,
    SegmentationNode,
)


class MarkupMixin(_HttpClient):
    """Markup operations — fiducials, segmentations, line builder via /exec."""

    # ------------------------------------------------------------- listing

    def list_fiducials(self) -> list[FiducialNode]:
        """GET /slicer/fiducials → list[FiducialNode]. Empty list when no markups exist."""
        endpoint = "/slicer/fiducials"
        data = self._get_json(endpoint)
        return [
            _fiducial_from_blob(node_id, blob)
            for node_id, blob in _normalize_dict(data, endpoint).items()
        ]

    def list_segmentations(self) -> list[SegmentationNode]:
        """GET /slicer/segmentations → list[SegmentationNode]."""
        endpoint = "/slicer/segmentations"
        data = self._get_json(endpoint)
        return [
            _segmentation_from_blob(node_id, blob)
            for node_id, blob in _normalize_dict(data, endpoint).items()
        ]

    def list_all_markup(self) -> list[MarkupRef]:
        """Convenience: fiducials + segmentations merged into one flat list."""
        out: list[MarkupRef] = []
        for f in self.list_fiducials():
            out.append(
                MarkupRef(
                    kind="fiducial",
                    id=f.id,
                    name=f.name,
                    extra={"point_count": len(f.markups)},
                )
            )
        for s in self.list_segmentations():
            out.append(
                MarkupRef(
                    kind="segmentation",
                    id=s.id,
                    name=s.name,
                    extra={"segment_count": len(s.segment_ids)},
                )
            )
        return out

    # ------------------------------------------------------------- mutate

    def set_fiducial_position(
        self,
        *,
        node_id: str,
        index: int,
        r: float,
        a: float,
        s: float,
    ) -> dict[str, Any]:
        """PUT /slicer/fiducial?id=...&index=...&r=...&a=...&s=...

        Refuses an empty `node_id` at the client layer (defense-in-depth).
        """
        cleaned = (node_id or "").strip()
        if not cleaned:
            raise SlicerBadInputError("node_id must not be empty")
        if index < 0:
            raise SlicerBadInputError(f"index must be >= 0, got {index}")

        endpoint = "/slicer/fiducial"
        params = {
            "id": cleaned,
            "index": str(index),
            "r": f"{r:g}",
            "a": f"{a:g}",
            "s": f"{s:g}",
        }
        response = self._request("PUT", endpoint, params=params)
        data = self._parse_json(response, endpoint=endpoint)
        if not isinstance(data, dict):
            raise SlicerBadResponseError(
                f"Expected JSON object from {endpoint}, got {type(data).__name__}",
                endpoint=endpoint,
            )
        return data

    def add_line(
        self,
        *,
        p1: tuple[float, float, float],
        p2: tuple[float, float, float],
        name: str = "AgentLine_1",
    ) -> LineMarkupResult:
        """Create a `vtkMRMLMarkupsLineNode` between two RAS points via templated /exec.

        Lines have no native HTTP endpoint (surface report §6.5). The templated
        body adds a node with two control points and reads back its world-space
        length. Routes through `_post_exec` so each call writes one audit-log
        entry per PRD §8.3.
        """
        cleaned_name = (name or "").strip()
        if not cleaned_name:
            raise SlicerBadInputError("name must not be empty")
        template = (
            "import slicer\n"
            "node = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLMarkupsLineNode', {name})\n"
            "node.AddControlPoint([{r1}, {a1}, {s1}])\n"
            "node.AddControlPoint([{r2}, {a2}, {s2}])\n"
            "__execResult = {{\n"
            "    'id': node.GetID(),\n"
            "    'length_mm': float(node.GetLineLengthWorld()),\n"
            "}}\n"
        )
        body = build_exec_payload(
            template,
            name=cleaned_name,
            r1=p1[0],
            a1=p1[1],
            s1=p1[2],
            r2=p2[0],
            a2=p2[1],
            s2=p2[2],
        )
        response = self._post_exec(body, op_label="markup.add_line")
        endpoint = "/slicer/exec"
        data = self._parse_json(response, endpoint=endpoint)
        if not isinstance(data, dict):
            raise SlicerBadResponseError(
                f"Expected JSON object from {endpoint}, got {type(data).__name__}",
                endpoint=endpoint,
            )
        return self._validate(LineMarkupResult, data, endpoint=endpoint)


# --------------------------------------------------------------- helpers


def _normalize_dict(data: Any, endpoint: str) -> dict[str, dict[str, Any]]:
    """Both list endpoints return `{node_id: blob}`; reject anything else early."""
    if not isinstance(data, dict):
        raise SlicerBadResponseError(
            f"Expected JSON object from {endpoint}, got {type(data).__name__}",
            endpoint=endpoint,
        )
    out: dict[str, dict[str, Any]] = {}
    for key, value in data.items():
        if not isinstance(value, dict):
            raise SlicerBadResponseError(
                f"Expected dict per node from {endpoint}, got {type(value).__name__}",
                endpoint=endpoint,
            )
        out[str(key)] = value
    return out


def _fiducial_from_blob(node_id: str, blob: dict[str, Any]) -> FiducialNode:
    raw_markups = blob.get("markups", [])
    if not isinstance(raw_markups, list):
        raw_markups = []
    points: list[FiducialPoint] = []
    for entry in raw_markups:
        if not isinstance(entry, dict):
            continue
        position = entry.get("position", [])
        if not isinstance(position, list):
            position = []
        points.append(
            FiducialPoint(
                label=entry.get("label"),
                position=[float(x) for x in position if isinstance(x, (int, float))],
                visible=entry.get("visible"),
            )
        )
    color = blob.get("color", [])
    if not isinstance(color, list):
        color = []
    return FiducialNode(
        id=node_id,
        name=str(blob.get("name", "")),
        color=[float(c) for c in color if isinstance(c, (int, float))],
        scale=_coerce_float_or_none(blob.get("scale")),
        markups=points,
        raw=blob,
    )


def _segmentation_from_blob(node_id: str, blob: dict[str, Any]) -> SegmentationNode:
    raw_ids = blob.get("segmentIDs", blob.get("segment_ids", []))
    if not isinstance(raw_ids, list):
        raw_ids = []
    return SegmentationNode(
        id=node_id,
        name=str(blob.get("name", "")),
        segmentIDs=[str(s) for s in raw_ids],
        raw=blob,
    )


def _coerce_float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None
