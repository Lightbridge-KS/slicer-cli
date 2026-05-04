"""Integration: markup commands against live Slicer.

`markup list` runs against whatever is in the user's scene (empty list is
valid). `markup line` and `markup fiducial-set` mutate Slicer state, so
they're cleaned up via `node delete` of the IDs they create. Skips cleanly
if `/slicer/exec` is gated off.
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
def test_markup_list_against_live_slicer(runner: CliRunner) -> None:
    """`markup list` returns a JSON array (possibly empty)."""
    result = runner.invoke(app, ["--json", "markup", "list"])
    assert result.exit_code == 0, result.stderr
    body = json.loads(result.stdout)
    assert "markups" in body
    assert isinstance(body["markups"], list)


@pytest.mark.skipif(not _gated(), reason="set SLICER_INTEGRATION=1 to run")
def test_markup_line_create_then_cleanup(runner: CliRunner) -> None:
    """Create a line markup via /exec, then delete the resulting node.

    Skips if /slicer/exec is disabled.
    """
    create = runner.invoke(
        app,
        [
            "--json",
            "markup",
            "line",
            "--p1",
            "0,0,0",
            "--p2",
            "50,0,0",
            "--name",
            "SlicerCliTestLine",
        ],
    )
    if create.exit_code != 0:
        body = json.loads(create.stdout)
        if body.get("error", {}).get("code") == "E_HTTP_5XX":
            pytest.skip("/slicer/exec disabled — markup line cannot run end-to-end")
        raise AssertionError(f"markup line failed: {create.stdout}")

    create_body = json.loads(create.stdout)
    node_id = create_body["id"]
    assert node_id
    # Length should be ~50 mm (we placed endpoints 50 mm apart on R axis).
    assert create_body["length_mm"] is not None
    assert 49.0 < create_body["length_mm"] < 51.0

    # Cleanup — never leak test state into the user's scene.
    cleanup = runner.invoke(app, ["--json", "node", "delete", node_id])
    assert cleanup.exit_code == 0, cleanup.stderr
