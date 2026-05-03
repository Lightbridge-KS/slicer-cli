"""System-scope endpoints — `/slicer/system*`."""

from __future__ import annotations

from typing import Any

from slicer_cli.client._http import _HttpClient
from slicer_cli.client.errors import SlicerBadResponseError
from slicer_cli.client.models import SystemVersion


class SystemMixin(_HttpClient):
    """`/slicer/system/version` (Phase 0) and `/slicer/system` shutdown (Phase 1)."""

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
