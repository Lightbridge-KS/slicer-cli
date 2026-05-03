"""`slicer-cli node show` — unit tests + empty-id safety guard."""

from __future__ import annotations

import json

import respx
from httpx import Response
from typer.testing import CliRunner

from slicer_cli.cli.app import app


def test_node_show_happy_path(runner: CliRunner) -> None:
    node_id = "vtkMRMLScalarVolumeNode1"
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        mock.get("/slicer/mrml/properties").mock(
            return_value=Response(200, json={node_id: {"Name": "MRHead"}})
        )
        result = runner.invoke(app, ["--json", "node", "show", node_id])

    assert result.exit_code == 0, result.stderr
    body = json.loads(result.stdout)
    assert body["node"]["id"] == node_id
    assert body["node"]["properties"]["Name"] == "MRHead"


def test_node_show_empty_id_blocked(runner: CliRunner) -> None:
    """Empty node id should fail at the CLI guard, never reaching Slicer.

    No routes registered: if the guard fails to fire, respx will raise on
    the unexpected request, surfacing the regression immediately.
    """
    with respx.mock(base_url="http://127.0.0.1:2016", assert_all_called=False):
        result = runner.invoke(app, ["--json", "node", "show", ""])

    assert result.exit_code == 6
    body = json.loads(result.stdout)
    assert body["error"]["code"] == "E_EMPTY_SELECTOR"


def test_node_show_whitespace_id_blocked(runner: CliRunner) -> None:
    with respx.mock(base_url="http://127.0.0.1:2016", assert_all_called=False):
        result = runner.invoke(app, ["--json", "node", "show", "   "])

    assert result.exit_code == 6
    assert json.loads(result.stdout)["error"]["code"] == "E_EMPTY_SELECTOR"


def test_node_show_4xx(runner: CliRunner) -> None:
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        mock.get("/slicer/mrml/properties").mock(
            return_value=Response(404, json={"message": "no such node"})
        )
        result = runner.invoke(app, ["--json", "node", "show", "missing"])

    assert result.exit_code == 2
    assert json.loads(result.stdout)["error"]["http_status"] == 404


# --------------------------------------------------------------- node reload (Batch 4)


def test_node_reload_happy_path(runner: CliRunner) -> None:
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        route = mock.put("/slicer/mrml", params={"id": "vtkMRMLScalarVolumeNode1"}).mock(
            return_value=Response(200, json={"success": True, "reloadedNodeIDs": ["v1"]})
        )
        result = runner.invoke(app, ["--json", "node", "reload", "vtkMRMLScalarVolumeNode1"])

    assert result.exit_code == 0, result.stderr
    assert route.called
    body = json.loads(result.stdout)
    assert body["node_id"] == "vtkMRMLScalarVolumeNode1"
    assert body["result"]["success"] is True


def test_node_reload_empty_id_blocked(runner: CliRunner) -> None:
    with respx.mock(base_url="http://127.0.0.1:2016", assert_all_called=False):
        result = runner.invoke(app, ["--json", "node", "reload", ""])
    assert result.exit_code == 6
    assert json.loads(result.stdout)["error"]["code"] == "E_EMPTY_SELECTOR"


# --------------------------------------------------------------- node delete (Batch 5)


def test_node_delete_happy_path(runner: CliRunner) -> None:
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        route = mock.delete("/slicer/mrml", params={"id": "vtkMRMLScalarVolumeNode2"}).mock(
            return_value=Response(200, json={"success": True})
        )
        result = runner.invoke(app, ["--json", "node", "delete", "vtkMRMLScalarVolumeNode2"])

    assert result.exit_code == 0, result.stderr
    assert route.called
    body = json.loads(result.stdout)
    assert body["node_id"] == "vtkMRMLScalarVolumeNode2"
    assert body["deleted"] is True


def test_node_delete_empty_id_blocked(runner: CliRunner) -> None:
    """Empty id is the trapdoor that clears the entire scene — guard MUST fire."""
    with respx.mock(base_url="http://127.0.0.1:2016", assert_all_called=False):
        result = runner.invoke(app, ["--json", "node", "delete", ""])

    assert result.exit_code == 6
    body = json.loads(result.stdout)
    assert body["error"]["code"] == "E_EMPTY_SELECTOR"


def test_node_delete_whitespace_id_blocked(runner: CliRunner) -> None:
    with respx.mock(base_url="http://127.0.0.1:2016", assert_all_called=False):
        result = runner.invoke(app, ["--json", "node", "delete", "   "])

    assert result.exit_code == 6
    assert json.loads(result.stdout)["error"]["code"] == "E_EMPTY_SELECTOR"
