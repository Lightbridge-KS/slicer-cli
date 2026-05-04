"""DICOM JSON Model tag IDs + value-extraction helpers.

DICOM JSON Model (PS3.18 §F) shapes every attribute as
`{"<tag>": {"vr": "<VR>", "Value": [<values>]}}`. Common tags:

  - String tags (LO, SH, UI, DA, …):  `Value: ["..."]`
  - Person Name (PN):                 `Value: [{"Alphabetic": "..."}]`
  - Multi-valued (CS for Modalities): `Value: ["CT", "MR"]`
  - Empty / absent:                   tag missing OR `Value` missing OR `[]`

The extraction helpers normalize all these into Pythonic `str | int | None`.
Lives next to `models.py` (NOT inside the `dicom` mixin) so `output.py` can
import it for pretty-rendering without crossing the cli → client boundary.
"""

from __future__ import annotations

from typing import Any

# 8-hex-digit tag keys per DICOM JSON Model.
TAG_PATIENT_NAME: str = "00100010"
TAG_PATIENT_ID: str = "00100020"
TAG_STUDY_DATE: str = "00080020"
TAG_STUDY_DESCRIPTION: str = "00081030"
TAG_ACCESSION_NUMBER: str = "00080050"
TAG_MODALITIES_IN_STUDY: str = "00080061"
TAG_STUDY_INSTANCE_UID: str = "0020000D"
TAG_SERIES_INSTANCE_UID: str = "0020000E"
TAG_SERIES_NUMBER: str = "00200011"
TAG_SERIES_DESCRIPTION: str = "0008103E"
TAG_MODALITY: str = "00080060"
TAG_SOP_INSTANCE_UID: str = "00080018"
TAG_INSTANCE_NUMBER: str = "00200013"


def dicom_tag_value(blob: dict[str, Any], tag: str, *, default: Any = None) -> Any:
    """Extract `Value[0]` from a DICOM JSON tag, handling absent / empty cases.

    Returns `default` if:
      - `tag` is missing from `blob`
      - the tag entry has no `Value` key
      - `Value` is an empty list
    """
    entry = blob.get(tag)
    if not isinstance(entry, dict):
        return default
    values = entry.get("Value")
    if not isinstance(values, list) or not values:
        return default
    return values[0]


def dicom_value_list(blob: dict[str, Any], tag: str) -> list[Any]:
    """Return the full `Value` list for multi-valued tags (e.g., ModalitiesInStudy).

    Returns `[]` if the tag is missing, has no `Value`, or `Value` is non-list.
    """
    entry = blob.get(tag)
    if not isinstance(entry, dict):
        return []
    values = entry.get("Value")
    if not isinstance(values, list):
        return []
    return values


def dicom_person_name(blob: dict[str, Any], tag: str = TAG_PATIENT_NAME) -> str | None:
    """Person Name (VR=PN) values are objects; return the Alphabetic representation.

    DICOM PN values look like `{"Alphabetic": "...", "Ideographic": "...", "Phonetic": "..."}`
    — most clinical data only sets `Alphabetic`. Returns None if no Alphabetic field.
    """
    raw = dicom_tag_value(blob, tag)
    if isinstance(raw, dict):
        alphabetic = raw.get("Alphabetic")
        if isinstance(alphabetic, str):
            return alphabetic
        return None
    if isinstance(raw, str):
        # Some encoders flatten PN values to a plain string.
        return raw
    return None


def coerce_int(value: Any) -> int | None:
    """Best-effort int coercion for tags like SeriesNumber / InstanceNumber."""
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return int(value)
        except ValueError:
            return None
    return None
