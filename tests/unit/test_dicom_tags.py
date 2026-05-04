"""Unit tests for the DICOM JSON tag-extraction helpers."""

from __future__ import annotations

from slicer_cli.client.dicom.tags import (
    TAG_MODALITIES_IN_STUDY,
    TAG_PATIENT_NAME,
    TAG_STUDY_DATE,
    coerce_int,
    dicom_person_name,
    dicom_tag_value,
    dicom_value_list,
)


def test_dicom_tag_value_normal_string() -> None:
    blob = {TAG_STUDY_DATE: {"vr": "DA", "Value": ["20200123"]}}
    assert dicom_tag_value(blob, TAG_STUDY_DATE) == "20200123"


def test_dicom_tag_value_missing_tag_returns_default() -> None:
    assert dicom_tag_value({}, TAG_STUDY_DATE) is None
    assert dicom_tag_value({}, TAG_STUDY_DATE, default="?") == "?"


def test_dicom_tag_value_missing_value_key() -> None:
    blob = {TAG_STUDY_DATE: {"vr": "DA"}}  # no Value
    assert dicom_tag_value(blob, TAG_STUDY_DATE) is None


def test_dicom_tag_value_empty_list() -> None:
    blob = {TAG_STUDY_DATE: {"vr": "DA", "Value": []}}
    assert dicom_tag_value(blob, TAG_STUDY_DATE) is None


def test_dicom_tag_value_non_dict_entry() -> None:
    blob = {TAG_STUDY_DATE: "not-a-dict"}
    assert dicom_tag_value(blob, TAG_STUDY_DATE) is None


def test_dicom_value_list_multi_valued() -> None:
    blob = {TAG_MODALITIES_IN_STUDY: {"vr": "CS", "Value": ["CT", "MR", "PT"]}}
    assert dicom_value_list(blob, TAG_MODALITIES_IN_STUDY) == ["CT", "MR", "PT"]


def test_dicom_value_list_missing() -> None:
    assert dicom_value_list({}, TAG_MODALITIES_IN_STUDY) == []


def test_dicom_person_name_alphabetic() -> None:
    blob = {TAG_PATIENT_NAME: {"vr": "PN", "Value": [{"Alphabetic": "DOE^JOHN"}]}}
    assert dicom_person_name(blob) == "DOE^JOHN"


def test_dicom_person_name_no_alphabetic_returns_none() -> None:
    """Some PN values only have Ideographic/Phonetic — we don't fabricate."""
    blob = {TAG_PATIENT_NAME: {"vr": "PN", "Value": [{"Ideographic": "山田"}]}}
    assert dicom_person_name(blob) is None


def test_dicom_person_name_flat_string_fallback() -> None:
    """Some encoders flatten PN to a plain string — accept it."""
    blob = {TAG_PATIENT_NAME: {"vr": "PN", "Value": ["DOE^JOHN"]}}
    assert dicom_person_name(blob) == "DOE^JOHN"


def test_dicom_person_name_missing() -> None:
    assert dicom_person_name({}) is None


def test_coerce_int_from_int() -> None:
    assert coerce_int(7) == 7


def test_coerce_int_from_string() -> None:
    assert coerce_int("42") == 42


def test_coerce_int_from_invalid() -> None:
    assert coerce_int("not-a-number") is None
    assert coerce_int(None) is None
    assert coerce_int("") is None
