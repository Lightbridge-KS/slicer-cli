"""SlicerClient — sync httpx wrapper with typed error mapping.

Sync (not async) is intentional: Slicer's WebServer is single-threaded inside
the Qt event loop, so concurrent requests serialize anyway. Sync also has a
much simpler test story with respx (PRD §11).
"""

from __future__ import annotations

from typing import Any, TypeVar

import httpx
from pydantic import BaseModel

from slicer_cli.client._id_helpers import attach_class_to_refs
from slicer_cli.client.errors import (
    SlicerBadInputError,
    SlicerBadResponseError,
    SlicerHttpError,
    SlicerNetworkError,
    SlicerNotRunningError,
    SlicerTimeoutError,
)
from slicer_cli.client.models import DeleteResult, LoadResult, NodeRef, SystemVersion, Volume

# `filetype` values that POST /slicer/mrml accepts (per PRD Appendix A).
LOAD_FILETYPES: frozenset[str] = frozenset(
    {
        "VolumeFile",
        "SegmentationFile",
        "ModelFile",
        "MarkupsFile",
        "TransformFile",
        "TableFile",
        "TextFile",
        "SequenceFile",
        "SceneFile",
    }
)

DEFAULT_TIMEOUT_S: float = 30.0
DEFAULT_URL: str = "http://127.0.0.1:2016"

_M = TypeVar("_M", bound=BaseModel)


class SlicerClient:
    """Typed Slicer HTTP client. Use as a context manager or call .close()."""

    def __init__(
        self,
        url: str = DEFAULT_URL,
        *,
        timeout: float = DEFAULT_TIMEOUT_S,
        client: httpx.Client | None = None,
    ) -> None:
        self.url = url.rstrip("/")
        self.timeout = timeout
        self._client = client or httpx.Client(base_url=self.url, timeout=timeout)
        self._owns_client = client is None

    def __enter__(self) -> SlicerClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    # ------------------------------------------------------------------ public API

    def system_version(self) -> SystemVersion:
        """GET /slicer/system/version — the canonical liveness probe."""
        data = self._get_json("/slicer/system/version")
        return self._validate(SystemVersion, data, endpoint="/slicer/system/version")

    # ----- volumes / mrml listing (Phase 1) -------------------------------------

    def list_volumes(self) -> list[Volume]:
        """GET /slicer/volumes → list[Volume].

        Live response shape is `[{name, id}, …]` — no class field. Callers that
        need class info should derive via `_id_helpers.id_to_class`.
        """
        endpoint = "/slicer/volumes"
        data = self._get_json(endpoint)
        if not isinstance(data, list):
            raise SlicerBadResponseError(
                f"Expected a JSON array from {endpoint}, got {type(data).__name__}",
                endpoint=endpoint,
            )
        return [self._validate(Volume, item, endpoint=endpoint) for item in data]

    def list_node_ids(self, *, class_: str | None = None, name: str | None = None) -> list[str]:
        """GET /slicer/mrml/ids → flat list of MRML node ids."""
        return self._list_strings("/slicer/mrml/ids", class_=class_, name=name)

    def list_node_names(self, *, class_: str | None = None, name: str | None = None) -> list[str]:
        """GET /slicer/mrml/names → flat list of MRML node names (parallel to /ids)."""
        return self._list_strings("/slicer/mrml/names", class_=class_, name=name)

    def list_nodes(self, *, class_: str | None = None, name: str | None = None) -> list[NodeRef]:
        """Convenience: zip /mrml/ids + /mrml/names and decorate with class.

        Slicer doesn't expose a single endpoint that returns {id, name, class}
        triples, so we make two calls. They run serially because Slicer's
        WebServer is single-threaded.
        """
        ids = self.list_node_ids(class_=class_, name=name)
        names = self.list_node_names(class_=class_, name=name)
        return attach_class_to_refs(ids, names)

    def get_node_properties(self, node_id: str) -> dict[str, Any]:
        """GET /slicer/mrml/properties?id=… → property dict for one node.

        Slicer's serialization is best-effort and varies by node type, so we
        return the raw dict rather than a typed model. The response shape is
        `{nodeId: {…props…}}`; we unwrap to just the inner dict.
        """
        endpoint = "/slicer/mrml/properties"
        data = self._get_json(endpoint, params={"id": node_id})
        if not isinstance(data, dict) or node_id not in data:
            raise SlicerBadResponseError(
                f"Expected {{ {node_id!r}: {{...}} }} from {endpoint}, got {type(data).__name__}",
                endpoint=endpoint,
            )
        inner = data[node_id]
        if not isinstance(inner, dict):
            raise SlicerBadResponseError(
                f"Expected dict properties for {node_id}, got {type(inner).__name__}",
                endpoint=endpoint,
            )
        return inner

    # ----- load operations (Phase 1 Batch 3) ------------------------------------

    def load_sample(self, name: str) -> str:
        """GET /slicer/sampledata?name=… → text response.

        Slicer returns plain text (not JSON) — typically a status sentence. We
        return it verbatim and let the CLI surface it inside the JSON envelope.
        """
        if not name.strip():
            raise SlicerBadInputError("sample name must not be empty")
        endpoint = "/slicer/sampledata"
        response = self._request("GET", endpoint, params={"name": name})
        return response.text

    def load_file(
        self,
        *,
        filetype: str,
        localfile: str | None = None,
        url: str | None = None,
        extra_params: dict[str, str] | None = None,
    ) -> LoadResult:
        """POST /slicer/mrml?...&filetype=… → LoadResult with loadedNodeIDs.

        Exactly one of `localfile` (server-side path) or `url` must be set.
        `filetype` is validated against `LOAD_FILETYPES`.
        """
        if filetype not in LOAD_FILETYPES:
            raise SlicerBadInputError(
                f"Unknown filetype: {filetype!r}",
                hint=f"Expected one of: {', '.join(sorted(LOAD_FILETYPES))}",
            )
        if (localfile is None) == (url is None):
            raise SlicerBadInputError(
                "load_file requires exactly one of localfile or url",
            )

        params: dict[str, Any] = {"filetype": filetype}
        if localfile is not None:
            params["localfile"] = localfile
        if url is not None:
            params["url"] = url
        if extra_params:
            params.update(extra_params)

        endpoint = "/slicer/mrml"
        response = self._request("POST", endpoint, params=params)
        data = self._parse_json(response, endpoint=endpoint)
        return self._validate(LoadResult, data, endpoint=endpoint)

    # ----- export / save / reload (Phase 1 Batch 4) -----------------------------

    def download_volume(self, node_id: str) -> bytes:
        """GET /slicer/volume?id=… → raw NRRD bytes (octet-stream).

        Returns the response body as bytes; the caller decides whether to write
        to disk or stream to stdout.
        """
        if not node_id.strip():
            raise SlicerBadInputError("node_id must not be empty")
        endpoint = "/slicer/volume"
        response = self._request("GET", endpoint, params={"id": node_id})
        return response.content

    def save_node_to_file(
        self,
        node_id: str,
        *,
        localfile: str,
        use_compression: bool = True,
    ) -> dict[str, Any]:
        """GET /slicer/mrml/file?id=…&localfile=…&useCompression=… → status JSON.

        Slicer writes server-side; `localfile` must be a path readable+writable
        by the Slicer process. Compression is per-node-type (NRRD honours it).
        """
        if not node_id.strip():
            raise SlicerBadInputError("node_id must not be empty")
        endpoint = "/slicer/mrml/file"
        params = {
            "id": node_id,
            "localfile": localfile,
            "useCompression": "true" if use_compression else "false",
        }
        data = self._get_json(endpoint, params=params)
        if not isinstance(data, dict):
            raise SlicerBadResponseError(
                f"Expected JSON object from {endpoint}, got {type(data).__name__}",
                endpoint=endpoint,
            )
        return data

    def reload_node(self, node_id: str) -> dict[str, Any]:
        """PUT /slicer/mrml?id=… → reload selected node from its original file."""
        if not node_id.strip():
            raise SlicerBadInputError("node_id must not be empty")
        endpoint = "/slicer/mrml"
        response = self._request("PUT", endpoint, params={"id": node_id})
        data = self._parse_json(response, endpoint=endpoint)
        if not isinstance(data, dict):
            raise SlicerBadResponseError(
                f"Expected JSON object from {endpoint}, got {type(data).__name__}",
                endpoint=endpoint,
            )
        return data

    def save_scene(self, path: str) -> dict[str, Any]:
        """Save the entire MRML scene to `path`.

        Slicer's WebServer has no native "save scene" endpoint, so we use the
        Python power tool (`POST /slicer/exec`) with `slicer.util.saveScene`.
        Per locked Q-A: implement now via templated payload; Phase 3 will
        migrate this into the proper `exec` audit-log machinery.
        """
        if not path.strip():
            raise SlicerBadInputError("path must not be empty")
        endpoint = "/slicer/exec"
        # Use repr() to safely embed the path in Python source (handles quotes/escapes).
        body = (
            f"import slicer\n"
            f"saved = slicer.util.saveScene({path!r})\n"
            f"__execResult = {{'saved': bool(saved), 'path': {path!r}}}\n"
        ).encode()
        response = self._request("POST", endpoint, content=body)
        data = self._parse_json(response, endpoint=endpoint)
        if not isinstance(data, dict):
            raise SlicerBadResponseError(
                f"Expected JSON object from {endpoint}, got {type(data).__name__}",
                endpoint=endpoint,
            )
        return data

    # ----- destructive ops (Phase 1 Batch 5) ------------------------------------

    def delete_node(self, node_id: str) -> DeleteResult:
        """DELETE /slicer/mrml?id=… — delete a single node by id.

        Refuses empty ids at the *client* layer (defense-in-depth — the CLI
        layer also guards via require_nonempty_id, but a future Jupyter caller
        going straight to the client gets the same protection).
        """
        if not node_id.strip():
            raise SlicerBadInputError(
                "node_id must not be empty",
                hint="Empty selectors on DELETE /slicer/mrml clear the entire scene.",
            )
        endpoint = "/slicer/mrml"
        response = self._request("DELETE", endpoint, params={"id": node_id})
        data = self._parse_json(response, endpoint=endpoint)
        return self._validate(DeleteResult, data, endpoint=endpoint)

    def clear_scene(self) -> DeleteResult:
        """DELETE /slicer/mrml — wipe the entire scene.

        Explicit, no parameters. The caller is responsible for confirmation
        (the CLI layer enforces --confirm; the client does not, allowing
        direct library use after the caller has decided).
        """
        endpoint = "/slicer/mrml"
        response = self._request("DELETE", endpoint)
        data = self._parse_json(response, endpoint=endpoint)
        return self._validate(DeleteResult, data, endpoint=endpoint)

    def shutdown(self) -> dict[str, Any]:
        """DELETE /slicer/system — schedules `slicer.util.exit()` after 1s."""
        endpoint = "/slicer/system"
        response = self._request("DELETE", endpoint)
        data = self._parse_json(response, endpoint=endpoint)
        if not isinstance(data, dict):
            raise SlicerBadResponseError(
                f"Expected JSON object from {endpoint}, got {type(data).__name__}",
                endpoint=endpoint,
            )
        return data

    def raw(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        body: bytes | None = None,
    ) -> httpx.Response:
        """Escape hatch — issue an arbitrary HTTP request and return the raw Response.

        The CLI's `api raw` builds on this. Destructive guards (refusing empty
        DELETE on /slicer/mrml etc.) are enforced at the CLI layer using
        `client.routes.DESTRUCTIVE_RAW`, NOT here — direct library callers
        opt into raw access deliberately.
        """
        return self._request(method.upper(), path, params=params, content=body)

    # ------------------------------------------------------------- internal helpers

    def _list_strings(self, path: str, *, class_: str | None, name: str | None) -> list[str]:
        """Fetch a JSON-array-of-strings endpoint with optional class/name filters."""
        params: dict[str, Any] = {}
        if class_ is not None:
            params["class"] = class_
        if name is not None:
            params["name"] = name
        data = self._get_json(path, params=params or None)
        if not isinstance(data, list) or any(not isinstance(x, str) for x in data):
            raise SlicerBadResponseError(
                f"Expected a JSON array of strings from {path}, got {type(data).__name__}",
                endpoint=path,
            )
        return data

    @staticmethod
    def _validate(model_cls: type[_M], data: Any, *, endpoint: str) -> _M:
        try:
            return model_cls.model_validate(data)
        except Exception as exc:  # pydantic validation
            raise SlicerBadResponseError(
                f"Could not parse {endpoint} response: {exc}",
                endpoint=endpoint,
            ) from exc

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

    @staticmethod
    def _parse_json(response: httpx.Response, *, endpoint: str) -> Any:
        try:
            return response.json()
        except ValueError as exc:
            raise SlicerBadResponseError(
                f"Expected JSON from {endpoint}, got {response.headers.get('content-type', '?')}",
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
