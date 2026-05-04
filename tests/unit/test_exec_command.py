"""`slicer-cli exec` — unit tests for gating, audit, and flag dispatch.

The command itself is a thin wrapper, but it has four distinct
behaviors to lock down:
  1. XOR validation of --code vs --file
  2. Gating against config.exec.enabled (env: SLICER_EXEC_ENABLED=false)
  3. --i-understand-the-risk override flag
  4. --no-audit-log emits a stderr warning AND skips the audit write
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import respx
from httpx import Response
from typer.testing import CliRunner

from slicer_cli.cli.app import app


def test_exec_code_happy_path_writes_audit(runner: CliRunner, audit_log_path: Path) -> None:
    """`exec --code '...'` POSTs the source and writes one audit line."""
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        route = mock.post("/slicer/exec").mock(
            return_value=Response(200, json={"value": 42, "ok": True})
        )
        result = runner.invoke(
            app,
            ["--json", "exec", "--code", "print(1); __execResult = {'value': 42, 'ok': True}"],
        )

    assert result.exit_code == 0, result.stderr
    assert route.called
    body = json.loads(result.stdout)
    assert body["result"]["value"] == 42

    sent = route.calls.last.request.content.decode()
    assert "__execResult" in sent

    audit = audit_log_path.read_text().rstrip("\n")
    assert "op=cli.exec" in audit


def test_exec_file_happy_path(runner: CliRunner, tmp_path: Path) -> None:
    script = tmp_path / "macro.py"
    script.write_text("__execResult = 'from-file'\n")
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        mock.post("/slicer/exec").mock(return_value=Response(200, json="from-file"))
        result = runner.invoke(app, ["--json", "exec", "--file", str(script)])

    assert result.exit_code == 0, result.stderr
    body = json.loads(result.stdout)
    assert body["result"] == "from-file"


def test_exec_xor_both_set_blocked(runner: CliRunner) -> None:
    with respx.mock(base_url="http://127.0.0.1:2016", assert_all_called=False):
        result = runner.invoke(
            app, ["--json", "exec", "--code", "x = 1", "--file", "/tmp/anything.py"]
        )
    assert result.exit_code == 1
    body = json.loads(result.stdout)
    assert body["error"]["code"] == "E_BAD_INPUT"
    assert "exactly one" in body["error"]["message"]


def test_exec_xor_neither_set_blocked(runner: CliRunner) -> None:
    with respx.mock(base_url="http://127.0.0.1:2016", assert_all_called=False):
        result = runner.invoke(app, ["--json", "exec"])
    assert result.exit_code == 1
    assert json.loads(result.stdout)["error"]["code"] == "E_BAD_INPUT"


def test_exec_file_nonexistent_blocked(runner: CliRunner, tmp_path: Path) -> None:
    with respx.mock(base_url="http://127.0.0.1:2016", assert_all_called=False):
        result = runner.invoke(
            app,
            ["--json", "exec", "--file", str(tmp_path / "nope.py")],
        )
    assert result.exit_code == 1
    body = json.loads(result.stdout)
    assert body["error"]["code"] == "E_BAD_INPUT"
    assert "Could not read --file" in body["error"]["message"]


def test_exec_disabled_without_override_blocked(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SLICER_EXEC_ENABLED=false → E_EXEC_DISABLED unless override flag is set."""
    monkeypatch.setenv("SLICER_EXEC_ENABLED", "false")
    with respx.mock(base_url="http://127.0.0.1:2016", assert_all_called=False):
        result = runner.invoke(app, ["--json", "exec", "--code", "x = 1"])
    assert result.exit_code == 5
    body = json.loads(result.stdout)
    assert body["error"]["code"] == "E_EXEC_DISABLED"
    assert "--i-understand-the-risk" in (body["error"]["hint"] or "")


def test_exec_disabled_with_override_proceeds(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SLICER_EXEC_ENABLED=false + --i-understand-the-risk → call goes through."""
    monkeypatch.setenv("SLICER_EXEC_ENABLED", "false")
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        route = mock.post("/slicer/exec").mock(return_value=Response(200, json="ok"))
        result = runner.invoke(
            app,
            [
                "--json",
                "exec",
                "--code",
                "__execResult = 'ok'",
                "--i-understand-the-risk",
            ],
        )

    assert result.exit_code == 0, result.stderr
    assert route.called


def test_exec_no_audit_log_skips_audit_and_warns(runner: CliRunner, audit_log_path: Path) -> None:
    """`--no-audit-log` writes a stderr warning AND does NOT touch the audit log file."""
    assert not audit_log_path.exists()
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        mock.post("/slicer/exec").mock(return_value=Response(200, json="ok"))
        result = runner.invoke(
            app,
            ["--json", "exec", "--code", "__execResult = 'ok'", "--no-audit-log"],
        )

    assert result.exit_code == 0, result.stderr
    # Audit file must NOT exist (no write).
    assert not audit_log_path.exists()
    # Stderr should carry a warning JSON line.
    assert '"warning"' in result.stderr
    assert "audit log skipped" in result.stderr
