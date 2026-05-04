"""Slicer-protocol helpers for working with MRML node ids.

Lives in `client/` because parsing the `vtkMRMLClassNameN` id format is
*protocol-level* knowledge — it would belong here even if there were no CLI.
The CLI layer imports these helpers; not the other way around.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from slicer_cli.client.mrml.models import NodeRef

# Node ids look like "vtkMRMLClassNameN" or "vtkMRMLClassNameSomeSuffix".
# Non-greedy capture stops at the *first* "Node" token. Verified against live
# Slicer 5.11.0 Preview's /slicer/mrml/ids output:
#   vtkMRMLScalarVolumeNode1            → vtkMRMLScalarVolumeNode
#   vtkMRMLViewNode1                    → vtkMRMLViewNode
#   vtkMRMLColorTableNodeFileMagma.txt  → vtkMRMLColorTableNode
#   vtkMRMLCrosshairNodedefault         → vtkMRMLCrosshairNode
#   vtkMRMLLayoutNodevtkMRMLLayoutNode  → vtkMRMLLayoutNode
_ID_CLASS_PATTERN = re.compile(r"^(vtkMRML[A-Z][A-Za-z0-9]*?Node)")


def id_to_class(node_id: str) -> str | None:
    """Extract the VTK class name from a Slicer MRML node id, or None if unparseable."""
    match = _ID_CLASS_PATTERN.match(node_id)
    return match.group(1) if match else None


def attach_class_to_refs(node_ids: Sequence[str], names: Sequence[str]) -> list[NodeRef]:
    """Zip parallel id+name lists (e.g. from /slicer/mrml/ids and /slicer/mrml/names)
    and decorate each with its class derived via `id_to_class`.

    Defensive: pairs only as many entries as the shorter list has.
    """
    pairs = zip(node_ids, names, strict=False)
    return [
        NodeRef.model_validate({"id": node_id, "name": name, "class": id_to_class(node_id)})
        for node_id, name in pairs
    ]
