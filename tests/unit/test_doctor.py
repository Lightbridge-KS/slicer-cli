"""`slicer-cli doctor` — capability matrix probe."""

from __future__ import annotations

import json

import respx
from httpx import Response
from typer.testing import CliRunner

from slicer_cli.cli.app import app


def _all_endpoints_up() -> respx.MockRouter:
    """Convenience: a healthy Slicer responds 200 to all 5 HTTP probes."""
    mock = respx.mock(base_url="http://127.0.0.1:2016", assert_all_called=False)
    mock.get("/slicer/system/version").mock(
        return_value=Response(
            200,
            json={"applicationName": "Slicer", "applicationVersion": "5.11.0"},
        )
    )
    mock.get("/slicer/volumes").mock(return_value=Response(200, json=[]))
    mock.get("/dicom/studies").mock(return_value=Response(200, json=[]))
    mock.post("/slicer/exec").mock(return_value=Response(200, json={"ok": True}))
    mock.get("/slicer/slice").mock(
        return_value=Response(
            200,
            content=b"\x89PNG\r\n\x1a\nfake-png-bytes",
            headers={"content-type": "image/png"},
        )
    )
    return mock


def test_doctor_all_green(runner: CliRunner) -> None:
    """Every probe passes against a fully-functional mock."""
    with _all_endpoints_up():
        result = runner.invoke(app, ["--json", "doctor"])

    assert result.exit_code == 0, result.stderr
    body = json.loads(result.stdout)
    names = [c["name"] for c in body["checks"]]
    # All six probes ran in the documented order.
    assert names == [
        "reachable",
        "slicer-api",
        "dicomweb",
        "power-tool-endpoint",
        "power-tool-gating",
        "render",
    ]
    assert all(c["ok"] for c in body["checks"]), body


def test_doctor_reports_partial_failure(runner: CliRunner) -> None:
    """One failing probe should not abort the rest — agents need the full map."""
    with respx.mock(base_url="http://127.0.0.1:2016", assert_all_called=False) as mock:
        mock.get("/slicer/system/version").mock(
            return_value=Response(
                200,
                json={"applicationName": "Slicer", "applicationVersion": "5.11.0"},
            )
        )
        mock.get("/slicer/volumes").mock(return_value=Response(200, json=[]))
        # DICOMweb is off → 5xx.
        mock.get("/dicom/studies").mock(return_value=Response(500))
        # /exec is off → 5xx (matches user's actual environment).
        mock.post("/slicer/exec").mock(return_value=Response(500, json={"message": "no exec"}))
        mock.get("/slicer/slice").mock(
            return_value=Response(
                200,
                content=b"\x89PNG\r\n\x1a\nfake",
                headers={"content-type": "image/png"},
            )
        )
        result = runner.invoke(app, ["--json", "doctor"])

    assert result.exit_code == 0  # doctor itself succeeds; individual checks may be FAIL
    body = json.loads(result.stdout)
    by_name = {c["name"]: c for c in body["checks"]}
    assert by_name["reachable"]["ok"] is True
    assert by_name["slicer-api"]["ok"] is True
    assert by_name["dicomweb"]["ok"] is False
    assert by_name["power-tool-endpoint"]["ok"] is False
    # Power-tool gating is local config (default true), independent of HTTP.
    assert by_name["power-tool-gating"]["ok"] is True
    assert by_name["render"]["ok"] is True


def test_doctor_when_slicer_is_down(runner: CliRunner) -> None:
    """When Slicer is unreachable, every HTTP probe FAILs cleanly (no exception)."""
    # No mock context — httpx will get a real connection refused, but we want
    # a deterministic test, so we simulate 'down' by having no routes match.
    # respx with assert_all_mocked=True would raise, so we use side_effect.
    with respx.mock(base_url="http://127.0.0.1:2016", assert_all_called=False) as mock:
        from httpx import ConnectError

        mock.route().mock(side_effect=ConnectError("connection refused"))
        result = runner.invoke(app, ["--json", "doctor"])

    assert result.exit_code == 0, result.stderr
    body = json.loads(result.stdout)
    by_name = {c["name"]: c for c in body["checks"]}
    assert by_name["reachable"]["ok"] is False
    # Local-only check is unaffected.
    assert by_name["power-tool-gating"]["ok"] is True
