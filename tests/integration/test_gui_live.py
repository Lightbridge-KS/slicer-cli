"""Integration: `gui layout` against live Slicer.

We switch to `oneup3d`, then immediately back to `fourup` to restore the
user's default. If the user had a non-fourup layout before the test, we
can't fully restore — document this in the test name so a reader knows.
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
def test_gui_layout_switch_then_restore_fourup(runner: CliRunner) -> None:
    """Switch layout twice; the second invocation restores the canonical default."""
    switch = runner.invoke(app, ["--json", "gui", "layout", "oneup3d"])
    assert switch.exit_code == 0, switch.stderr
    body = json.loads(switch.stdout)
    assert body["layout"] == "oneup3d"
    # Slicer should report success.
    assert body["result"].get("success") is True

    restore = runner.invoke(app, ["--json", "gui", "layout", "fourup"])
    assert restore.exit_code == 0, restore.stderr
