"""`slicer-cli markup list / fiducial-set / line` — unit tests.

Respx-mocked. The list endpoints return `{node_id: blob}` per the surface
report; the mixin normalizes to flat lists so callers iterate naturally.
"""

from __future__ import annotations

import json
from pathlib import Path

import respx
from httpx import Response
from typer.testing import CliRunner

from slicer_cli.cli.app import app

# Synthetic fixtures — no PHI, no real MRML state.
_FIDUCIALS_BLOB = {
    "vtkMRMLMarkupsFiducialNode1": {
        "name": "F1",
        "color": [1.0, 0.0, 0.0],
        "scale": 3.0,
        "markups": [
            {"label": "P0", "position": [10.0, -5.0, 2.0], "visible": True},
            {"label": "P1", "position": [12.0, -5.0, 2.0], "visible": True},
        ],
    },
    "vtkMRMLMarkupsFiducialNode2": {
        "name": "F2",
        "color": [0.0, 1.0, 0.0],
        "scale": 3.0,
        "markups": [],
    },
}

_SEGMENTATIONS_BLOB = {
    "vtkMRMLSegmentationNode1": {
        "name": "Seg1",
        "segmentIDs": ["Segment_1", "Segment_2"],
    },
}


# --------------------------------------------------------------- list


def test_markup_list_merged_view(runner: CliRunner) -> None:
    """No --type → two GETs (fiducials + segmentations) merged into one table."""
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        mock.get("/slicer/fiducials").mock(return_value=Response(200, json=_FIDUCIALS_BLOB))
        mock.get("/slicer/segmentations").mock(return_value=Response(200, json=_SEGMENTATIONS_BLOB))
        result = runner.invoke(app, ["--json", "markup", "list"])

    assert result.exit_code == 0, result.stderr
    body = json.loads(result.stdout)
    rows = body["markups"]
    kinds = [r["kind"] for r in rows]
    assert kinds.count("fiducial") == 2
    assert kinds.count("segmentation") == 1
    f1 = next(r for r in rows if r["id"] == "vtkMRMLMarkupsFiducialNode1")
    assert f1["extra"]["point_count"] == 2
    seg = next(r for r in rows if r["kind"] == "segmentation")
    assert seg["extra"]["segment_count"] == 2


def test_markup_list_filter_fiducial(runner: CliRunner) -> None:
    """`--type fiducial` → only the /slicer/fiducials GET fires."""
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        mock.get("/slicer/fiducials").mock(return_value=Response(200, json=_FIDUCIALS_BLOB))
        result = runner.invoke(app, ["--json", "markup", "list", "--type", "fiducial"])

    assert result.exit_code == 0, result.stderr
    body = json.loads(result.stdout)
    rows = body["markups"]
    assert len(rows) == 2
    assert all(r["kind"] == "fiducial" for r in rows)
    f1 = next(r for r in rows if r["id"] == "vtkMRMLMarkupsFiducialNode1")
    assert f1["scale"] == 3.0
    assert len(f1["points"]) == 2
    assert f1["points"][0]["position"] == [10.0, -5.0, 2.0]


def test_markup_list_filter_segmentation(runner: CliRunner) -> None:
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        mock.get("/slicer/segmentations").mock(return_value=Response(200, json=_SEGMENTATIONS_BLOB))
        result = runner.invoke(app, ["--json", "markup", "list", "--type", "segmentation"])

    assert result.exit_code == 0, result.stderr
    body = json.loads(result.stdout)
    assert body["markups"][0]["segment_ids"] == ["Segment_1", "Segment_2"]


def test_markup_list_unknown_type_blocked(runner: CliRunner) -> None:
    with respx.mock(base_url="http://127.0.0.1:2016", assert_all_called=False):
        result = runner.invoke(app, ["--json", "markup", "list", "--type", "bogus"])
    assert result.exit_code == 1
    assert json.loads(result.stdout)["error"]["code"] == "E_BAD_INPUT"


def test_markup_list_empty_returns_empty_array(runner: CliRunner) -> None:
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        mock.get("/slicer/fiducials").mock(return_value=Response(200, json={}))
        mock.get("/slicer/segmentations").mock(return_value=Response(200, json={}))
        result = runner.invoke(app, ["--json", "markup", "list"])

    assert result.exit_code == 0, result.stderr
    assert json.loads(result.stdout)["markups"] == []


def test_markup_list_5xx_surfaces_clean_error(runner: CliRunner) -> None:
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        mock.get("/slicer/fiducials").mock(return_value=Response(500))
        result = runner.invoke(app, ["--json", "markup", "list", "--type", "fiducial"])
    assert result.exit_code == 2
    assert json.loads(result.stdout)["error"]["code"] == "E_HTTP_5XX"


# --------------------------------------------------------------- fiducial-set


def test_fiducial_set_happy_path(runner: CliRunner) -> None:
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        route = mock.put("/slicer/fiducial").mock(
            return_value=Response(200, json={"success": True})
        )
        result = runner.invoke(
            app,
            [
                "--json",
                "markup",
                "fiducial-set",
                "--id",
                "F1",
                "--index",
                "0",
                "--r",
                "10",
                "--a",
                "-5",
                "--s",
                "2",
            ],
        )

    assert result.exit_code == 0, result.stderr
    assert route.called
    sent = route.calls.last.request
    qs = dict(sent.url.params.multi_items())
    assert qs["id"] == "F1"
    assert qs["index"] == "0"
    assert float(qs["r"]) == 10.0
    assert float(qs["a"]) == -5.0
    body = json.loads(result.stdout)
    assert body["id"] == "F1"
    assert body["index"] == 0
    assert body["position"] == [10.0, -5.0, 2.0]


def test_fiducial_set_empty_id_blocked(runner: CliRunner) -> None:
    with respx.mock(base_url="http://127.0.0.1:2016", assert_all_called=False):
        result = runner.invoke(
            app,
            [
                "--json",
                "markup",
                "fiducial-set",
                "--id",
                "",
                "--index",
                "0",
                "--r",
                "0",
                "--a",
                "0",
                "--s",
                "0",
            ],
        )
    assert result.exit_code == 1
    assert json.loads(result.stdout)["error"]["code"] == "E_BAD_INPUT"


def test_fiducial_set_negative_index_blocked(runner: CliRunner) -> None:
    with respx.mock(base_url="http://127.0.0.1:2016", assert_all_called=False):
        result = runner.invoke(
            app,
            [
                "--json",
                "markup",
                "fiducial-set",
                "--id",
                "F1",
                "--index",
                "-1",
                "--r",
                "0",
                "--a",
                "0",
                "--s",
                "0",
            ],
        )
    assert result.exit_code == 1
    assert json.loads(result.stdout)["error"]["code"] == "E_BAD_INPUT"


# --------------------------------------------------------------- line (templated /exec)


def test_markup_line_happy_path_writes_audit(runner: CliRunner, audit_log_path: Path) -> None:
    """`markup line` posts a templated /exec body and writes one audit line."""
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        route = mock.post("/slicer/exec").mock(
            return_value=Response(200, json={"id": "vtkMRMLMarkupsLineNode1", "length_mm": 86.6})
        )
        result = runner.invoke(
            app,
            [
                "--json",
                "markup",
                "line",
                "--p1",
                "0,0,0",
                "--p2",
                "50,50,50",
                "--name",
                "MyLine",
            ],
        )

    assert result.exit_code == 0, result.stderr
    body = json.loads(result.stdout)
    assert body["id"] == "vtkMRMLMarkupsLineNode1"
    assert body["length_mm"] == 86.6
    assert body["p1"] == [0.0, 0.0, 0.0]
    assert body["p2"] == [50.0, 50.0, 50.0]

    sent = route.calls.last.request.content.decode()
    assert "vtkMRMLMarkupsLineNode" in sent
    assert "AddControlPoint" in sent
    assert "'MyLine'" in sent  # repr-quoted name
    # All six coordinates appear as Python repr (-> "0" for ints, "50.0" via float).
    assert "0" in sent and "50" in sent

    # Audit log line written.
    line = audit_log_path.read_text().rstrip("\n")
    assert "op=markup.add_line" in line


def test_markup_line_bad_p1_format_blocked(runner: CliRunner) -> None:
    with respx.mock(base_url="http://127.0.0.1:2016", assert_all_called=False):
        result = runner.invoke(
            app,
            ["--json", "markup", "line", "--p1", "not,a,number", "--p2", "0,0,0"],
        )
    assert result.exit_code == 1
    assert json.loads(result.stdout)["error"]["code"] == "E_BAD_INPUT"


def test_markup_line_two_components_blocked(runner: CliRunner) -> None:
    """`--p1` must have three components."""
    with respx.mock(base_url="http://127.0.0.1:2016", assert_all_called=False):
        result = runner.invoke(
            app,
            ["--json", "markup", "line", "--p1", "1,2", "--p2", "0,0,0"],
        )
    assert result.exit_code == 1
    assert json.loads(result.stdout)["error"]["code"] == "E_BAD_INPUT"


def test_markup_line_empty_name_blocked(runner: CliRunner) -> None:
    with respx.mock(base_url="http://127.0.0.1:2016", assert_all_called=False):
        result = runner.invoke(
            app,
            ["--json", "markup", "line", "--p1", "0,0,0", "--p2", "1,1,1", "--name", "  "],
        )
    assert result.exit_code == 1
    assert json.loads(result.stdout)["error"]["code"] == "E_BAD_INPUT"
