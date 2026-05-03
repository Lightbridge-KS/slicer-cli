"""Escape-hatch — issue an arbitrary HTTP request and return the raw Response.

The CLI's `api raw` command builds on this. Destructive guards (e.g.
refusing empty DELETE on `/slicer/mrml`) are enforced at the *CLI* layer
using `client.routes.DESTRUCTIVE_RAW`, NOT here — direct library callers
opt into raw access deliberately.
"""

from __future__ import annotations

from typing import Any

import httpx

from slicer_cli.client._http import _HttpClient


class RawMixin(_HttpClient):
    """One method: `raw(method, path, ...)` returning the unwrapped httpx.Response."""

    def raw(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        body: bytes | None = None,
    ) -> httpx.Response:
        """Issue an arbitrary HTTP request and return the raw Response."""
        return self._request(method.upper(), path, params=params, content=body)
