"""System-scope endpoints — `/slicer/system*`.

Flat domain (no sub-bundle): the response model `SystemVersion` is defined
inline below. See `src/slicer_cli/AGENTS.md` for the bundle-vs-flat threshold.
"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from slicer_cli.client._internal.http import _HttpClient
from slicer_cli.client._internal.models_base import _SlicerModel
from slicer_cli.client.errors import SlicerBadResponseError


class SystemVersion(_SlicerModel):
    """Response of GET /slicer/system/version (PRD Appendix A)."""

    application_name: str = Field(alias="applicationName")
    application_version: str = Field(alias="applicationVersion")
    application_display_name: str | None = Field(default=None, alias="applicationDisplayName")
    release_type: str | None = Field(default=None, alias="releaseType")
    revision: str | None = None
    arch: str | None = None
    os: str | None = None
    major_version: int | None = Field(default=None, alias="majorVersion")
    minor_version: int | None = Field(default=None, alias="minorVersion")


class SystemMixin(_HttpClient):
    """`/slicer/system/version` and `/slicer/system` shutdown."""

    def system_version(self) -> SystemVersion:
        """GET /slicer/system/version — the canonical liveness probe."""
        endpoint = "/slicer/system/version"
        data = self._get_json(endpoint)
        return self._validate(SystemVersion, data, endpoint=endpoint)

    def shutdown(self) -> dict[str, Any]:
        """DELETE /slicer/system — schedules `slicer.util.exit()` after 1 s."""
        endpoint = "/slicer/system"
        response = self._request("DELETE", endpoint)
        data = self._parse_json(response, endpoint=endpoint)
        if not isinstance(data, dict):
            raise SlicerBadResponseError(
                f"Expected JSON object from {endpoint}, got {type(data).__name__}",
                endpoint=endpoint,
            )
        return data
