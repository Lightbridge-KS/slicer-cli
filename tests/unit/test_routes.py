"""Route inventory data file — sanity checks."""

from __future__ import annotations

from slicer_cli.client.routes import (
    DESTRUCTIVE_RAW,
    ROUTES,
    Route,
    find_route,
)


def test_routes_is_nonempty() -> None:
    assert len(ROUTES) >= 30


def test_phase1_endpoints_present() -> None:
    paths = {(r.method, r.path) for r in ROUTES}
    must_have = {
        ("GET", "/slicer/system/version"),
        ("DELETE", "/slicer/system"),
        ("GET", "/slicer/volumes"),
        ("GET", "/slicer/volume"),
        ("GET", "/slicer/mrml/ids"),
        ("GET", "/slicer/mrml/names"),
        ("GET", "/slicer/mrml/properties"),
        ("POST", "/slicer/mrml"),
        ("PUT", "/slicer/mrml"),
        ("DELETE", "/slicer/mrml"),
        ("GET", "/slicer/sampledata"),
    }
    missing = must_have - paths
    assert not missing, f"Missing Phase-1 routes: {missing}"


def test_destructive_routes_flagged() -> None:
    """The set of destructive routes must include the known dangerous ones."""
    assert ("DELETE", "/slicer/mrml") in DESTRUCTIVE_RAW
    assert ("DELETE", "/slicer/system") in DESTRUCTIVE_RAW
    # /slicer/exec is destructive (arbitrary code execution)
    assert ("POST", "/slicer/exec") in DESTRUCTIVE_RAW


def test_read_only_routes_not_flagged() -> None:
    assert ("GET", "/slicer/system/version") not in DESTRUCTIVE_RAW
    assert ("GET", "/slicer/volumes") not in DESTRUCTIVE_RAW


def test_find_route_returns_match() -> None:
    route = find_route("GET", "/slicer/system/version")
    assert route is not None
    assert route.method == "GET"
    assert route.cli_command == "status / system version"


def test_find_route_method_is_case_insensitive() -> None:
    assert find_route("get", "/slicer/volumes") is not None


def test_find_route_returns_none_for_unknown() -> None:
    assert find_route("GET", "/slicer/does-not-exist") is None


def test_route_dataclass_is_frozen() -> None:
    route = ROUTES[0]
    assert isinstance(route, Route)
    # frozen=True; mutation should raise
    try:
        route.path = "/changed"  # type: ignore[misc]
    except (AttributeError, TypeError):
        return
    raise AssertionError("Route should be frozen")


def test_access_dicomweb_study_is_flagged_with_bug_note() -> None:
    """The known upstream Slicer bug must be exposed via `api routes` so agents see the hazard."""
    route = find_route("POST", "/slicer/accessDICOMwebStudy")
    assert route is not None
    assert route.note is not None
    assert "exec" in route.note.lower()  # mentions the workaround


def test_phase2_endpoints_present() -> None:
    paths = {(r.method, r.path) for r in ROUTES}
    must_have = {
        ("GET", "/slicer/slice"),
        ("GET", "/slicer/threeD"),
        ("GET", "/slicer/screenshot"),
        ("GET", "/slicer/threeDGraphics"),
        ("GET", "/dicom/studies"),
        ("POST", "/slicer/accessDICOMwebStudy"),
    }
    missing = must_have - paths
    assert not missing, f"Missing Phase-2 routes: {missing}"
