"""DICOMweb endpoints — `/dicom/studies/...` (QIDO + WADO-RS).

Slicer's DICOMweb implementation is sourced entirely from
`slicer.dicomDatabase` — anything not yet imported into Slicer's local DB is
invisible to these endpoints. The companion `dicom pull` command (Batch 3)
populates that DB from a remote DICOMweb peer (e.g., Orthanc).

QIDO responses use the DICOM JSON Model: each row is a dict mapping tag
strings to `{vr, Value}` blobs. We flatten the common tags into Pythonic
fields on `StudyRef` / `SeriesRef` / `InstanceRef` (see `models.py`) while
preserving the full blob in `.raw` for power-tool access.
"""

from __future__ import annotations

from typing import Any

from slicer_cli.client._internal.dicom_tags import (
    TAG_ACCESSION_NUMBER,
    TAG_INSTANCE_NUMBER,
    TAG_MODALITIES_IN_STUDY,
    TAG_MODALITY,
    TAG_PATIENT_ID,
    TAG_SERIES_DESCRIPTION,
    TAG_SERIES_INSTANCE_UID,
    TAG_SERIES_NUMBER,
    TAG_SOP_INSTANCE_UID,
    TAG_STUDY_DATE,
    TAG_STUDY_DESCRIPTION,
    TAG_STUDY_INSTANCE_UID,
    coerce_int,
    dicom_person_name,
    dicom_tag_value,
    dicom_value_list,
)
from slicer_cli.client._internal.exec_template import build_exec_payload
from slicer_cli.client._internal.http import _HttpClient
from slicer_cli.client.errors import SlicerBadInputError, SlicerBadResponseError
from slicer_cli.client.models import InstanceRef, SeriesRef, StudyRef


class DicomMixin(_HttpClient):
    """QIDO + WADO-RS read endpoints for Slicer's DICOM database."""

    # ------------------------------------------------------------- QIDO listing

    def list_studies(
        self,
        *,
        patient_id: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[StudyRef]:
        """QIDO: GET /dicom/studies → list[StudyRef]."""
        params: dict[str, Any] = {}
        if patient_id is not None:
            params["PatientID"] = patient_id
        if limit is not None:
            params["limit"] = str(limit)
        if offset is not None:
            params["offset"] = str(offset)

        endpoint = "/dicom/studies"
        rows = self._fetch_dicom_array(endpoint, params=params)
        return [_study_ref_from_blob(row) for row in rows]

    def list_series(self, study_uid: str) -> list[SeriesRef]:
        """QIDO: GET /dicom/studies/{studyUID}/series → list[SeriesRef]."""
        cleaned = self._require_uid(study_uid, "study_uid")
        endpoint = f"/dicom/studies/{cleaned}/series"
        rows = self._fetch_dicom_array(endpoint)
        return [_series_ref_from_blob(row, study_uid=cleaned) for row in rows]

    def list_instances(self, study_uid: str, series_uid: str) -> list[InstanceRef]:
        """QIDO: GET /dicom/studies/{studyUID}/series/{seriesUID}/instances."""
        s = self._require_uid(study_uid, "study_uid")
        se = self._require_uid(series_uid, "series_uid")
        endpoint = f"/dicom/studies/{s}/series/{se}/instances"
        rows = self._fetch_dicom_array(endpoint)
        return [_instance_ref_from_blob(row, study_uid=s, series_uid=se) for row in rows]

    # ------------------------------------------------------------- WADO-RS

    def download_instance(self, study_uid: str, series_uid: str, sop_uid: str) -> bytes:
        """WADO-RS: GET .../instances/{sopUID} → raw DICOM bytes.

        The response body is the DICOM file (Part-10) — caller writes it to disk
        or pipes it to a downstream tool.
        """
        s = self._require_uid(study_uid, "study_uid")
        se = self._require_uid(series_uid, "series_uid")
        so = self._require_uid(sop_uid, "sop_uid")
        endpoint = f"/dicom/studies/{s}/series/{se}/instances/{so}"
        response = self._request("GET", endpoint)
        return response.content

    # ------------------------------------------------------------- metadata (3 endpoints)

    def get_study_metadata(self, study_uid: str) -> list[dict[str, Any]]:
        """GET /dicom/studies/{studyUID}/metadata → DICOM JSON list.

        Returns a list (potentially of one element) per the DICOM JSON Model.
        """
        cleaned = self._require_uid(study_uid, "study_uid")
        endpoint = f"/dicom/studies/{cleaned}/metadata"
        return self._fetch_dicom_array(endpoint)

    def get_series_metadata(self, study_uid: str, series_uid: str) -> list[dict[str, Any]]:
        s = self._require_uid(study_uid, "study_uid")
        se = self._require_uid(series_uid, "series_uid")
        endpoint = f"/dicom/studies/{s}/series/{se}/metadata"
        return self._fetch_dicom_array(endpoint)

    def get_instance_metadata(
        self, study_uid: str, series_uid: str, sop_uid: str
    ) -> list[dict[str, Any]]:
        s = self._require_uid(study_uid, "study_uid")
        se = self._require_uid(series_uid, "series_uid")
        so = self._require_uid(sop_uid, "sop_uid")
        endpoint = f"/dicom/studies/{s}/series/{se}/instances/{so}/metadata"
        return self._fetch_dicom_array(endpoint)

    # ------------------------------------------------------------- pull (via /exec)

    def pull_from_dicomweb(
        self,
        *,
        prefix: str,
        study_uid: str,
        store: str = "dicom-web",
        access_token: str = "",
    ) -> dict[str, Any]:
        """Pull a study from a DICOMweb peer (e.g., Orthanc) into Slicer's DB.

        Routes through `/slicer/exec` calling `DICOMLib.DICOMUtils.importFromDICOMWeb`
        because the native `/slicer/accessDICOMwebStudy` endpoint has a hard
        Python `TypeError` bug (surface report §8.1: handler does
        `request = json.loads(...), b"application/json"` — that's a tuple —
        then `request["dicomWEBPrefix"]`).

        `prefix` should be the Orthanc base URL, e.g. `http://localhost:8042`.
        `store` is appended as a subpath unless empty (default `dicom-web` —
        Orthanc's default DICOMweb plugin route). Pass `store=""` if `prefix`
        already includes the full path.

        Phase 3 will retroactively gate this through the `exec` audit-log
        once that machinery lands; the `build_exec_payload` helper is the
        single migration point. (Same precedent as `mrml.save_scene`.)
        """
        cleaned_prefix = prefix.strip().rstrip("/")
        if not cleaned_prefix:
            raise SlicerBadInputError(
                "orthanc prefix must not be empty",
                hint="Pass --orthanc http://host:port (e.g., http://localhost:8042).",
            )
        cleaned_study = study_uid.strip()
        if not cleaned_study:
            raise SlicerBadInputError("study UID must not be empty")

        if store.strip():
            endpoint_url = f"{cleaned_prefix}/{store.strip().strip('/')}"
        else:
            endpoint_url = cleaned_prefix

        endpoint = "/slicer/exec"
        template = (
            "from DICOMLib import DICOMUtils\n"
            "_token = {access_token}\n"
            "loaded = DICOMUtils.importFromDICOMWeb(\n"
            "    dicomWebEndpoint={endpoint_url},\n"
            "    studyInstanceUID={study_uid},\n"
            "    accessToken=(_token if _token else None),\n"
            ")\n"
            "__execResult = {{\n"
            "    'imported_count': len(loaded or []),\n"
            "    'study_uid': {study_uid},\n"
            "    'endpoint': {endpoint_url},\n"
            "}}\n"
        )
        body = build_exec_payload(
            template,
            endpoint_url=endpoint_url,
            study_uid=cleaned_study,
            access_token=access_token,
        )
        response = self._post_exec(body, op_label="dicom.pull_from_dicomweb")
        data = self._parse_json(response, endpoint=endpoint)
        if not isinstance(data, dict):
            raise SlicerBadResponseError(
                f"Expected JSON object from {endpoint}, got {type(data).__name__}",
                endpoint=endpoint,
            )
        return data

    # ------------------------------------------------------------- internal helpers

    def _fetch_dicom_array(
        self, path: str, *, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """GET a QIDO endpoint expected to return a JSON array of tag-blob dicts."""
        data = self._get_json(path, params=params or None)
        if not isinstance(data, list):
            raise SlicerBadResponseError(
                f"Expected a JSON array from {path}, got {type(data).__name__}",
                endpoint=path,
            )
        for entry in data:
            if not isinstance(entry, dict):
                raise SlicerBadResponseError(
                    f"Expected dict entries from {path}, got {type(entry).__name__}",
                    endpoint=path,
                )
        return data

    @staticmethod
    def _require_uid(value: str, name: str) -> str:
        cleaned = (value or "").strip()
        if not cleaned:
            raise SlicerBadInputError(f"{name} must not be empty")
        return cleaned


# --------------------------------------------------------------- model factories


def _study_ref_from_blob(blob: dict[str, Any]) -> StudyRef:
    return StudyRef(
        study_uid=str(dicom_tag_value(blob, TAG_STUDY_INSTANCE_UID, default="")),
        patient_id=_str_or_none(dicom_tag_value(blob, TAG_PATIENT_ID)),
        patient_name=dicom_person_name(blob),
        study_date=_str_or_none(dicom_tag_value(blob, TAG_STUDY_DATE)),
        study_description=_str_or_none(dicom_tag_value(blob, TAG_STUDY_DESCRIPTION)),
        accession_number=_str_or_none(dicom_tag_value(blob, TAG_ACCESSION_NUMBER)),
        modalities_in_study=[
            str(m) for m in dicom_value_list(blob, TAG_MODALITIES_IN_STUDY) if m is not None
        ],
        raw=blob,
    )


def _series_ref_from_blob(blob: dict[str, Any], *, study_uid: str) -> SeriesRef:
    return SeriesRef(
        series_uid=str(dicom_tag_value(blob, TAG_SERIES_INSTANCE_UID, default="")),
        study_uid=study_uid,
        modality=_str_or_none(dicom_tag_value(blob, TAG_MODALITY)),
        series_number=coerce_int(dicom_tag_value(blob, TAG_SERIES_NUMBER)),
        series_description=_str_or_none(dicom_tag_value(blob, TAG_SERIES_DESCRIPTION)),
        raw=blob,
    )


def _instance_ref_from_blob(
    blob: dict[str, Any], *, study_uid: str, series_uid: str
) -> InstanceRef:
    return InstanceRef(
        sop_uid=str(dicom_tag_value(blob, TAG_SOP_INSTANCE_UID, default="")),
        series_uid=series_uid,
        study_uid=study_uid,
        instance_number=coerce_int(dicom_tag_value(blob, TAG_INSTANCE_NUMBER)),
        raw=blob,
    )


def _str_or_none(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value or None
    return str(value)
