"""`slicer-cli sample list / load` — offline + Slicer-mocked."""

from __future__ import annotations

import json

import respx
from httpx import Response
from typer.testing import CliRunner

from slicer_cli.cli.app import app
from slicer_cli.cli.mrml.sample import CURATED_SAMPLES


def test_sample_list_returns_curated(runner: CliRunner) -> None:
    result = runner.invoke(app, ["--json", "sample", "list"])

    assert result.exit_code == 0, result.stderr
    body = json.loads(result.stdout)
    assert body["ok"] is True
    assert len(body["samples"]) == len(CURATED_SAMPLES)
    names = [s["name"] for s in body["samples"]]
    assert "MRHead" in names
    assert "CTAAbdomenPanoramix" in names
    # Each entry has both name and description fields
    assert all("description" in s for s in body["samples"])


def test_sample_list_pretty_includes_mrhead(runner: CliRunner) -> None:
    result = runner.invoke(app, ["--pretty", "sample", "list"])
    assert result.exit_code == 0
    assert "MRHead" in result.stdout
    assert "T1-weighted" in result.stdout


def test_sample_load_happy_path(runner: CliRunner) -> None:
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        route = mock.get("/slicer/sampledata", params={"name": "CTHead"}).mock(
            return_value=Response(200, text="loaded CTHead")
        )
        result = runner.invoke(app, ["--json", "sample", "load", "CTHead"])

    assert result.exit_code == 0, result.stderr
    assert route.called
    body = json.loads(result.stdout)
    assert body["name"] == "CTHead"
    assert "loaded" in body["response"].lower()


def test_sample_load_4xx_for_unknown(runner: CliRunner) -> None:
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        mock.get("/slicer/sampledata").mock(
            return_value=Response(400, json={"message": "no such sample"})
        )
        result = runner.invoke(app, ["--json", "sample", "load", "BogusSample"])

    assert result.exit_code == 2
    body = json.loads(result.stdout)
    assert body["error"]["code"] == "E_HTTP_4XX"
    assert body["error"]["http_status"] == 400


def test_sample_load_empty_name_blocked(runner: CliRunner) -> None:
    """Empty sample name is rejected at the client layer (E_BAD_INPUT)."""
    with respx.mock(base_url="http://127.0.0.1:2016", assert_all_called=False):
        result = runner.invoke(app, ["--json", "sample", "load", "   "])

    assert result.exit_code == 1
    body = json.loads(result.stdout)
    assert body["error"]["code"] == "E_BAD_INPUT"
