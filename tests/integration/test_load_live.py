"""Integration: load operations (sample load) against live Slicer.

`volume import` and `scene load` require a server-side file path Slicer can
read; integration tests for those are deferred until we have a fixture
strategy (out of MVP scope).
"""

from __future__ import annotations

import json
import os

import pytest
from typer.testing import CliRunner

from slicer_cli.cli.app import app

pytestmark = pytest.mark.integration


def _gated() -> bool:
    return os.environ.get("SLICER_INTEGRATION", "") not in {"", "0", "false", "False"}


@pytest.mark.skipif(not _gated(), reason="set SLICER_INTEGRATION=1 to run")
def test_sample_load_known_name(runner: CliRunner) -> None:
    """Load a curated sample. Mutates state — leaves an extra volume in the scene."""
    result = runner.invoke(app, ["--json", "sample", "load", "MRBrainTumor1"])

    assert result.exit_code == 0, result.stderr
    body = json.loads(result.stdout)
    assert body["ok"] is True
    assert body["name"] == "MRBrainTumor1"
    assert "loaded" in body["response"].lower()


@pytest.mark.skipif(not _gated(), reason="set SLICER_INTEGRATION=1 to run")
def test_sample_load_unknown_name_returns_5xx(runner: CliRunner) -> None:
    """Slicer returns 500 'sampledata X was not found' for unknown names."""
    result = runner.invoke(app, ["--json", "sample", "load", "DefinitelyNotASampleName"])

    assert result.exit_code == 2
    body = json.loads(result.stdout)
    assert body["error"]["code"] == "E_HTTP_5XX"
    assert "not found" in body["error"]["message"].lower()


@pytest.mark.skipif(not _gated(), reason="set SLICER_INTEGRATION=1 to run")
def test_sample_load_empty_name_blocked(runner: CliRunner) -> None:
    """Empty sample name is rejected at the client layer (no HTTP call)."""
    result = runner.invoke(app, ["--json", "sample", "load", ""])

    assert result.exit_code == 1
    body = json.loads(result.stdout)
    assert body["error"]["code"] == "E_BAD_INPUT"
