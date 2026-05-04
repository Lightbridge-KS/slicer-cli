"""MRML scene/node endpoints — every `/slicer/mrml*` path.

This is the bulk of Slicer's HTTP surface: scene listing, property dumps,
file load (any node type), per-node save, delete, scene wipe, reload from
disk, and the templated `save_scene` (which technically goes through
`/slicer/exec` — see method docstring).

`LOAD_FILETYPES` lives here because `load_file` validates against it; tests
and the CLI's `volume import` both look it up via this module.
"""

from __future__ import annotations

from typing import Any

from slicer_cli.client._internal.exec import build_exec_payload
from slicer_cli.client._internal.http import _HttpClient
from slicer_cli.client._internal.id_helpers import attach_class_to_refs
from slicer_cli.client.errors import (
    SlicerBadInputError,
    SlicerBadResponseError,
)
from slicer_cli.client.models import DeleteResult, LoadResult, NodeRef

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


class MrmlMixin(_HttpClient):
    """All `/slicer/mrml*` operations."""

    # ------------------------------------------------------------- listing

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

    # ------------------------------------------------------------- load / save

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

    def save_scene(self, path: str) -> dict[str, Any]:
        """Save the entire MRML scene to `path`.

        Slicer's WebServer has no native "save scene" endpoint, so we route
        through the audited `_post_exec` funnel with a templated
        `slicer.util.saveScene` payload. The audit log records every
        invocation per PRD §8.3 when the client is constructed with an
        `AuditLogger`.
        """
        if not path.strip():
            raise SlicerBadInputError("path must not be empty")
        endpoint = "/slicer/exec"
        template = (
            "import slicer\n"
            "saved = slicer.util.saveScene({path})\n"
            "__execResult = {{'saved': bool(saved), 'path': {path}}}\n"
        )
        body = build_exec_payload(template, path=path)
        response = self._post_exec(body, op_label="mrml.save_scene")
        data = self._parse_json(response, endpoint=endpoint)
        if not isinstance(data, dict):
            raise SlicerBadResponseError(
                f"Expected JSON object from {endpoint}, got {type(data).__name__}",
                endpoint=endpoint,
            )
        return data

    # ------------------------------------------------------------- mutate / delete

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

    # ------------------------------------------------------------- internal

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
