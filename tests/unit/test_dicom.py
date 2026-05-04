"""`slicer-cli dicom studies / series / instances / instance / meta` — unit tests.

Respx fixtures mirror the DICOM JSON Model (PS3.18 §F): each row is a dict
mapping 8-hex tag → `{"vr": "...", "Value": [...]}`. Person Name (VR=PN)
values are objects with an Alphabetic field.

All fixture UIDs use the DICOM-reserved `2.25.*` prefix (PS3.5 §B.2 — UUIDs
reformatted as decimal under root 2.25), which never collides with real
clinical UIDs. All names / IDs / accession numbers are synthetic.
"""

from __future__ import annotations

import json
from pathlib import Path

import respx
from httpx import Response
from typer.testing import CliRunner

from slicer_cli.cli.app import app

# Synthetic DICOM JSON fixture (no PHI; 2.25.* root per DICOM PS3.5 §B.2).
_TEST_STUDY_UID = "2.25.123456789012345678901234567890123456"
_TEST_SERIES_UID = "2.25.234567890123456789012345678901234567"
_TEST_SOP_UID = "2.25.345678901234567890123456789012345678"

_TEST_STUDY = {
    "00100010": {"vr": "PN", "Value": [{"Alphabetic": "TEST^PATIENT^^MR."}]},
    "00100020": {"vr": "LO", "Value": ["TEST001"]},
    "00080020": {"vr": "DA", "Value": ["20200101"]},
    "00081030": {"vr": "LO", "Value": ["CHEST (upright)"]},
    "00080050": {"vr": "SH", "Value": ["TEST-AN-001"]},
    "00080061": {"vr": "CS", "Value": ["CR"]},
    "0020000D": {"vr": "UI", "Value": [_TEST_STUDY_UID]},
}

_TEST_SERIES = {
    "0020000E": {"vr": "UI", "Value": [_TEST_SERIES_UID]},
    "00080060": {"vr": "CS", "Value": ["CR"]},
    "00200011": {"vr": "IS", "Value": [1]},
    "0008103E": {"vr": "LO", "Value": ["AP"]},
}

_TEST_INSTANCE = {
    "00080018": {"vr": "UI", "Value": [_TEST_SOP_UID]},
    "00200013": {"vr": "IS", "Value": [1]},
}


# --------------------------------------------------------------- studies


def test_dicom_studies_happy_path(runner: CliRunner) -> None:
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        mock.get("/dicom/studies").mock(return_value=Response(200, json=[_TEST_STUDY]))
        result = runner.invoke(app, ["--json", "dicom", "studies"])

    assert result.exit_code == 0, result.stderr
    body = json.loads(result.stdout)
    assert len(body["studies"]) == 1
    s = body["studies"][0]
    assert s["patient_name"] == "TEST^PATIENT^^MR."
    assert s["patient_id"] == "TEST001"
    assert s["study_uid"] == _TEST_STUDY_UID
    assert s["study_date"] == "20200101"
    assert s["accession_number"] == "TEST-AN-001"
    assert s["modalities_in_study"] == ["CR"]


def test_dicom_studies_filter_by_patient(runner: CliRunner) -> None:
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        route = mock.get("/dicom/studies", params={"PatientID": "TEST001"}).mock(
            return_value=Response(200, json=[_TEST_STUDY])
        )
        result = runner.invoke(app, ["--json", "dicom", "studies", "--patient", "TEST001"])

    assert result.exit_code == 0, result.stderr
    assert route.called


def test_dicom_studies_empty_db(runner: CliRunner) -> None:
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        mock.get("/dicom/studies").mock(return_value=Response(200, json=[]))
        result = runner.invoke(app, ["--json", "dicom", "studies"])

    assert result.exit_code == 0
    assert json.loads(result.stdout)["studies"] == []


def test_dicom_studies_5xx(runner: CliRunner) -> None:
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        mock.get("/dicom/studies").mock(return_value=Response(500))
        result = runner.invoke(app, ["--json", "dicom", "studies"])

    assert result.exit_code == 2
    assert json.loads(result.stdout)["error"]["code"] == "E_HTTP_5XX"


# --------------------------------------------------------------- series


def test_dicom_series_happy_path(runner: CliRunner) -> None:
    study_uid = _TEST_STUDY_UID
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        mock.get(f"/dicom/studies/{study_uid}/series").mock(
            return_value=Response(200, json=[_TEST_SERIES])
        )
        result = runner.invoke(app, ["--json", "dicom", "series", study_uid])

    assert result.exit_code == 0, result.stderr
    body = json.loads(result.stdout)
    assert len(body["series"]) == 1
    s = body["series"][0]
    assert s["modality"] == "CR"
    assert s["series_number"] == 1
    assert s["series_description"] == "AP"


def test_dicom_series_empty_uid_blocked(runner: CliRunner) -> None:
    with respx.mock(base_url="http://127.0.0.1:2016", assert_all_called=False):
        result = runner.invoke(app, ["--json", "dicom", "series", ""])
    assert result.exit_code == 1
    assert json.loads(result.stdout)["error"]["code"] == "E_BAD_INPUT"


def test_dicom_series_unknown_study_4xx(runner: CliRunner) -> None:
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        mock.get("/dicom/studies/bogus/series").mock(return_value=Response(404))
        result = runner.invoke(app, ["--json", "dicom", "series", "bogus"])

    assert result.exit_code == 2
    assert json.loads(result.stdout)["error"]["code"] == "E_HTTP_4XX"


# --------------------------------------------------------------- instances


def test_dicom_instances_happy_path(runner: CliRunner) -> None:
    study = _TEST_STUDY_UID
    series = _TEST_SERIES_UID
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        mock.get(f"/dicom/studies/{study}/series/{series}/instances").mock(
            return_value=Response(200, json=[_TEST_INSTANCE])
        )
        result = runner.invoke(app, ["--json", "dicom", "instances", study, series])

    assert result.exit_code == 0, result.stderr
    body = json.loads(result.stdout)
    assert len(body["instances"]) == 1
    i = body["instances"][0]
    assert i["sop_uid"] == _TEST_SOP_UID
    assert i["instance_number"] == 1


# --------------------------------------------------------------- instance (WADO-RS)


def test_dicom_instance_writes_dicom_file(runner: CliRunner, tmp_path: Path) -> None:
    study = "1.2.840.S"
    series = "1.2.840.E"
    sop = "1.2.840.I"
    out_path = tmp_path / "instance.dcm"
    # Real DICOM files have the "DICM" magic at byte 128 (after preamble).
    fake_dcm = b"\x00" * 128 + b"DICM" + b"\x00" * 1024
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        mock.get(f"/dicom/studies/{study}/series/{series}/instances/{sop}").mock(
            return_value=Response(200, content=fake_dcm)
        )
        result = runner.invoke(
            app,
            [
                "--json",
                "dicom",
                "instance",
                study,
                series,
                sop,
                "--out",
                str(out_path),
            ],
        )

    assert result.exit_code == 0, result.stderr
    body = json.loads(result.stdout)
    assert body["bytes"] == len(fake_dcm)
    assert body["format"] == "dicom"
    assert out_path.read_bytes() == fake_dcm


def test_dicom_instance_requires_out(runner: CliRunner) -> None:
    """Locked Q-D — same as `volume export` and `render slice`."""
    result = runner.invoke(app, ["--json", "dicom", "instance", "a", "b", "c"])
    assert result.exit_code == 2  # Typer missing-required-option


# --------------------------------------------------------------- meta variadic


def test_dicom_meta_study_level(runner: CliRunner) -> None:
    study = "1.2.840.X"
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        mock.get(f"/dicom/studies/{study}/metadata").mock(
            return_value=Response(200, json=[_TEST_STUDY])
        )
        result = runner.invoke(app, ["--json", "dicom", "meta", study])

    assert result.exit_code == 0, result.stderr
    body = json.loads(result.stdout)
    assert body["level"] == "study"
    assert len(body["meta"]) == 1


def test_dicom_meta_series_level(runner: CliRunner) -> None:
    study = "1.2.840.X"
    series = "1.2.840.Y"
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        mock.get(f"/dicom/studies/{study}/series/{series}/metadata").mock(
            return_value=Response(200, json=[_TEST_SERIES])
        )
        result = runner.invoke(app, ["--json", "dicom", "meta", study, series])

    assert result.exit_code == 0, result.stderr
    assert json.loads(result.stdout)["level"] == "series"


def test_dicom_meta_instance_level(runner: CliRunner) -> None:
    study, series, sop = "1.2.840.X", "1.2.840.Y", "1.2.840.Z"
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        mock.get(f"/dicom/studies/{study}/series/{series}/instances/{sop}/metadata").mock(
            return_value=Response(200, json=[_TEST_INSTANCE])
        )
        result = runner.invoke(app, ["--json", "dicom", "meta", study, series, sop])

    assert result.exit_code == 0, result.stderr
    assert json.loads(result.stdout)["level"] == "instance"


def test_dicom_meta_skip_series_with_sop_blocked(runner: CliRunner) -> None:
    """Cannot pass `dicom meta <study> "" <sop>` — must pass series before sop."""
    with respx.mock(base_url="http://127.0.0.1:2016", assert_all_called=False):
        # Typer treats a 3-positional invocation differently — use plain syntax.
        result = runner.invoke(
            app,
            [
                "--json",
                "dicom",
                "meta",
                "1.2.840.X",
                "",  # empty series_uid
                "1.2.840.Z",
            ],
        )
    # Series is empty string (truthy as positional, but client rejects empty UID).
    assert result.exit_code == 1
    assert json.loads(result.stdout)["error"]["code"] == "E_BAD_INPUT"


# --------------------------------------------------------------- bad response shape


def test_dicom_studies_returns_non_array(runner: CliRunner) -> None:
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        mock.get("/dicom/studies").mock(return_value=Response(200, json={"oops": "not a list"}))
        result = runner.invoke(app, ["--json", "dicom", "studies"])
    assert result.exit_code == 2
    assert json.loads(result.stdout)["error"]["code"] == "E_BAD_RESPONSE"


# --------------------------------------------------------------- DICOM tag helpers


def test_dicom_studies_handles_missing_tags(runner: CliRunner) -> None:
    """A study row with only StudyInstanceUID still produces a usable StudyRef."""
    minimal = {"0020000D": {"vr": "UI", "Value": ["1.2.840.M"]}}
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        mock.get("/dicom/studies").mock(return_value=Response(200, json=[minimal]))
        result = runner.invoke(app, ["--json", "dicom", "studies"])

    assert result.exit_code == 0, result.stderr
    body = json.loads(result.stdout)
    s = body["studies"][0]
    assert s["study_uid"] == "1.2.840.M"
    assert s["patient_name"] is None
    assert s["modalities_in_study"] == []


# --------------------------------------------------------------- dicom pull (Batch 3)


def test_dicom_pull_happy_path(runner: CliRunner) -> None:
    """Routes through /slicer/exec; returns the imported_count from the templated payload."""
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        route = mock.post("/slicer/exec").mock(
            return_value=Response(
                200,
                json={
                    "imported_count": 1,
                    "study_uid": _TEST_STUDY_UID,
                    "endpoint": "http://localhost:8042/dicom-web",
                },
            )
        )
        result = runner.invoke(
            app,
            [
                "--json",
                "dicom",
                "pull",
                "--orthanc",
                "http://localhost:8042",
                "--study",
                _TEST_STUDY_UID,
            ],
        )

    assert result.exit_code == 0, result.stderr
    assert route.called
    body = json.loads(result.stdout)
    assert body["imported_count"] == 1
    assert body["study_uid"] == _TEST_STUDY_UID
    assert body["endpoint"] == "http://localhost:8042/dicom-web"

    # Verify the templated /exec body really called DICOMUtils.importFromDICOMWeb
    # with our endpoint built as `prefix + "/" + store`.
    sent = route.calls.last.request.content.decode()
    assert "DICOMLib" in sent
    assert "importFromDICOMWeb" in sent
    assert "'http://localhost:8042/dicom-web'" in sent
    assert f"'{_TEST_STUDY_UID}'" in sent


def test_dicom_pull_explicit_store(runner: CliRunner) -> None:
    """User-supplied --store is appended to --orthanc as a subpath."""
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        route = mock.post("/slicer/exec").mock(
            return_value=Response(200, json={"imported_count": 1, "study_uid": "X"})
        )
        result = runner.invoke(
            app,
            [
                "--json",
                "dicom",
                "pull",
                "--orthanc",
                "http://localhost:8042",
                "--study",
                "X",
                "--store",
                "wado-rs",
            ],
        )

    assert result.exit_code == 0, result.stderr
    sent = route.calls.last.request.content.decode()
    assert "'http://localhost:8042/wado-rs'" in sent


def test_dicom_pull_empty_store_uses_prefix_as_is(runner: CliRunner) -> None:
    """`--store ""` means the user already gave the full DICOMweb base URL."""
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        route = mock.post("/slicer/exec").mock(
            return_value=Response(200, json={"imported_count": 1, "study_uid": "X"})
        )
        result = runner.invoke(
            app,
            [
                "--json",
                "dicom",
                "pull",
                "--orthanc",
                "http://localhost:8042/custom-dicomweb",
                "--study",
                "X",
                "--store",
                "",
            ],
        )

    assert result.exit_code == 0, result.stderr
    sent = route.calls.last.request.content.decode()
    assert "'http://localhost:8042/custom-dicomweb'" in sent


def test_dicom_pull_token_is_passed_through(runner: CliRunner) -> None:
    """When `--token` is set, the templated payload assigns it to _token."""
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        route = mock.post("/slicer/exec").mock(
            return_value=Response(200, json={"imported_count": 1, "study_uid": "X"})
        )
        result = runner.invoke(
            app,
            [
                "--json",
                "dicom",
                "pull",
                "--orthanc",
                "http://localhost:8042",
                "--study",
                "X",
                "--token",
                "secret-bearer-abc",
            ],
        )

    assert result.exit_code == 0, result.stderr
    sent = route.calls.last.request.content.decode()
    assert "_token = 'secret-bearer-abc'" in sent


def test_dicom_pull_empty_orthanc_blocked(runner: CliRunner) -> None:
    with respx.mock(base_url="http://127.0.0.1:2016", assert_all_called=False):
        result = runner.invoke(app, ["--json", "dicom", "pull", "--orthanc", "", "--study", "X"])
    assert result.exit_code == 1
    assert json.loads(result.stdout)["error"]["code"] == "E_BAD_INPUT"


def test_dicom_pull_empty_study_blocked(runner: CliRunner) -> None:
    with respx.mock(base_url="http://127.0.0.1:2016", assert_all_called=False):
        result = runner.invoke(
            app,
            [
                "--json",
                "dicom",
                "pull",
                "--orthanc",
                "http://localhost:8042",
                "--study",
                "",
            ],
        )
    assert result.exit_code == 1
    assert json.loads(result.stdout)["error"]["code"] == "E_BAD_INPUT"


def test_dicom_pull_when_exec_disabled_surfaces_5xx(runner: CliRunner) -> None:
    """When /slicer/exec is gated off in Slicer, the CLI surfaces a clean E_HTTP_5XX."""
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        mock.post("/slicer/exec").mock(
            return_value=Response(500, json={"message": "unknown command \"b'/exec'\""})
        )
        result = runner.invoke(
            app,
            [
                "--json",
                "dicom",
                "pull",
                "--orthanc",
                "http://localhost:8042",
                "--study",
                _TEST_STUDY_UID,
            ],
        )

    assert result.exit_code == 2
    body = json.loads(result.stdout)
    assert body["error"]["code"] == "E_HTTP_5XX"
    # Verifies the underlying /exec disabled path is the actual root cause.
    assert body["error"]["http_status"] == 500


def test_dicom_pull_orthanc_with_trailing_slash_normalized(runner: CliRunner) -> None:
    """`--orthanc http://localhost:8042/` → `http://localhost:8042/dicom-web` (no double slash)."""
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        route = mock.post("/slicer/exec").mock(
            return_value=Response(200, json={"imported_count": 1, "study_uid": "X"})
        )
        result = runner.invoke(
            app,
            [
                "--json",
                "dicom",
                "pull",
                "--orthanc",
                "http://localhost:8042/",
                "--study",
                "X",
            ],
        )

    assert result.exit_code == 0, result.stderr
    sent = route.calls.last.request.content.decode()
    assert "'http://localhost:8042/dicom-web'" in sent
    assert "//dicom-web" not in sent  # no accidental double slash
