"""Route inventory for 3D Slicer's HTTP server.

This is a *data file*. The CLI's `api routes` command reads it for offline
introspection; `api raw` reads it to enforce destructive guards on matching
`(method, path)` pairs.

Schema:
- `method`        : HTTP verb the endpoint expects ("GET", "POST", "PUT", "DELETE").
- `path`          : Slicer-side URL path, no leading host.
- `purpose`       : one-line description for `api routes` output.
- `cli_command`   : equivalent slicer-cli command, or None if no wrapper.
- `destructive`   : True if calling this is destructive (clears scene, shuts down,
                    runs arbitrary code, deletes a node). Used by `api raw` guards.
- `stub`          : True if Slicer's handler is known to be a stub / NotImplemented
                    upstream. CLI surfaces E_NOT_IMPLEMENTED proactively for these.
- `phase`         : Capability tag that wraps it (see Batch 3 — to become semantic
                    `category` like "mrml", "render", "dicom"), or None for
                    endpoints we don't wrap (escape-hatch only via `api raw`).
- `note`          : Optional caveat — Slicer-side bugs, workarounds, or pointers
                    to the right CLI command when the route shouldn't be called
                    directly.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Route:
    method: str
    path: str
    purpose: str
    cli_command: str | None
    destructive: bool
    stub: bool
    phase: str | None
    note: str | None = None


# --------------------------------------------------------------------- /slicer/*

_SYSTEM: tuple[Route, ...] = (
    Route(
        "GET",
        "/slicer/system/version",
        "App identity + version",
        "status / system version",
        False,
        False,
        "Phase 0",
    ),
    Route(
        "DELETE",
        "/slicer/system",
        "Quit application (1 s deferred)",
        "system shutdown --confirm",
        True,
        False,
        "Phase 1",
    ),
)

_MRML: tuple[Route, ...] = (
    Route(
        "GET",
        "/slicer/mrml/names",
        "List names of selected MRML nodes",
        "scene nodes / scene ids",
        False,
        False,
        "Phase 1",
    ),
    Route(
        "GET",
        "/slicer/mrml/ids",
        "List ids of selected MRML nodes",
        "scene ids",
        False,
        False,
        "Phase 1",
    ),
    Route(
        "GET",
        "/slicer/mrml/properties",
        "Full property dict of selected nodes",
        "node show",
        False,
        False,
        "Phase 1",
    ),
    Route(
        "GET",
        "/slicer/mrml/file",
        "Save selected node to server-side file",
        "node export (via volume export) / scene save",
        False,
        False,
        "Phase 1",
    ),
    Route(
        "POST",
        "/slicer/mrml",
        "Load file/url as typed node",
        "volume import / scene load",
        False,
        False,
        "Phase 1",
    ),
    Route(
        "PUT",
        "/slicer/mrml",
        "Reload selected nodes from original",
        "node reload",
        False,
        False,
        "Phase 1",
    ),
    Route(
        "DELETE",
        "/slicer/mrml",
        "Delete selected nodes (empty = clear scene!)",
        "node delete / scene clear --confirm",
        True,
        False,
        "Phase 1",
    ),
)

_DATA: tuple[Route, ...] = (
    Route(
        "GET",
        "/slicer/sampledata",
        "Download/load a built-in SampleData set",
        "sample load",
        False,
        False,
        "Phase 1",
    ),
    Route(
        "GET",
        "/slicer/volumes",
        "List scalar + labelmap volumes",
        "volume list",
        False,
        False,
        "Phase 1",
    ),
    Route(
        "GET",
        "/slicer/volume",
        "Stream a volume as NRRD bytes",
        "volume export",
        False,
        False,
        "Phase 1",
    ),
    Route(
        "POST", "/slicer/volume", "Upload NRRD; LPS/signed-short only", None, False, False, None
    ),  # Phase 2+ if ever — `volume import` covers the file path
    Route(
        "GET",
        "/slicer/volumeSelection",
        "Cycle active volume in slice viewers",
        None,
        False,
        False,
        None,
    ),
)

_RENDER: tuple[Route, ...] = (
    Route(
        "GET",
        "/slicer/screenshot",
        "Main-window screenshot (PNG)",
        "render screenshot",
        False,
        False,
        "Phase 2",
    ),
    Route(
        "GET",
        "/slicer/slice",
        "Render a slice viewer to PNG",
        "render slice",
        False,
        False,
        "Phase 2",
    ),
    Route(
        "GET",
        "/slicer/threeD",
        "Render the first 3D view to PNG",
        "render threed",
        False,
        False,
        "Phase 2",
    ),
    Route(
        "GET",
        "/slicer/threeDGraphics",
        "Export 3D view as glTF (binary)",
        "render gltf",
        False,
        False,
        "Phase 2",
    ),
    Route("GET", "/slicer/timeimage", "Debug: render system time as PNG", None, False, False, None),
    Route(
        "PUT",
        "/slicer/gui",
        "Show/hide GUI chrome and switch layouts",
        "gui layout",
        False,
        False,
        "Phase 3",
    ),
)

_MARKUPS: tuple[Route, ...] = (
    Route(
        "GET",
        "/slicer/fiducials",
        "All MarkupsFiducialNodes flat",
        "markup list --type fiducial",
        False,
        False,
        "Phase 3",
    ),
    Route(
        "PUT",
        "/slicer/fiducial",
        "Set position of one fiducial control point",
        "markup fiducial-set",
        False,
        False,
        "Phase 3",
    ),
    Route(
        "GET",
        "/slicer/segmentations",
        "All SegmentationNodes with segment IDs",
        "markup list --type segmentation",
        False,
        False,
        "Phase 3",
    ),
    Route("GET", "/slicer/segmentation", "(stub: 'not implemented yet')", None, False, True, None),
    Route(
        "GET",
        "/slicer/gridTransforms",
        "List GridTransformNodes",
        "transform list",
        False,
        False,
        "Phase 3",
    ),
    Route(
        "GET",
        "/slicer/gridTransform",
        "Stream displacement grid as NRRD",
        "transform export",
        False,
        False,
        "Phase 3",
    ),
    Route("POST", "/slicer/gridTransform", "(stub: NotImplementedError)", None, False, True, None),
    Route("GET", "/slicer/tracking", "Set internal tracking cursor pose", None, False, False, None),
)

_POWER: tuple[Route, ...] = (
    Route(
        "POST", "/slicer/exec", "Run Python in Slicer's interpreter", "exec", True, False, "Phase 3"
    ),
    Route(
        "POST",
        "/slicer/accessDICOMwebStudy",
        "Pull a study from a DICOMweb server (e.g., Orthanc)",
        "dicom pull",
        False,
        False,
        "Phase 2",
        note=(
            "bypassed in CLI: Slicer's handler has a TypeError bug — it builds "
            "a 2-tuple body and then indexes into it with a string key. "
            "`dicom pull` uses /slicer/exec instead."
        ),
    ),
)

# --------------------------------------------------------------------- /dicom/*

_DICOM: tuple[Route, ...] = (
    Route(
        "GET",
        "/dicom/studies",
        "QIDO: list studies in Slicer's DICOM DB",
        "dicom studies",
        False,
        False,
        "Phase 2",
    ),
    Route(
        "GET",
        "/dicom/studies/{studyUID}/metadata",
        "QIDO: study metadata (DICOM JSON)",
        "dicom meta",
        False,
        False,
        "Phase 2",
    ),
    Route(
        "GET",
        "/dicom/studies/{studyUID}/series",
        "QIDO: list series in a study",
        "dicom series",
        False,
        False,
        "Phase 2",
    ),
    Route(
        "GET",
        "/dicom/studies/{studyUID}/series/{seriesUID}/metadata",
        "QIDO: series metadata",
        "dicom meta",
        False,
        False,
        "Phase 2",
    ),
    Route(
        "GET",
        "/dicom/studies/{studyUID}/series/{seriesUID}/instances",
        "QIDO: list instances in a series",
        "dicom instances",
        False,
        False,
        "Phase 2",
    ),
    Route(
        "GET",
        "/dicom/studies/{studyUID}/series/{seriesUID}/instances/{sopUID}",
        "WADO-RS: retrieve raw DICOM file",
        "dicom instance",
        False,
        False,
        "Phase 2",
    ),
    Route(
        "GET",
        "/dicom/studies/{studyUID}/series/{seriesUID}/instances/{sopUID}/metadata",
        "WADO-RS: instance metadata",
        "dicom meta",
        False,
        False,
        "Phase 2",
    ),
)


ROUTES: tuple[Route, ...] = (
    *_SYSTEM,
    *_MRML,
    *_DATA,
    *_RENDER,
    *_MARKUPS,
    *_POWER,
    *_DICOM,
)


# Pairs that `api raw` should refuse without --confirm.
DESTRUCTIVE_RAW: frozenset[tuple[str, str]] = frozenset(
    (r.method, r.path) for r in ROUTES if r.destructive
)


def find_route(method: str, path: str) -> Route | None:
    """Look up a route by (method, exact path). Used by `api raw` for guards."""
    method_upper = method.upper()
    for route in ROUTES:
        if route.method == method_upper and route.path == path:
            return route
    return None
