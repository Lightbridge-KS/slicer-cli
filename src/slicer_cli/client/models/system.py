"""Models for `/slicer/system*` responses."""

from __future__ import annotations

from pydantic import Field

from slicer_cli.client._internal.models_base import _SlicerModel


class SystemVersion(_SlicerModel):
    """Response of GET /slicer/system/version (PRD Appendix A)."""

    application_name: str = Field(alias="applicationName")
    application_version: str = Field(alias="applicationVersion")
    application_display_name: str | None = Field(default=None, alias="applicationDisplayName")
    release_type: str | None = Field(default=None, alias="releaseType")
    revision: str | None = None
    arch: str | None = None
    os: str | None = None
    major_version: int | None = Field(default=None, alias="majorVersion")
    minor_version: int | None = Field(default=None, alias="minorVersion")
