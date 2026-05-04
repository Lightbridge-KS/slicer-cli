"""Shared base for every Slicer response model."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class _SlicerModel(BaseModel):
    """Tolerant of unknown fields — Slicer's schema can drift between releases."""

    model_config = ConfigDict(extra="ignore", frozen=True, populate_by_name=True)
