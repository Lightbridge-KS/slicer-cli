"""Integration: DICOMweb endpoints against live Slicer (+ optional Orthanc).

Two tiers of tests here:

  - **Always-on** (just `SLICER_INTEGRATION=1`): exercise `dicom studies`
    against Slicer's local DB (which may be empty) and confirm `api routes`
    surfaces the §8.1 bug note. These never depend on external state.

  - **`@pytest.mark.requires_orthanc`**: end-to-end pull -> query -> fetch
    against a local Orthanc, using a developer-supplied test fixture
    (UIDs read from environment / `tests/integration/.env` — never
    hard-coded, since real DICOM UIDs are PHI). The autouse fixture in
    `conftest.py` skips these cleanly if Orthanc DICOMweb isn't reachable
    or if the test-fixture env vars aren't set.

Required env vars (loaded from `tests/integration/.env` if present):

  SLCLI_TEST_ORTHANC_URL          e.g. http://localhost:8042
  SLCLI_TEST_STUDY_UID            real DICOM StudyInstanceUID in the Orthanc fixture
  SLCLI_TEST_SERIES_UID           real SeriesInstanceUID belonging to that study
  SLCLI_TEST_SOP_UID              real SOPInstanceUID in that series
  SLCLI_TEST_PATIENT_NAME_SUBSTR  substring expected in patient_name (e.g. surname)

See `tests/integration/.env.example` for the template.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from slicer_cli.cli.app import app

pytestmark = pytest.mark.integration


def _gated() -> bool:
    return os.environ.get("SLICER_INTEGRATION", "") not in {"", "0", "false", "False"}


def _fixture_env() -> dict[str, str] | None:
    """Return the test-fixture env dict, or None if any required var is missing."""
    keys = (
        "SLCLI_TEST_ORTHANC_URL",
        "SLCLI_TEST_STUDY_UID",
        "SLCLI_TEST_SERIES_UID",
        "SLCLI_TEST_SOP_UID",
        "SLCLI_TEST_PATIENT_NAME_SUBSTR",
    )
    values = {k: os.environ.get(k, "") for k in keys}
    if not all(values.values()):
        return None
    return values


def _require_fixture() -> dict[str, str]:
    env = _fixture_env()
    if env is None:
        pytest.skip(
            "Orthanc test-fixture env vars not set "
            "(see tests/integration/.env.example for SLCLI_TEST_* keys)."
        )
    return env


# --------------------------------------------------------------- Slicer-only


@pytest.mark.skipif(not _gated(), reason="set SLICER_INTEGRATION=1 to run")
def test_dicom_studies_against_live_slicer(runner: CliRunner) -> None:
    """`dicom studies` against an empty (or populated) Slicer DB returns a list."""
    result = runner.invoke(app, ["--json", "dicom", "studies"])

    assert result.exit_code == 0, result.stderr
    body = json.loads(result.stdout)
    assert "studies" in body
    assert isinstance(body["studies"], list)


@pytest.mark.skipif(not _gated(), reason="set SLICER_INTEGRATION=1 to run")
def test_api_routes_exposes_dicomweb_bug_note(runner: CliRunner) -> None:
    """The known §8.1 bug must be visible to agents via `api routes --json`."""
    result = runner.invoke(app, ["--json", "api", "routes"])

    assert result.exit_code == 0, result.stderr
    body = json.loads(result.stdout)
    matches = [r for r in body["routes"] if r["path"] == "/slicer/accessDICOMwebStudy"]
    assert len(matches) == 1
    assert matches[0]["note"] is not None
    assert "exec" in matches[0]["note"].lower()


# --------------------------------------------------------------- Orthanc round-trip


@pytest.mark.skipif(not _gated(), reason="set SLICER_INTEGRATION=1 to run")
@pytest.mark.requires_orthanc
def test_dicom_pull_then_query_round_trip(runner: CliRunner, tmp_path: Path) -> None:
    """Full Orthanc -> Slicer -> query -> WADO retrieve workflow with the test fixture.

    Skips cleanly if Orthanc DICOMweb plugin isn't installed (autouse fixture)
    or if the SLCLI_TEST_* fixture env vars aren't set. Also skips cleanly if
    Slicer's `/exec` is disabled (Slicer returns 5xx with the documented
    "unknown command" message).
    """
    env = _require_fixture()
    orthanc_url = env["SLCLI_TEST_ORTHANC_URL"]
    study_uid = env["SLCLI_TEST_STUDY_UID"]
    series_uid = env["SLCLI_TEST_SERIES_UID"]
    sop_uid = env["SLCLI_TEST_SOP_UID"]

    # 1. Pull the test study from Orthanc into Slicer's DB.
    pull = runner.invoke(
        app,
        [
            "--json",
            "dicom",
            "pull",
            "--orthanc",
            orthanc_url,
            "--study",
            study_uid,
        ],
    )
    if pull.exit_code != 0:
        body = json.loads(pull.stdout)
        if body.get("error", {}).get("code") == "E_HTTP_5XX":
            pytest.skip("/slicer/exec disabled — `dicom pull` cannot run end-to-end")
        raise AssertionError(f"pull failed: {pull.stdout}")

    pull_body = json.loads(pull.stdout)
    assert pull_body["imported_count"] is not None

    # 2. Confirm Slicer's DB now has the study.
    studies = runner.invoke(app, ["--json", "dicom", "studies"])
    assert studies.exit_code == 0, studies.stderr
    study_uids = {s["study_uid"] for s in json.loads(studies.stdout)["studies"]}
    assert study_uid in study_uids

    # 3. List series; the fixture series is expected.
    series_result = runner.invoke(app, ["--json", "dicom", "series", study_uid])
    assert series_result.exit_code == 0, series_result.stderr
    series_uids = {s["series_uid"] for s in json.loads(series_result.stdout)["series"]}
    assert series_uid in series_uids

    # 4. List instances.
    inst_result = runner.invoke(app, ["--json", "dicom", "instances", study_uid, series_uid])
    assert inst_result.exit_code == 0, inst_result.stderr
    sop_uids = {i["sop_uid"] for i in json.loads(inst_result.stdout)["instances"]}
    assert sop_uid in sop_uids

    # 5. WADO-RS retrieve the actual DICOM file.
    out_path = tmp_path / "fixture.dcm"
    fetch = runner.invoke(
        app,
        [
            "--json",
            "dicom",
            "instance",
            study_uid,
            series_uid,
            sop_uid,
            "--out",
            str(out_path),
        ],
    )
    assert fetch.exit_code == 0, fetch.stderr
    fetch_body = json.loads(fetch.stdout)
    assert fetch_body["bytes"] > 0
    # DICOM files have the "DICM" magic at byte 128 (after the 128-byte preamble).
    raw = out_path.read_bytes()
    assert raw[128:132] == b"DICM"

    # 6. Metadata round-trip at study level.
    meta = runner.invoke(app, ["--json", "dicom", "meta", study_uid])
    assert meta.exit_code == 0, meta.stderr
    meta_body = json.loads(meta.stdout)
    assert meta_body["level"] == "study"
    assert isinstance(meta_body["meta"], list)


@pytest.mark.skipif(not _gated(), reason="set SLICER_INTEGRATION=1 to run")
@pytest.mark.requires_orthanc
def test_dicom_pull_then_studies_finds_patient(runner: CliRunner) -> None:
    """After pull, `dicom studies` shows a row whose patient_name contains the configured substring.

    Note: we do NOT use `--patient <name>` because that filter maps to
    QIDO's `?PatientID=…` (exact-match on the *MRN*), and a typical
    fixture's PatientID is a hospital MRN, not the patient name.
    Filtering by patient *name* substring is a client-side operation here.
    """
    env = _require_fixture()
    orthanc_url = env["SLCLI_TEST_ORTHANC_URL"]
    study_uid = env["SLCLI_TEST_STUDY_UID"]
    name_substr = env["SLCLI_TEST_PATIENT_NAME_SUBSTR"]

    pull = runner.invoke(
        app,
        [
            "--json",
            "dicom",
            "pull",
            "--orthanc",
            orthanc_url,
            "--study",
            study_uid,
        ],
    )
    if pull.exit_code != 0:
        body = json.loads(pull.stdout)
        if body.get("error", {}).get("code") == "E_HTTP_5XX":
            pytest.skip("/slicer/exec disabled — `dicom pull` cannot run end-to-end")
        raise AssertionError(f"pull failed unexpectedly: {pull.stdout}")

    result = runner.invoke(app, ["--json", "dicom", "studies"])
    assert result.exit_code == 0, result.stderr

    body = json.loads(result.stdout)
    names = [s["patient_name"] for s in body["studies"]]
    assert any(name and name_substr in name for name in names), (
        f"Expected to find a study with {name_substr!r} in patient_name; got {len(names)} studies"
    )


@pytest.mark.skipif(not _gated(), reason="set SLICER_INTEGRATION=1 to run")
@pytest.mark.requires_orthanc
def test_dicom_studies_patient_id_filter_is_exact_match(runner: CliRunner) -> None:
    """`--patient` is a DICOM-spec exact-match on PatientID (NOT a name substring).

    Locked-in expectation: passing the *patient name substring* as `--patient`
    returns 0 results, because QIDO's PatientID filter expects an MRN-style
    exact match. This documents Slicer's QIDO semantics for agents using the CLI.
    """
    env = _require_fixture()
    orthanc_url = env["SLCLI_TEST_ORTHANC_URL"]
    study_uid = env["SLCLI_TEST_STUDY_UID"]
    name_substr = env["SLCLI_TEST_PATIENT_NAME_SUBSTR"]

    runner.invoke(
        app,
        [
            "--json",
            "dicom",
            "pull",
            "--orthanc",
            orthanc_url,
            "--study",
            study_uid,
        ],
    )
    # The substring is the patient *name*, not the *ID* — must return 0.
    result = runner.invoke(app, ["--json", "dicom", "studies", "--patient", name_substr])
    assert result.exit_code == 0, result.stderr
    body = json.loads(result.stdout)
    assert body["studies"] == []
