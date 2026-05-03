"""Integration test: real Slicer with WebServer up.

Gated by env var so unit-test runs stay hermetic. Run with:

  SLICER_INTEGRATION=1 uv run pytest

If SLICER_URL is set, that overrides the default localhost:2016 (e.g., for
reaching a remote Slicer through an SSH tunnel).
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
def test_status_live(runner: CliRunner) -> None:
    args = ["--json"]
    if url := os.environ.get("SLICER_URL"):
        args += ["--url", url]
    args.append("status")

    result = runner.invoke(app, args)

    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["applicationName"] == "Slicer"
