"""Sample-data endpoint — `/slicer/sampledata`."""

from __future__ import annotations

from slicer_cli.client._internal.http import _HttpClient
from slicer_cli.client.errors import SlicerBadInputError


class SampleMixin(_HttpClient):
    """Trigger Slicer's SampleData module to download/load a known sample."""

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
