"""Integration: export operations against live Slicer with MRHead loaded.

`scene save` is intentionally NOT tested live because the user's Slicer has
/exec disabled in this environment; that path is fully covered by unit
tests with respx mocks.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from slicer_cli.cli.app import app

pytestmark = pytest.mark.integration


def _gated() -> bool:
    return os.environ.get("SLICER_INTEGRATION", "") not in {"", "0", "false", "False"}


@pytest.mark.skipif(not _gated(), reason="set SLICER_INTEGRATION=1 to run")
def test_volume_export_mrhead_to_disk(runner: CliRunner, tmp_path: Path) -> None:
    """Export the MRHead volume and verify a real NRRD lands on disk."""
    list_result = runner.invoke(app, ["--json", "volume", "list"])
    volumes = json.loads(list_result.stdout)["volumes"]
    mrhead = next(v for v in volumes if v["name"] == "MRHead")

    out_path = tmp_path / "mrhead.nrrd"
    result = runner.invoke(
        app, ["--json", "volume", "export", mrhead["id"], "--out", str(out_path)]
    )

    assert result.exit_code == 0, result.stderr
    body = json.loads(result.stdout)
    assert body["bytes"] > 100_000  # MRHead is ~16 MB
    assert out_path.exists()
    assert out_path.read_bytes()[:5] == b"NRRD0"  # NRRD magic header


@pytest.mark.skipif(not _gated(), reason="set SLICER_INTEGRATION=1 to run")
def test_volume_export_unknown_id_returns_error(runner: CliRunner, tmp_path: Path) -> None:
    out_path = tmp_path / "nope.nrrd"
    result = runner.invoke(
        app,
        ["--json", "volume", "export", "vtkMRMLDoesNotExist99", "--out", str(out_path)],
    )

    # Slicer typically returns 5xx with a python traceback for unknown ids.
    # Either way, the CLI surfaces a non-zero exit code.
    assert result.exit_code != 0
    body = json.loads(result.stdout)
    assert body["ok"] is False
