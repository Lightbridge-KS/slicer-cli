"""MRML domain — `/slicer/mrml*` endpoints + the templated `save_scene`.

Public re-exports: callers should `from slicer_cli.client.mrml import ...`
unchanged from before the bundling. The internal layout (mixin / models /
id_helpers) is an implementation detail.
"""

from __future__ import annotations

from slicer_cli.client.mrml.id_helpers import attach_class_to_refs, id_to_class
from slicer_cli.client.mrml.mixin import LOAD_FILETYPES, MrmlMixin
from slicer_cli.client.mrml.models import DeleteResult, LoadResult, NodeRef

__all__ = [
    "LOAD_FILETYPES",
    "DeleteResult",
    "LoadResult",
    "MrmlMixin",
    "NodeRef",
    "attach_class_to_refs",
    "id_to_class",
]
