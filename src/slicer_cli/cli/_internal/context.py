"""Shared CLI execution context — config + output mode + client factory."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from slicer_cli.cli.output import OutputMode
from slicer_cli.client._internal.audit import AuditLogger
from slicer_cli.client.base import SlicerClient
from slicer_cli.config import AppConfig, load_config


@dataclass(frozen=True, slots=True)
class CliContext:
    """Resolved per-invocation state. Lives on `typer.Context.obj`."""

    config: AppConfig
    output_mode: OutputMode

    def make_client(self, *, disable_audit: bool = False) -> SlicerClient:
        """Build a SlicerClient with config-derived defaults.

        By default attaches an AuditLogger built from `config.exec.audit_log`
        so every internal `/slicer/exec` POST is audited (mrml.save_scene,
        dicom.pull_from_dicomweb, markup.add_line, formal exec). Pass
        `disable_audit=True` to opt out (used by `slicer-cli exec --no-audit-log`).
        """
        audit_logger = None if disable_audit else self.make_audit_logger()
        return SlicerClient(
            url=self.config.server.url,
            timeout=self.config.server.timeout_seconds,
            audit_logger=audit_logger,
        )

    def make_audit_logger(self) -> AuditLogger:
        """Construct an AuditLogger from `config.exec.audit_log` (path expanded)."""
        path = Path(self.config.exec.audit_log).expanduser()
        return AuditLogger(path=path)


def build_context(
    *,
    url: str | None,
    json_mode: bool,
    pretty_mode: bool,
    timeout: float | None,
) -> CliContext:
    """Merge CLI flags onto loaded config and pick the output mode."""
    overrides: dict[str, Any] = {}
    if url is not None:
        overrides.setdefault("server", {})["url"] = url
    if timeout is not None:
        overrides.setdefault("server", {})["timeout_seconds"] = timeout

    config = load_config(overrides=overrides)

    if json_mode and pretty_mode:
        # --json wins; --pretty is the default-equivalent flag.
        output_mode: OutputMode = "json"
    elif json_mode:
        output_mode = "json"
    elif pretty_mode:
        output_mode = "pretty"
    else:
        output_mode = "json" if config.output.default == "json" else "pretty"

    return CliContext(config=config, output_mode=output_mode)
