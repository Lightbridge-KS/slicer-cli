"""`slicer-cli system shutdown` — destructive guard + happy path."""

from __future__ import annotations

import json

import respx
from httpx import Response
from typer.testing import CliRunner

from slicer_cli.cli.app import app


def test_system_shutdown_without_confirm_is_blocked(runner: CliRunner) -> None:
    """Without `--confirm`, the guard fires and no HTTP call is made."""
    with respx.mock(base_url="http://127.0.0.1:2016", assert_all_called=False):
        result = runner.invoke(app, ["--json", "system", "shutdown"])

    assert result.exit_code == 6
    body = json.loads(result.stdout)
    assert body["error"]["code"] == "E_DESTRUCTIVE"


def test_system_shutdown_with_confirm_calls_delete(runner: CliRunner) -> None:
    """With `--confirm`, the CLI issues DELETE /slicer/system."""
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        route = mock.delete("/slicer/system").mock(
            return_value=Response(200, json={"success": True})
        )
        result = runner.invoke(app, ["--json", "system", "shutdown", "--confirm"])

    assert result.exit_code == 0, result.stderr
    assert route.called
    body = json.loads(result.stdout)
    assert body["shutdown"] == {"success": True}
