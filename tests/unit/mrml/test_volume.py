"""`slicer-cli volume list / show` — unit tests with respx mocking."""

from __future__ import annotations

import json

import respx
from httpx import Response
from typer.testing import CliRunner

from slicer_cli.cli.app import app


def test_volume_list_happy_path(runner: CliRunner) -> None:
    payload = [{"id": "vtkMRMLScalarVolumeNode1", "name": "MRHead"}]
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        mock.get("/slicer/volumes").mock(return_value=Response(200, json=payload))
        result = runner.invoke(app, ["--json", "volume", "list"])

    assert result.exit_code == 0, result.stderr
    body = json.loads(result.stdout)
    assert body["ok"] is True
    assert body["volumes"] == [
        {"id": "vtkMRMLScalarVolumeNode1", "name": "MRHead", "class": "vtkMRMLScalarVolumeNode"},
    ]


def test_volume_list_empty(runner: CliRunner) -> None:
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        mock.get("/slicer/volumes").mock(return_value=Response(200, json=[]))
        result = runner.invoke(app, ["--json", "volume", "list"])

    assert result.exit_code == 0
    assert json.loads(result.stdout)["volumes"] == []


def test_volume_list_5xx_maps_to_e_http_5xx(runner: CliRunner) -> None:
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        mock.get("/slicer/volumes").mock(
            return_value=Response(500, json={"message": "scene gone bad"})
        )
        result = runner.invoke(app, ["--json", "volume", "list"])

    assert result.exit_code == 2
    body = json.loads(result.stdout)
    assert body["error"]["code"] == "E_HTTP_5XX"
    assert body["error"]["http_status"] == 500


def test_volume_show_happy_path(runner: CliRunner) -> None:
    node_id = "vtkMRMLScalarVolumeNode1"
    response_payload = {node_id: {"Name": "MRHead", "Spacing": [1.0, 1.0, 1.3]}}
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        mock.get("/slicer/mrml/properties").mock(return_value=Response(200, json=response_payload))
        result = runner.invoke(app, ["--json", "volume", "show", node_id])

    assert result.exit_code == 0, result.stderr
    body = json.loads(result.stdout)
    assert body["node"]["id"] == node_id
    assert body["node"]["properties"]["Name"] == "MRHead"


def test_volume_show_4xx_maps_to_e_http_4xx(runner: CliRunner) -> None:
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        mock.get("/slicer/mrml/properties").mock(
            return_value=Response(404, json={"message": "no such node"})
        )
        result = runner.invoke(app, ["--json", "volume", "show", "missing"])

    assert result.exit_code == 2
    body = json.loads(result.stdout)
    assert body["error"]["code"] == "E_HTTP_4XX"
    assert body["error"]["http_status"] == 404


# --------------------------------------------------------------- volume import (Batch 3)


def test_volume_import_happy_path(runner: CliRunner) -> None:
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        route = mock.post(
            "/slicer/mrml",
            params={"filetype": "VolumeFile", "localfile": "/tmp/x.nrrd"},
        ).mock(
            return_value=Response(
                200,
                json={"success": True, "loadedNodeIDs": ["vtkMRMLScalarVolumeNode2"]},
            )
        )
        result = runner.invoke(app, ["--json", "volume", "import", "/tmp/x.nrrd"])

    assert result.exit_code == 0, result.stderr
    assert route.called
    body = json.loads(result.stdout)
    assert body["loaded_node_ids"] == ["vtkMRMLScalarVolumeNode2"]
    assert body["path"] == "/tmp/x.nrrd"


def test_volume_import_passes_name_param(runner: CliRunner) -> None:
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        route = mock.post(
            "/slicer/mrml",
            params={
                "filetype": "VolumeFile",
                "localfile": "/tmp/x.nrrd",
                "name": "MyVolume",
            },
        ).mock(return_value=Response(200, json={"success": True, "loadedNodeIDs": ["v1"]}))

        result = runner.invoke(
            app, ["--json", "volume", "import", "/tmp/x.nrrd", "--name", "MyVolume"]
        )

    assert result.exit_code == 0, result.stderr
    assert route.called


def test_volume_import_4xx_for_missing_file(runner: CliRunner) -> None:
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        mock.post("/slicer/mrml").mock(return_value=Response(400, json={"message": "no file"}))
        result = runner.invoke(app, ["--json", "volume", "import", "/tmp/missing.nrrd"])

    assert result.exit_code == 2
    assert json.loads(result.stdout)["error"]["code"] == "E_HTTP_4XX"


# --------------------------------------------------------------- volume export (Batch 4)


def test_volume_export_writes_file(runner: CliRunner, tmp_path: object) -> None:
    """`volume export --out path` writes the NRRD bytes to disk."""
    from pathlib import Path

    out_path = Path(tmp_path) / "export.nrrd"  # type: ignore[arg-type]
    fake_nrrd = b"NRRD0004\nfake bytes content for testing"
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        mock.get("/slicer/volume", params={"id": "vtkMRMLScalarVolumeNode1"}).mock(
            return_value=Response(200, content=fake_nrrd)
        )
        result = runner.invoke(
            app,
            ["--json", "volume", "export", "vtkMRMLScalarVolumeNode1", "--out", str(out_path)],
        )

    assert result.exit_code == 0, result.stderr
    body = json.loads(result.stdout)
    assert body["bytes"] == len(fake_nrrd)
    assert out_path.read_bytes() == fake_nrrd


def test_volume_export_requires_out_flag(runner: CliRunner) -> None:
    """Locked Q-D: --out is required (no surprise binary on TTY)."""
    result = runner.invoke(app, ["--json", "volume", "export", "vtkMRMLScalarVolumeNode1"])
    # Typer exits 2 for missing required option; we don't reach the client.
    assert result.exit_code == 2


def test_volume_export_empty_id_blocked(runner: CliRunner) -> None:
    with respx.mock(base_url="http://127.0.0.1:2016", assert_all_called=False):
        result = runner.invoke(app, ["--json", "volume", "export", "", "--out", "/tmp/x.nrrd"])

    assert result.exit_code == 6
    assert json.loads(result.stdout)["error"]["code"] == "E_EMPTY_SELECTOR"


# --------------------------------------------------------------- volume delete (Batch 5)


def test_volume_delete_happy_path(runner: CliRunner) -> None:
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        route = mock.delete("/slicer/mrml", params={"id": "vtkMRMLScalarVolumeNode3"}).mock(
            return_value=Response(200, json={"success": True})
        )
        result = runner.invoke(app, ["--json", "volume", "delete", "vtkMRMLScalarVolumeNode3"])

    assert result.exit_code == 0, result.stderr
    assert route.called
    body = json.loads(result.stdout)
    assert body["node_id"] == "vtkMRMLScalarVolumeNode3"
    assert body["deleted"] is True


def test_volume_delete_empty_id_blocked(runner: CliRunner) -> None:
    with respx.mock(base_url="http://127.0.0.1:2016", assert_all_called=False):
        result = runner.invoke(app, ["--json", "volume", "delete", ""])

    assert result.exit_code == 6
    assert json.loads(result.stdout)["error"]["code"] == "E_EMPTY_SELECTOR"
