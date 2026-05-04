"""`slicer-cli gui layout` — unit tests.

Layout names are pass-through; tests assert on query-string round-trip and
error mapping for invalid `--contents`.
"""

from __future__ import annotations

import json

import respx
from httpx import Response
from typer.testing import CliRunner

from slicer_cli.cli.app import app


def test_gui_layout_happy_path(runner: CliRunner) -> None:
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        route = mock.put("/slicer/gui").mock(return_value=Response(200, json={"success": True}))
        result = runner.invoke(app, ["--json", "gui", "layout", "fourup"])

    assert result.exit_code == 0, result.stderr
    assert route.called
    qs = dict(route.calls.last.request.url.params.multi_items())
    assert qs["viewersLayout"] == "fourup"
    assert qs["contents"] == "full"
    body = json.loads(result.stdout)
    assert body["layout"] == "fourup"
    assert body["contents"] == "full"


def test_gui_layout_with_contents_viewers(runner: CliRunner) -> None:
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        route = mock.put("/slicer/gui").mock(return_value=Response(200, json={"success": True}))
        result = runner.invoke(
            app,
            ["--json", "gui", "layout", "oneup3d", "--contents", "viewers"],
        )

    assert result.exit_code == 0, result.stderr
    qs = dict(route.calls.last.request.url.params.multi_items())
    assert qs["viewersLayout"] == "oneup3d"
    assert qs["contents"] == "viewers"


def test_gui_layout_invalid_contents_blocked(runner: CliRunner) -> None:
    with respx.mock(base_url="http://127.0.0.1:2016", assert_all_called=False):
        result = runner.invoke(app, ["--json", "gui", "layout", "fourup", "--contents", "bogus"])
    assert result.exit_code == 1
    assert json.loads(result.stdout)["error"]["code"] == "E_BAD_INPUT"


def test_gui_layout_empty_layout_blocked(runner: CliRunner) -> None:
    with respx.mock(base_url="http://127.0.0.1:2016", assert_all_called=False):
        result = runner.invoke(app, ["--json", "gui", "layout", ""])
    assert result.exit_code == 1
    assert json.loads(result.stdout)["error"]["code"] == "E_BAD_INPUT"


def test_gui_layout_5xx_clean_error(runner: CliRunner) -> None:
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        mock.put("/slicer/gui").mock(return_value=Response(500))
        result = runner.invoke(app, ["--json", "gui", "layout", "fourup"])
    assert result.exit_code == 2
    assert json.loads(result.stdout)["error"]["code"] == "E_HTTP_5XX"
