"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

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


@pytest.fixture()
def audit_log_path(tmp_path: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect `CliContext.make_audit_logger` to a per-test tmp file.

    Returns the audit log path so a test can assert on what got written. Tests
    that don't request this fixture still get the autouse redirect from
    `_redirect_audit_log_to_tmp` below — they just don't see the path.
    """
    log_path = Path(str(tmp_path)) / "audit.log"
    from slicer_cli.cli._internal.context import CliContext
    from slicer_cli.client._internal.audit import AuditLogger

    monkeypatch.setattr(
        CliContext,
        "make_audit_logger",
        lambda self: AuditLogger(path=log_path),
    )
    return log_path


@pytest.fixture(autouse=True)
def _redirect_audit_log_to_tmp(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Default audit-log redirect so unit tests don't litter the real ~/.local/state.

    Tests that need to inspect the audit output should request the
    `audit_log_path` fixture above, which overrides this with a per-test path.
    """
    session_dir = tmp_path_factory.mktemp("slicer_cli_audit", numbered=True)
    log_path = Path(str(session_dir)) / "audit.log"
    from slicer_cli.cli._internal.context import CliContext
    from slicer_cli.client._internal.audit import AuditLogger

    monkeypatch.setattr(
        CliContext,
        "make_audit_logger",
        lambda self: AuditLogger(path=log_path),
    )
