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
- `category`      : Capability tag — one of "system", "mrml", "data", "render",
                    "markup", "transform", "dicom", "exec", "gui", or None for
                    endpoints we don't wrap (escape-hatch only via `api raw`).
                    Used by `api routes --category` for filtered browsing.
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
    category: str | None
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
        "system",
    ),
    Route(
        "DELETE",
        "/slicer/system",
        "Quit application (1 s deferred)",
        "system shutdown --confirm",
        True,
        False,
        "system",
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
        "mrml",
    ),
    Route(
        "GET",
        "/slicer/mrml/ids",
        "List ids of selected MRML nodes",
        "scene ids",
        False,
        False,
        "mrml",
    ),
    Route(
        "GET",
        "/slicer/mrml/properties",
        "Full property dict of selected nodes",
        "node show",
        False,
        False,
        "mrml",
    ),
    Route(
        "GET",
        "/slicer/mrml/file",
        "Save selected node to server-side file",
        "node export (via volume export) / scene save",
        False,
        False,
        "mrml",
    ),
    Route(
        "POST",
        "/slicer/mrml",
        "Load file/url as typed node",
        "volume import / scene load",
        False,
        False,
        "mrml",
    ),
    Route(
        "PUT",
        "/slicer/mrml",
        "Reload selected nodes from original",
        "node reload",
        False,
        False,
        "mrml",
    ),
    Route(
        "DELETE",
        "/slicer/mrml",
        "Delete selected nodes (empty = clear scene!)",
        "node delete / scene clear --confirm",
        True,
        False,
        "mrml",
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
        "data",
    ),
    Route(
        "GET",
        "/slicer/volumes",
        "List scalar + labelmap volumes",
        "volume list",
        False,
        False,
        "data",
    ),
    Route(
        "GET",
        "/slicer/volume",
        "Stream a volume as NRRD bytes",
        "volume export",
        False,
        False,
        "data",
    ),
    Route("POST", "/slicer/volume", "Upload NRRD; LPS/signed-short only", None, False, False, None),
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
        "render",
    ),
    Route(
        "GET",
        "/slicer/slice",
        "Render a slice viewer to PNG",
        "render slice",
        False,
        False,
        "render",
    ),
    Route(
        "GET",
        "/slicer/threeD",
        "Render the first 3D view to PNG",
        "render threed",
        False,
        False,
        "render",
    ),
    Route(
        "GET",
        "/slicer/threeDGraphics",
        "Export 3D view as glTF (binary)",
        "render gltf",
        False,
        False,
        "render",
    ),
    Route("GET", "/slicer/timeimage", "Debug: render system time as PNG", None, False, False, None),
    Route(
        "PUT",
        "/slicer/gui",
        "Show/hide GUI chrome and switch layouts",
        "gui layout",
        False,
        False,
        "gui",
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
        "markup",
    ),
    Route(
        "PUT",
        "/slicer/fiducial",
        "Set position of one fiducial control point",
        "markup fiducial-set",
        False,
        False,
        "markup",
    ),
    Route(
        "GET",
        "/slicer/segmentations",
        "All SegmentationNodes with segment IDs",
        "markup list --type segmentation",
        False,
        False,
        "markup",
    ),
    Route("GET", "/slicer/segmentation", "(stub: 'not implemented yet')", None, False, True, None),
    Route(
        "GET",
        "/slicer/gridTransforms",
        "List GridTransformNodes",
        "transform list",
        False,
        False,
        "transform",
    ),
    Route(
        "GET",
        "/slicer/gridTransform",
        "Stream displacement grid as NRRD",
        "transform export",
        False,
        False,
        "transform",
    ),
    Route("POST", "/slicer/gridTransform", "(stub: NotImplementedError)", None, False, True, None),
    Route("GET", "/slicer/tracking", "Set internal tracking cursor pose", None, False, False, None),
)

_POWER: tuple[Route, ...] = (
    Route(
        "POST", "/slicer/exec", "Run Python in Slicer's interpreter", "exec", True, False, "exec"
    ),
    Route(
        "POST",
        "/slicer/accessDICOMwebStudy",
        "Pull a study from a DICOMweb server (e.g., Orthanc)",
        "dicom pull",
        False,
        False,
        "dicom",
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
        "dicom",
    ),
    Route(
        "GET",
        "/dicom/studies/{studyUID}/metadata",
        "QIDO: study metadata (DICOM JSON)",
        "dicom meta",
        False,
        False,
        "dicom",
    ),
    Route(
        "GET",
        "/dicom/studies/{studyUID}/series",
        "QIDO: list series in a study",
        "dicom series",
        False,
        False,
        "dicom",
    ),
    Route(
        "GET",
        "/dicom/studies/{studyUID}/series/{seriesUID}/metadata",
        "QIDO: series metadata",
        "dicom meta",
        False,
        False,
        "dicom",
    ),
    Route(
        "GET",
        "/dicom/studies/{studyUID}/series/{seriesUID}/instances",
        "QIDO: list instances in a series",
        "dicom instances",
        False,
        False,
        "dicom",
    ),
    Route(
        "GET",
        "/dicom/studies/{studyUID}/series/{seriesUID}/instances/{sopUID}",
        "WADO-RS: retrieve raw DICOM file",
        "dicom instance",
        False,
        False,
        "dicom",
    ),
    Route(
        "GET",
        "/dicom/studies/{studyUID}/series/{seriesUID}/instances/{sopUID}/metadata",
        "WADO-RS: instance metadata",
        "dicom meta",
        False,
        False,
        "dicom",
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
