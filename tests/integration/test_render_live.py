"""Integration: render endpoints against live Slicer with MRHead loaded."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from slicer_cli.cli.app import app

pytestmark = pytest.mark.integration


def _gated() -> bool:
    return os.environ.get("SLICER_INTEGRATION", "") not in {"", "0", "false", "False"}


@pytest.mark.skipif(not _gated(), reason="set SLICER_INTEGRATION=1 to run")
def test_render_slice_writes_real_png(runner: CliRunner, tmp_path: Path) -> None:
    out_path = tmp_path / "red.png"
    result = runner.invoke(
        app, ["--json", "render", "slice", "--out", str(out_path), "--view", "red"]
    )

    assert result.exit_code == 0, result.stderr
    body = json.loads(result.stdout)
    assert body["bytes"] > 1000  # MRHead slice is comfortably larger
    assert out_path.exists()
    assert out_path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


@pytest.mark.skipif(not _gated(), reason="set SLICER_INTEGRATION=1 to run")
def test_render_threed_anterior_view(runner: CliRunner, tmp_path: Path) -> None:
    out_path = tmp_path / "threed_a.png"
    result = runner.invoke(
        app, ["--json", "render", "threed", "--out", str(out_path), "--look", "A"]
    )

    assert result.exit_code == 0, result.stderr
    assert out_path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


@pytest.mark.skipif(not _gated(), reason="set SLICER_INTEGRATION=1 to run")
def test_render_screenshot(runner: CliRunner, tmp_path: Path) -> None:
    """Screenshot needs Slicer's main window — assumed alive in this dev setup."""
    out_path = tmp_path / "shot.png"
    result = runner.invoke(app, ["--json", "render", "screenshot", "--out", str(out_path)])

    assert result.exit_code == 0, result.stderr
    assert out_path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


@pytest.mark.skipif(not _gated(), reason="set SLICER_INTEGRATION=1 to run")
def test_render_gltf(runner: CliRunner, tmp_path: Path) -> None:
    """Slicer 5.11 returns JSON glTF (~10 KB); validate_binary >= 1024 accepts it."""
    out_path = tmp_path / "scene.gltf"
    result = runner.invoke(app, ["--json", "render", "gltf", "--out", str(out_path)])

    assert result.exit_code == 0, result.stderr
    body = json.loads(result.stdout)
    assert body["bytes"] >= 1024
    assert out_path.exists()
