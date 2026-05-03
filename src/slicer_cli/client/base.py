"""SlicerClient — composed from per-domain mixins.

The actual methods live in:
- `client/system.py`  — `/slicer/system*` (version, shutdown)
- `client/mrml.py`    — `/slicer/mrml*` (listing, load/save/delete, scene clear, save_scene via /exec)
- `client/volume.py`  — `/slicer/volume(s)` (list, NRRD download)
- `client/sample.py`  — `/slicer/sampledata`
- `client/raw.py`     — escape hatch for `api raw`
- `client/_http.py`   — shared httpx plumbing + error mapping (parent of every mixin)

Mixins all extend `_HttpClient`, so Python's MRO collapses to one shared
HTTP layer; `__init__` runs once. Adding a new endpoint family in Phase 2
means: (a) new file `client/<topic>.py` defining `<Topic>Mixin(_HttpClient)`,
(b) one extra parent in this class's bases list. No public-API churn.
"""

from __future__ import annotations

from slicer_cli.client._http import DEFAULT_TIMEOUT_S, DEFAULT_URL
from slicer_cli.client.mrml import LOAD_FILETYPES, MrmlMixin
from slicer_cli.client.raw import RawMixin
from slicer_cli.client.render import RenderMixin
from slicer_cli.client.sample import SampleMixin
from slicer_cli.client.system import SystemMixin
from slicer_cli.client.volume import VolumeMixin


class SlicerClient(
    SystemMixin,
    MrmlMixin,
    VolumeMixin,
    SampleMixin,
    RenderMixin,
    RawMixin,
):
    """Typed Slicer HTTP client. Use as a context manager or call .close().

    Composed from the per-domain mixins above. All methods are documented on
    their respective mixin classes; this class adds nothing of its own.
    """


__all__ = ["DEFAULT_TIMEOUT_S", "DEFAULT_URL", "LOAD_FILETYPES", "SlicerClient"]
