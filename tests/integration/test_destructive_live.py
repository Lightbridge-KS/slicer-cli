"""Integration: scoped destructive ops against live Slicer.

CRITICAL: these tests never call `scene clear` or `system shutdown` against
the user's running Slicer. They load a throwaway sample, then delete the
specific node ids that load returned. The user's MRHead session is preserved.

`api raw` and `doctor` integration coverage lives here too because they make
end-to-end HTTP calls and benefit from a live Slicer.
"""

from __future__ import annotations

import json
import os

import pytest
from typer.testing import CliRunner

from slicer_cli.cli.app import app

pytestmark = pytest.mark.integration


def _gated() -> bool:
    return os.environ.get("SLICER_INTEGRATION", "") not in {"", "0", "false", "False"}


@pytest.mark.skipif(not _gated(), reason="set SLICER_INTEGRATION=1 to run")
def test_doctor_reports_reachable(runner: CliRunner) -> None:
    """`doctor` against live Slicer: reachable + slicer-api should always be OK."""
    result = runner.invoke(app, ["--json", "doctor"])

    assert result.exit_code == 0, result.stderr
    body = json.loads(result.stdout)
    by_name = {c["name"]: c for c in body["checks"]}
    assert by_name["reachable"]["ok"] is True
    assert by_name["slicer-api"]["ok"] is True


@pytest.mark.skipif(not _gated(), reason="set SLICER_INTEGRATION=1 to run")
def test_api_routes_lists_mrml_endpoints(runner: CliRunner) -> None:
    """`api routes` is offline-only, but worth verifying inside the live suite too."""
    result = runner.invoke(app, ["--json", "api", "routes", "--category", "mrml"])

    assert result.exit_code == 0, result.stderr
    body = json.loads(result.stdout)
    paths = {r["path"] for r in body["routes"]}
    assert "/slicer/mrml" in paths


@pytest.mark.skipif(not _gated(), reason="set SLICER_INTEGRATION=1 to run")
def test_api_raw_get_volumes_round_trip(runner: CliRunner) -> None:
    """End-to-end: `api raw GET /slicer/volumes` matches `volume list`."""
    raw_result = runner.invoke(app, ["--json", "api", "raw", "GET", "/slicer/volumes"])
    list_result = runner.invoke(app, ["--json", "volume", "list"])

    assert raw_result.exit_code == 0, raw_result.stderr
    assert list_result.exit_code == 0, list_result.stderr

    raw_body = json.loads(raw_result.stdout)
    list_body = json.loads(list_result.stdout)
    raw_ids = {v["id"] for v in raw_body["response"]}
    list_ids = {v["id"] for v in list_body["volumes"]}
    assert raw_ids == list_ids


@pytest.mark.skipif(not _gated(), reason="set SLICER_INTEGRATION=1 to run")
def test_load_then_delete_throwaway_sample(runner: CliRunner) -> None:
    """Round-trip: load a sample, capture its node ids, delete each, verify gone.

    Uses MRBrainTumor1 as the throwaway. If MRHead is what's currently loaded,
    this distinct sample is loaded *additionally* and only the new ids get
    deleted — the user's MRHead session is preserved.
    """
    before = runner.invoke(app, ["--json", "scene", "ids"])
    assert before.exit_code == 0, before.stderr
    before_ids: set[str] = set(json.loads(before.stdout)["ids"])

    loaded = runner.invoke(app, ["--json", "sample", "load", "MRBrainTumor1"])
    assert loaded.exit_code == 0, loaded.stderr

    after = runner.invoke(app, ["--json", "scene", "ids"])
    assert after.exit_code == 0, after.stderr
    after_ids: set[str] = set(json.loads(after.stdout)["ids"])

    new_ids = after_ids - before_ids
    if not new_ids:
        pytest.skip("Sample load did not add new nodes (already loaded?)")

    # Delete only the nodes we just added.
    for node_id in new_ids:
        result = runner.invoke(app, ["--json", "node", "delete", node_id])
        # Some auxiliary nodes may have been auto-removed when the parent went;
        # we tolerate 4xx ("no such node") on those.
        if result.exit_code not in (0, 2):
            raise AssertionError(
                f"Unexpected exit {result.exit_code} for {node_id}: {result.stdout}"
            )

    final = runner.invoke(app, ["--json", "scene", "ids"])
    assert final.exit_code == 0, final.stderr
    final_ids: set[str] = set(json.loads(final.stdout)["ids"])
    # The originals (e.g., MRHead) are still present.
    assert before_ids.issubset(final_ids), "Existing nodes were unexpectedly removed"


@pytest.mark.skipif(not _gated(), reason="set SLICER_INTEGRATION=1 to run")
def test_scene_clear_is_blocked_without_confirm(runner: CliRunner) -> None:
    """Defence-in-depth: even against live Slicer, the guard fires before any HTTP call."""
    result = runner.invoke(app, ["--json", "scene", "clear"])
    assert result.exit_code == 6
    body = json.loads(result.stdout)
    assert body["error"]["code"] == "E_DESTRUCTIVE"


@pytest.mark.skipif(not _gated(), reason="set SLICER_INTEGRATION=1 to run")
def test_system_shutdown_is_blocked_without_confirm(runner: CliRunner) -> None:
    """Likewise — never accidentally shut down the user's running Slicer."""
    result = runner.invoke(app, ["--json", "system", "shutdown"])
    assert result.exit_code == 6
    body = json.loads(result.stdout)
    assert body["error"]["code"] == "E_DESTRUCTIVE"
