"""`slicer-cli scene nodes / scene ids` — unit tests with respx mocking."""

from __future__ import annotations

import json

import respx
from httpx import Response
from typer.testing import CliRunner

from slicer_cli.cli.app import app


def test_scene_ids_happy_path(runner: CliRunner) -> None:
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        mock.get("/slicer/mrml/ids").mock(
            return_value=Response(200, json=["vtkMRMLViewNode1", "vtkMRMLScalarVolumeNode1"])
        )
        result = runner.invoke(app, ["--json", "scene", "ids"])

    assert result.exit_code == 0, result.stderr
    body = json.loads(result.stdout)
    assert body["ids"] == ["vtkMRMLViewNode1", "vtkMRMLScalarVolumeNode1"]


def test_scene_ids_passes_class_filter(runner: CliRunner) -> None:
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        route = mock.get(
            "/slicer/mrml/ids",
            params={"class": "vtkMRMLScalarVolumeNode"},
        ).mock(return_value=Response(200, json=["vtkMRMLScalarVolumeNode1"]))

        result = runner.invoke(
            app,
            ["--json", "scene", "ids", "--class", "vtkMRMLScalarVolumeNode"],
        )

    assert result.exit_code == 0, result.stderr
    assert route.called
    assert json.loads(result.stdout)["ids"] == ["vtkMRMLScalarVolumeNode1"]


def test_scene_nodes_zips_ids_and_names(runner: CliRunner) -> None:
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        mock.get("/slicer/mrml/ids").mock(
            return_value=Response(200, json=["vtkMRMLScalarVolumeNode1", "vtkMRMLViewNode1"])
        )
        mock.get("/slicer/mrml/names").mock(return_value=Response(200, json=["MRHead", "View1"]))
        result = runner.invoke(app, ["--json", "scene", "nodes"])

    assert result.exit_code == 0, result.stderr
    body = json.loads(result.stdout)
    assert body["nodes"] == [
        {"id": "vtkMRMLScalarVolumeNode1", "name": "MRHead", "class": "vtkMRMLScalarVolumeNode"},
        {"id": "vtkMRMLViewNode1", "name": "View1", "class": "vtkMRMLViewNode"},
    ]


def test_scene_ids_5xx(runner: CliRunner) -> None:
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        mock.get("/slicer/mrml/ids").mock(return_value=Response(500))
        result = runner.invoke(app, ["--json", "scene", "ids"])

    assert result.exit_code == 2
    body = json.loads(result.stdout)
    assert body["error"]["code"] == "E_HTTP_5XX"


# --------------------------------------------------------------- scene load (Batch 3)


def test_scene_load_happy_path(runner: CliRunner) -> None:
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        route = mock.post(
            "/slicer/mrml",
            params={"filetype": "SceneFile", "localfile": "/tmp/scene.mrb"},
        ).mock(return_value=Response(200, json={"success": True, "loadedNodeIDs": ["a", "b"]}))

        result = runner.invoke(app, ["--json", "scene", "load", "/tmp/scene.mrb"])

    assert result.exit_code == 0, result.stderr
    assert route.called
    body = json.loads(result.stdout)
    assert body["loaded_node_ids"] == ["a", "b"]


def test_scene_load_4xx(runner: CliRunner) -> None:
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        mock.post("/slicer/mrml").mock(return_value=Response(400, json={"message": "bad scene"}))
        result = runner.invoke(app, ["--json", "scene", "load", "/tmp/bad.mrb"])

    assert result.exit_code == 2
    assert json.loads(result.stdout)["error"]["code"] == "E_HTTP_4XX"


# --------------------------------------------------------------- scene save (Batch 4)


def test_scene_save_uses_power_tool_endpoint(runner: CliRunner) -> None:
    """Locked Q-A: scene save uses POST /slicer/exec with a templated payload."""
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        route = mock.post("/slicer/exec").mock(
            return_value=Response(200, json={"saved": True, "path": "/tmp/test.mrb"})
        )
        result = runner.invoke(app, ["--json", "scene", "save", "/tmp/test.mrb"])

    assert result.exit_code == 0, result.stderr
    assert route.called
    body = json.loads(result.stdout)
    assert body["path"] == "/tmp/test.mrb"
    assert body["result"]["saved"] is True


def test_scene_save_5xx_when_power_tool_disabled(runner: CliRunner) -> None:
    """Some Slicer instances have /exec disabled; surface a clean E_HTTP_5XX."""
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        mock.post("/slicer/exec").mock(
            return_value=Response(500, json={"message": "unknown command"})
        )
        result = runner.invoke(app, ["--json", "scene", "save", "/tmp/x.mrb"])

    assert result.exit_code == 2
    body = json.loads(result.stdout)
    assert body["error"]["code"] == "E_HTTP_5XX"


# --------------------------------------------------------------- scene clear (Batch 5)


def test_scene_clear_without_confirm_is_blocked(runner: CliRunner) -> None:
    """Without `--confirm`, never makes the HTTP call — guard fires first."""
    with respx.mock(base_url="http://127.0.0.1:2016", assert_all_called=False):
        result = runner.invoke(app, ["--json", "scene", "clear"])

    assert result.exit_code == 6
    body = json.loads(result.stdout)
    assert body["error"]["code"] == "E_DESTRUCTIVE"


def test_scene_clear_with_confirm_calls_delete(runner: CliRunner) -> None:
    """With `--confirm`, the CLI issues a parameter-less DELETE on /slicer/mrml."""
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        route = mock.delete("/slicer/mrml").mock(return_value=Response(200, json={"success": True}))
        result = runner.invoke(app, ["--json", "scene", "clear", "--confirm"])

    assert result.exit_code == 0, result.stderr
    assert route.called
    body = json.loads(result.stdout)
    assert body["cleared"] is True
