"""Shared pytest fixtures."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from slicer_cli.cli.app import app


@pytest.fixture()
def runner() -> CliRunner:
    """Typer CliRunner — newer Click versions always separate stderr."""
    return CliRunner()


@pytest.fixture()
def slicer_app() -> object:
    """The root Typer app, for invocation in tests."""
    return app
