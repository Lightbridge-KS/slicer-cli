"""Integration-test fixtures.

Orthanc gate
------------
`@pytest.mark.requires_orthanc` skips a test if a local Orthanc DICOMweb
endpoint isn't reachable. We probe `http://localhost:8042/dicom-web/studies`
once per test (cached via session-scope) and skip cleanly if:

  - Orthanc isn't running (connection refused / timeout)
  - The OrthancDicomWeb plugin isn't loaded (404 or non-JSON response)

Folded under `SLICER_INTEGRATION=1` per the locked Q-5 (no separate env var):
running the full integration suite requires Slicer; Orthanc-dependent tests
just bail when their backing service is missing.
"""

from __future__ import annotations

import os
from pathlib import Path

import httpx
import pytest

ORTHANC_URL: str = "http://localhost:8042"
ORTHANC_DICOMWEB_PROBE: str = f"{ORTHANC_URL}/dicom-web/studies"

# Test-fixture env vars (UIDs / names) live in tests/integration/.env which
# is gitignored — see .env.example for the keys. Real DICOM UIDs are PHI and
# must never be committed to a public repo.
_ENV_FILE = Path(__file__).with_name(".env")


def _load_env_file() -> None:
    """Bare-bones KEY=VALUE loader; missing file is a no-op. No quoting tricks."""
    if not _ENV_FILE.is_file():
        return
    for raw in _ENV_FILE.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        # Don't override anything already set in the real environment.
        os.environ.setdefault(key, value)


_load_env_file()


@pytest.fixture(scope="session")
def orthanc_dicomweb_available() -> bool:
    """Probe Orthanc once per session; True only if the DICOMweb endpoint responds 200."""
    try:
        response = httpx.get(ORTHANC_DICOMWEB_PROBE, timeout=2.0)
    except (httpx.ConnectError, httpx.TimeoutException, httpx.RequestError):
        return False
    return response.status_code == 200


@pytest.fixture(autouse=True)
def _skip_if_no_orthanc(request: pytest.FixtureRequest, orthanc_dicomweb_available: bool) -> None:
    """Auto-applied: tests marked `requires_orthanc` skip cleanly when DICOMweb is down."""
    if request.node.get_closest_marker("requires_orthanc") and not orthanc_dicomweb_available:
        pytest.skip(
            f"Orthanc DICOMweb plugin not reachable at {ORTHANC_DICOMWEB_PROBE} "
            "— install OrthancDicomWeb plugin and reload Orthanc to enable these tests."
        )
