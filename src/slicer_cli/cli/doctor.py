"""`slicer-cli doctor` — capability matrix probe.

The doctor probes a battery of independent capabilities and reports
OK/FAIL per check. Each probe is wrapped so a single failing check
never aborts the whole run — agents need a complete map to decide what
they can / can't do against this Slicer.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import typer

from slicer_cli.cli._internal.context import CliContext
from slicer_cli.cli.output import render_success
from slicer_cli.client.base import SlicerClient
from slicer_cli.client.errors import SlicerError
from slicer_cli.config import AppConfig


@dataclass(frozen=True, slots=True)
class CheckResult:
    """One row in the doctor report."""

    name: str
    ok: bool
    detail: str


def doctor_command(ctx: typer.Context) -> None:
    """Run a battery of capability probes against Slicer and report the matrix."""
    cli_ctx: CliContext = ctx.obj
    with cli_ctx.make_client() as client:
        checks = run_checks(client, cli_ctx.config)

    payload = {"checks": [asdict(c) for c in checks]}
    render_success(payload, mode=cli_ctx.output_mode, renderer="doctor")


def run_checks(client: SlicerClient, config: AppConfig) -> list[CheckResult]:
    """Run all probes in order and return their results.

    Probes are independent — one failure does NOT short-circuit the rest.
    Reachability is run first because most other probes need the server up,
    but they each handle the down case themselves and report a clean FAIL.
    """
    return [
        _probe_reachable(client),
        _probe_slicer_api(client),
        _probe_dicomweb(client),
        _probe_power_tool_endpoint(client),
        _probe_power_tool_gating(config),
        _probe_render(client),
    ]


# ----------------------------------------------------------------- individual probes


def _probe_reachable(client: SlicerClient) -> CheckResult:
    """GET /slicer/system/version — confirms HTTP server is up."""
    try:
        version = client.system_version()
    except SlicerError as error:
        return CheckResult("reachable", False, _short(error.message))
    return CheckResult(
        "reachable",
        True,
        f"{version.application_name} {version.application_version or ''}".strip(),
    )


def _probe_slicer_api(client: SlicerClient) -> CheckResult:
    """GET /slicer/volumes — confirms the SlicerWebServer module is loaded."""
    try:
        volumes = client.list_volumes()
    except SlicerError as error:
        return CheckResult("slicer-api", False, _short(error.message))
    return CheckResult("slicer-api", True, f"{len(volumes)} volume(s) listed")


def _probe_dicomweb(client: SlicerClient) -> CheckResult:
    """GET /dicom/studies — confirms the DICOMweb endpoint group is enabled."""
    try:
        response = client.raw("GET", "/dicom/studies")
    except SlicerError as error:
        return CheckResult("dicomweb", False, _short(error.message))
    if response.status_code == 200:
        return CheckResult("dicomweb", True, "DICOMweb responded 200")
    return CheckResult("dicomweb", False, f"HTTP {response.status_code}")


def _probe_power_tool_endpoint(client: SlicerClient) -> CheckResult:
    """POST /slicer/exec — minimal ping; 200 means the power tool is enabled server-side."""
    try:
        response = client.raw("POST", "/slicer/exec", body=b"__execResult = {'ok': True}\n")
    except SlicerError as error:
        return CheckResult("power-tool-endpoint", False, _short(error.message))
    if response.status_code == 200:
        return CheckResult("power-tool-endpoint", True, "exec returned 200")
    return CheckResult(
        "power-tool-endpoint",
        False,
        f"HTTP {response.status_code} (exec disabled or unavailable)",
    )


def _probe_power_tool_gating(config: AppConfig) -> CheckResult:
    """Read `exec.enabled` from config — purely local, no HTTP."""
    enabled = bool(config.exec.enabled)
    return CheckResult(
        "power-tool-gating",
        enabled,
        "config exec.enabled = " + ("true" if enabled else "false"),
    )


def _probe_render(client: SlicerClient) -> CheckResult:
    """GET /slicer/slice — verify a non-empty PNG with non-zero dimensions comes back.

    Uses the same `validate_png` gate that real `render slice` does, so a green
    doctor probe means the actual render commands will succeed too.
    """
    from slicer_cli.client._internal.validators import validate_png

    try:
        response = client.raw("GET", "/slicer/slice", params={"size": "64"})
        validate_png(response.content, endpoint="/slicer/slice")
    except SlicerError as error:
        return CheckResult("render", False, _short(error.message))
    return CheckResult("render", True, f"PNG returned ({len(response.content)} bytes)")


# ----------------------------------------------------------------- helpers


def _short(message: str, *, limit: int = 80) -> str:
    """Trim long error messages so the doctor table stays readable."""
    if len(message) <= limit:
        return message
    return message[: limit - 1] + "…"
