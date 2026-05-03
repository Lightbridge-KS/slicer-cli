"""`slicer-cli status` happy path with respx mocking."""

from __future__ import annotations

import json

import respx
from httpx import Response
from typer.testing import CliRunner

from slicer_cli.cli._internal.argv import hoist_global_flags
from slicer_cli.cli.app import app

MOCK_VERSION = {
    "applicationName": "Slicer",
    "applicationVersion": "5.11.0-2026-04-25",
    "applicationDisplayName": "Slicer",
    "releaseType": "Preview",
    "revision": "34516",
    "arch": "amd64",
    "os": "macosx",
    "majorVersion": 5,
    "minorVersion": 11,
}


def test_status_json_returns_envelope(runner: CliRunner) -> None:
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        mock.get("/slicer/system/version").mock(return_value=Response(200, json=MOCK_VERSION))

        result = runner.invoke(app, ["--json", "status"])

    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["applicationName"] == "Slicer"
    assert payload["applicationVersion"] == "5.11.0-2026-04-25"
    assert payload["url"] == "http://127.0.0.1:2016"


def test_status_global_flag_after_command_via_hoister(runner: CliRunner) -> None:
    """`slicer-cli status --json` must work end-to-end after argv hoisting."""
    hoisted = hoist_global_flags(["status", "--json"])
    assert hoisted == ["--json", "status"]

    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        mock.get("/slicer/system/version").mock(return_value=Response(200, json=MOCK_VERSION))
        result = runner.invoke(app, hoisted)

    assert result.exit_code == 0, result.stderr
    assert json.loads(result.stdout)["ok"] is True


def test_status_pretty_includes_application_name(runner: CliRunner) -> None:
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        mock.get("/slicer/system/version").mock(return_value=Response(200, json=MOCK_VERSION))

        result = runner.invoke(app, ["--pretty", "status"])

    assert result.exit_code == 0
    assert "Slicer" in result.stdout
    assert "5.11.0-2026-04-25" in result.stdout


def test_hoist_lifts_value_flags() -> None:
    assert hoist_global_flags(["status", "--url", "http://x:1"]) == [
        "--url",
        "http://x:1",
        "status",
    ]
    assert hoist_global_flags(["status", "--url=http://x:1"]) == [
        "--url=http://x:1",
        "status",
    ]


def test_hoist_passes_through_command_args() -> None:
    assert hoist_global_flags(["volume", "show", "vtkMRMLNode1"]) == [
        "volume",
        "show",
        "vtkMRMLNode1",
    ]
