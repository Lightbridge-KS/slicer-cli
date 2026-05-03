"""Offline / connection-refused -> E_NOT_RUNNING with exit code 3."""

from __future__ import annotations

import json

import httpx
import respx
from typer.testing import CliRunner

from slicer_cli.cli.app import app


def test_status_connection_refused_returns_e_not_running(runner: CliRunner) -> None:
    with respx.mock(base_url="http://127.0.0.1:9999") as mock:
        mock.get("/slicer/system/version").mock(side_effect=httpx.ConnectError("refused"))

        result = runner.invoke(app, ["--json", "--url", "http://127.0.0.1:9999", "status"])

    assert result.exit_code == 3, result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "E_NOT_RUNNING"
    assert payload["error"]["endpoint"] == "/slicer/system/version"
    assert "Web Server" in payload["error"]["hint"]


def test_status_timeout_returns_e_timeout(runner: CliRunner) -> None:
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        mock.get("/slicer/system/version").mock(side_effect=httpx.ReadTimeout("slow"))

        result = runner.invoke(app, ["--json", "status"])

    assert result.exit_code == 3
    payload = json.loads(result.stdout)
    assert payload["error"]["code"] == "E_TIMEOUT"


def test_status_http_500_returns_e_http_5xx(runner: CliRunner) -> None:
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        mock.get("/slicer/system/version").mock(
            return_value=httpx.Response(500, json={"message": "boom"})
        )

        result = runner.invoke(app, ["--json", "status"])

    assert result.exit_code == 2
    payload = json.loads(result.stdout)
    assert payload["error"]["code"] == "E_HTTP_5XX"
    assert payload["error"]["http_status"] == 500
    assert "boom" in payload["error"]["message"]
