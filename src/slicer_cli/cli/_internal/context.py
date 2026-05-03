"""Shared CLI execution context — config + output mode + client factory."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from slicer_cli.client.base import SlicerClient
from slicer_cli.config import AppConfig, load_config
from slicer_cli.output import OutputMode


@dataclass(frozen=True, slots=True)
class CliContext:
    """Resolved per-invocation state. Lives on `typer.Context.obj`."""

    config: AppConfig
    output_mode: OutputMode

    def make_client(self) -> SlicerClient:
        """Build a SlicerClient with config-derived defaults."""
        return SlicerClient(
            url=self.config.server.url,
            timeout=self.config.server.timeout_seconds,
        )


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
