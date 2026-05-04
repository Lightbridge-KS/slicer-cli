"""`slicer-cli api routes / api raw` — offline introspection + raw escape hatch."""

from __future__ import annotations

import json
from pathlib import Path

import respx
from httpx import Response
from typer.testing import CliRunner

from slicer_cli.cli.app import app

# ----------------------------------------------------------------- api routes


def test_api_routes_returns_full_table(runner: CliRunner) -> None:
    """Pure offline command — no HTTP calls, just reads `client.routes`."""
    with respx.mock(base_url="http://127.0.0.1:2016", assert_all_called=False):
        result = runner.invoke(app, ["--json", "api", "routes"])

    assert result.exit_code == 0, result.stderr
    body = json.loads(result.stdout)
    assert len(body["routes"]) >= 30  # the inventory currently lists 30+ routes
    # /slicer/system/version is always present.
    paths = {r["path"] for r in body["routes"]}
    assert "/slicer/system/version" in paths


def test_api_routes_filters_by_method(runner: CliRunner) -> None:
    with respx.mock(base_url="http://127.0.0.1:2016", assert_all_called=False):
        result = runner.invoke(app, ["--json", "api", "routes", "--method", "DELETE"])

    assert result.exit_code == 0, result.stderr
    body = json.loads(result.stdout)
    assert all(r["method"] == "DELETE" for r in body["routes"])


def test_api_routes_destructive_only(runner: CliRunner) -> None:
    with respx.mock(base_url="http://127.0.0.1:2016", assert_all_called=False):
        result = runner.invoke(app, ["--json", "api", "routes", "--destructive"])

    assert result.exit_code == 0, result.stderr
    body = json.loads(result.stdout)
    assert len(body["routes"]) >= 1
    assert all(r["destructive"] for r in body["routes"])


def test_api_routes_phase_filter(runner: CliRunner) -> None:
    with respx.mock(base_url="http://127.0.0.1:2016", assert_all_called=False):
        result = runner.invoke(app, ["--json", "api", "routes", "--phase", "Phase 1"])

    assert result.exit_code == 0, result.stderr
    body = json.loads(result.stdout)
    assert len(body["routes"]) >= 1
    assert all(r["phase"] == "Phase 1" for r in body["routes"])


# ----------------------------------------------------------------- api raw


def test_api_raw_get_json_response(runner: CliRunner) -> None:
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        route = mock.get("/slicer/volumes").mock(
            return_value=Response(200, json=[{"id": "v1", "name": "MRHead"}])
        )
        result = runner.invoke(app, ["--json", "api", "raw", "GET", "/slicer/volumes"])

    assert result.exit_code == 0, result.stderr
    assert route.called
    body = json.loads(result.stdout)
    assert body["http_status"] == 200
    assert body["response"] == [{"id": "v1", "name": "MRHead"}]


def test_api_raw_passes_query_params(runner: CliRunner) -> None:
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        route = mock.get("/slicer/mrml/ids", params={"class": "vtkMRMLViewNode"}).mock(
            return_value=Response(200, json=["vtkMRMLViewNode1"])
        )
        result = runner.invoke(
            app,
            [
                "--json",
                "api",
                "raw",
                "GET",
                "/slicer/mrml/ids",
                "--query",
                "class=vtkMRMLViewNode",
            ],
        )

    assert result.exit_code == 0, result.stderr
    assert route.called


def test_api_raw_destructive_blocked_without_confirm(runner: CliRunner) -> None:
    """DELETE /slicer/mrml is in DESTRUCTIVE_RAW; --confirm is mandatory."""
    with respx.mock(base_url="http://127.0.0.1:2016", assert_all_called=False):
        result = runner.invoke(app, ["--json", "api", "raw", "DELETE", "/slicer/mrml"])

    assert result.exit_code == 6
    body = json.loads(result.stdout)
    assert body["error"]["code"] == "E_DESTRUCTIVE"


def test_api_raw_destructive_passes_with_confirm(runner: CliRunner) -> None:
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        route = mock.delete("/slicer/mrml").mock(return_value=Response(200, json={"success": True}))
        result = runner.invoke(app, ["--json", "api", "raw", "DELETE", "/slicer/mrml", "--confirm"])

    assert result.exit_code == 0, result.stderr
    assert route.called


def test_api_raw_invalid_method_returns_e_bad_input(runner: CliRunner) -> None:
    with respx.mock(base_url="http://127.0.0.1:2016", assert_all_called=False):
        result = runner.invoke(app, ["--json", "api", "raw", "PATCH", "/slicer/mrml"])

    assert result.exit_code == 1
    assert json.loads(result.stdout)["error"]["code"] == "E_BAD_INPUT"


def test_api_raw_malformed_query_returns_e_bad_input(runner: CliRunner) -> None:
    with respx.mock(base_url="http://127.0.0.1:2016", assert_all_called=False):
        result = runner.invoke(
            app,
            ["--json", "api", "raw", "GET", "/slicer/mrml/ids", "--query", "no_equals"],
        )

    assert result.exit_code == 1
    assert json.loads(result.stdout)["error"]["code"] == "E_BAD_INPUT"


def test_api_raw_non_json_response_requires_out(runner: CliRunner) -> None:
    """Binary / non-JSON responses must not be dumped to stdout silently."""
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        mock.get("/slicer/slice").mock(
            return_value=Response(
                200,
                content=b"\x89PNG\r\n\x1a\nfake",
                headers={"content-type": "image/png"},
            )
        )
        result = runner.invoke(app, ["--json", "api", "raw", "GET", "/slicer/slice"])

    assert result.exit_code == 1
    assert json.loads(result.stdout)["error"]["code"] == "E_BAD_INPUT"


def test_api_raw_non_json_response_writes_out_file(runner: CliRunner, tmp_path: Path) -> None:
    out_path = tmp_path / "fake.png"
    fake = b"\x89PNG\r\n\x1a\nfake-bytes"
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        mock.get("/slicer/slice").mock(
            return_value=Response(200, content=fake, headers={"content-type": "image/png"})
        )
        result = runner.invoke(
            app,
            ["--json", "api", "raw", "GET", "/slicer/slice", "--out", str(out_path)],
        )

    assert result.exit_code == 0, result.stderr
    body = json.loads(result.stdout)
    assert body["bytes"] == len(fake)
    assert out_path.read_bytes() == fake


def test_api_raw_body_from_file(runner: CliRunner, tmp_path: Path) -> None:
    body_file = tmp_path / "payload.py"
    body_file.write_bytes(b"__execResult = {'ok': True}\n")
    # POST /slicer/exec is in DESTRUCTIVE_RAW, so --confirm is required.
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        route = mock.post("/slicer/exec").mock(return_value=Response(200, json={"ok": True}))
        result = runner.invoke(
            app,
            [
                "--json",
                "api",
                "raw",
                "POST",
                "/slicer/exec",
                "--body",
                f"@{body_file}",
                "--confirm",
            ],
        )

    assert result.exit_code == 0, result.stderr
    assert route.called
    # The mocked request received our file's bytes verbatim.
    sent = route.calls.last.request.content
    assert sent == body_file.read_bytes()
