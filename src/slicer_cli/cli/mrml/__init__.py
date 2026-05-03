"""MRML-flavored command groups (scene, node, volume, sample, markup).

These groups all manipulate `vtkMRMLNode`-derived state. They share helpers
in `_helpers.py` for empty-selector validation, class-filter parsing, and
node-table formatting. Each leaf module exports its own Typer `app`,
registered at the *root* by `cli/app.py` (so the user-facing surface stays
flat: `slicer-cli scene ...`, `slicer-cli volume ...`, not nested).
"""
