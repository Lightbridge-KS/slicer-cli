"""Integration: `slicer-cli exec` against live Slicer.

Skips cleanly if /slicer/exec is gated off in the user's Slicer build.
The test runs a tiny payload that returns a known string so we can assert
on round-trip without depending on Slicer's internal state.
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
def test_exec_code_round_trip(runner: CliRunner) -> None:
    """`exec --code 'X'` returns Slicer's parsed __execResult."""
    result = runner.invoke(
        app,
        [
            "--json",
            "exec",
            "--code",
            "__execResult = {'msg': 'hello-from-slicer-cli', 'two': 1 + 1}",
        ],
    )
    if result.exit_code != 0:
        body = json.loads(result.stdout)
        if body.get("error", {}).get("code") == "E_HTTP_5XX":
            pytest.skip("/slicer/exec disabled — cannot run end-to-end")
        raise AssertionError(f"exec failed: {result.stdout}")

    body = json.loads(result.stdout)
    assert body["result"]["msg"] == "hello-from-slicer-cli"
    assert body["result"]["two"] == 2
