"""HTTP plumbing shared by every client mixin.

`_HttpClient` is the only class that owns httpx state and knows how to map
httpx exceptions / non-2xx responses to `SlicerError` subclasses. Per-domain
mixins (`system`, `mrml`, `volume`, `sample`, `raw`) inherit from it and use
the protected helpers (`_request`, `_get_json`, `_parse_json`, `_validate`).

Sync (not async) is intentional: Slicer's WebServer is single-threaded inside
the Qt event loop, so concurrent requests serialize anyway. Sync also has a
much simpler test story with `respx`.
"""

from __future__ import annotations

from typing import Any, Self, TypeVar

import httpx
from pydantic import BaseModel

from slicer_cli.client._internal.audit import AuditLogger
from slicer_cli.client.errors import (
    SlicerBadResponseError,
    SlicerHttpError,
    SlicerNetworkError,
    SlicerNotRunningError,
    SlicerTimeoutError,
)

DEFAULT_TIMEOUT_S: float = 30.0
DEFAULT_URL: str = "http://127.0.0.1:2016"
EXEC_ENDPOINT: str = "/slicer/exec"

_M = TypeVar("_M", bound=BaseModel)


class _HttpClient:
    """Owns the httpx.Client and maps transport errors to SlicerError."""

    def __init__(
        self,
        url: str = DEFAULT_URL,
        *,
        timeout: float = DEFAULT_TIMEOUT_S,
        client: httpx.Client | None = None,
        audit_logger: AuditLogger | None = None,
    ) -> None:
        self.url = url.rstrip("/")
        self.timeout = timeout
        self._client = client or httpx.Client(base_url=self.url, timeout=timeout)
        self._owns_client = client is None
        self._audit_logger = audit_logger

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    # ------------------------------------------------------------- protected helpers

    def _get_json(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        response = self._request("GET", path, params=params)
        return self._parse_json(response, endpoint=path)

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        content: bytes | None = None,
        json_body: Any | None = None,
    ) -> httpx.Response:
        try:
            response = self._client.request(
                method,
                path,
                params=params,
                content=content,
                json=json_body,
            )
        except httpx.ConnectError as exc:
            raise SlicerNotRunningError(self.url) from exc
        except httpx.TimeoutException as exc:
            raise SlicerTimeoutError(self.timeout, endpoint=path) from exc
        except httpx.RequestError as exc:
            raise SlicerNetworkError(str(exc), endpoint=path) from exc

        if response.status_code >= 400:
            raise SlicerHttpError(
                response.status_code,
                _http_error_message(response),
                endpoint=path,
            )
        return response

    def _post_exec(self, source: bytes, *, op_label: str) -> httpx.Response:
        """Single funnel for every POST to `/slicer/exec`.

        Writes one audit-log line via `self._audit_logger` (if set), THEN sends
        the POST. Audit-before-send so a successful audit precedes the actual
        side-effect; if Slicer crashes mid-call, we still know what was
        attempted.

        Every `/slicer/exec` caller (`mrml.save_scene`,
        `dicom.pull_from_dicomweb`, `markup.add_line`, `run_python`) MUST
        route through this method so audit logging has a single insertion
        point.
        """
        if self._audit_logger is not None:
            self._audit_logger.log(source, url=self.url, op_label=op_label)
        return self._request("POST", EXEC_ENDPOINT, content=source)

    def run_python(self, source: str | bytes, *, op_label: str = "cli.exec") -> Any:
        """POST `/slicer/exec` via the audited funnel; return the parsed `__execResult`.

        This is the public entry point for the formal `slicer-cli exec` command
        and any library caller that wants raw remote-Python access. Internal
        users (mrml.save_scene, dicom.pull_from_dicomweb, markup.add_line)
        own their templates; they call `_post_exec` directly with the
        already-built body.
        """
        body = source.encode("utf-8") if isinstance(source, str) else source
        response = self._post_exec(body, op_label=op_label)
        return self._parse_json(response, endpoint=EXEC_ENDPOINT)

    @staticmethod
    def _parse_json(response: httpx.Response, *, endpoint: str) -> Any:
        try:
            return response.json()
        except ValueError as exc:
            raise SlicerBadResponseError(
                f"Expected JSON from {endpoint}, got {response.headers.get('content-type', '?')}",
                endpoint=endpoint,
            ) from exc

    @staticmethod
    def _validate(model_cls: type[_M], data: Any, *, endpoint: str) -> _M:
        try:
            return model_cls.model_validate(data)
        except Exception as exc:  # pydantic validation
            raise SlicerBadResponseError(
                f"Could not parse {endpoint} response: {exc}",
                endpoint=endpoint,
            ) from exc


def _http_error_message(response: httpx.Response) -> str:
    """Extract a useful message from a Slicer error response."""
    try:
        body = response.json()
    except ValueError:
        return f"HTTP {response.status_code}: {response.text[:200]}"
    if isinstance(body, dict) and "message" in body:
        message = str(body["message"])
        return f"HTTP {response.status_code}: {message}"
    return f"HTTP {response.status_code}"
