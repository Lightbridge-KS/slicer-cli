"""Markup domain — fiducials, segmentations, and the templated line-markup helper.

Public re-exports: callers should `from slicer_cli.client.markup import ...`
unchanged from before the bundling.
"""

from __future__ import annotations

from slicer_cli.client.markup.mixin import MarkupMixin
from slicer_cli.client.markup.models import (
    FiducialNode,
    FiducialPoint,
    LineMarkupResult,
    MarkupRef,
    MarkupType,
    SegmentationNode,
)

__all__ = [
    "FiducialNode",
    "FiducialPoint",
    "LineMarkupResult",
    "MarkupMixin",
    "MarkupRef",
    "MarkupType",
    "SegmentationNode",
]
