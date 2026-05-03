"""Integration: read-only Phase-1 commands against live Slicer with MRHead loaded.

Gated on SLICER_INTEGRATION=1. The user is expected to have at least one
volume in the scene named "MRHead" (the standard SampleData entry) when
running these tests.
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
def test_volume_list_finds_mrhead(runner: CliRunner) -> None:
    result = runner.invoke(app, ["--json", "volume", "list"])
    assert result.exit_code == 0, result.stderr
    body = json.loads(result.stdout)
    names = [v["name"] for v in body["volumes"]]
    assert "MRHead" in names


@pytest.mark.skipif(not _gated(), reason="set SLICER_INTEGRATION=1 to run")
def test_scene_ids_returns_many(runner: CliRunner) -> None:
    result = runner.invoke(app, ["--json", "scene", "ids"])
    assert result.exit_code == 0
    ids = json.loads(result.stdout)["ids"]
    # MRHead scene has dozens of nodes (color tables, slice views, etc.)
    assert len(ids) > 20
    assert any(node_id.startswith("vtkMRMLScalarVolumeNode") for node_id in ids)


@pytest.mark.skipif(not _gated(), reason="set SLICER_INTEGRATION=1 to run")
def test_scene_nodes_class_filter(runner: CliRunner) -> None:
    result = runner.invoke(
        app,
        ["--json", "scene", "nodes", "--class", "vtkMRMLScalarVolumeNode"],
    )
    assert result.exit_code == 0
    nodes = json.loads(result.stdout)["nodes"]
    assert len(nodes) >= 1
    assert all(n["class"] == "vtkMRMLScalarVolumeNode" for n in nodes)


@pytest.mark.skipif(not _gated(), reason="set SLICER_INTEGRATION=1 to run")
def test_node_show_mrhead(runner: CliRunner) -> None:
    # First find the MRHead volume id
    list_result = runner.invoke(app, ["--json", "volume", "list"])
    volumes = json.loads(list_result.stdout)["volumes"]
    mrhead = next(v for v in volumes if v["name"] == "MRHead")

    show_result = runner.invoke(app, ["--json", "node", "show", mrhead["id"]])
    assert show_result.exit_code == 0
    body = json.loads(show_result.stdout)
    assert body["node"]["id"] == mrhead["id"]
    # MRHead is a scalar volume — should have spacing in properties
    assert "Spacing" in body["node"]["properties"]


@pytest.mark.skipif(not _gated(), reason="set SLICER_INTEGRATION=1 to run")
def test_sample_list_offline_works_without_slicer(runner: CliRunner) -> None:
    """`sample list` is purely offline — no Slicer call. Still passes when Slicer is up."""
    result = runner.invoke(app, ["--json", "sample", "list"])
    assert result.exit_code == 0
    assert "MRHead" in result.stdout
