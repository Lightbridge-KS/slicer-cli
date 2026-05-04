# `tests/` — testing guide

This file is symlinked from `CLAUDE.md` in the same directory.
Read [`/AGENTS.md`](../AGENTS.md) first for project-wide context; this file adds rules that apply only when editing tests under `tests/`.

## Layout

```
tests/
├── conftest.py            shared fixtures (currently: `runner`, `slicer_app`)
├── unit/                  hermetic, fast. respx mocks Slicer. No network.
└── integration/           hits real Slicer (and optionally Orthanc).
    ├── conftest.py        autouse Orthanc-probe + skip fixture
    └── test_*_live.py     feature-named files (NOT `test_phaseN_*`)
```

Run them with:

```
uv run pytest -m "not integration"        # unit only (default for CI)
SLICER_INTEGRATION=1 uv run pytest        # both — needs Slicer running with WebServer started
```

Tests marked `@pytest.mark.requires_orthanc` additionally need a local
Orthanc with the DICOMweb plugin at `http://localhost:8042`. They skip
cleanly otherwise (autouse fixture in `tests/integration/conftest.py`),
so you don't need to install Orthanc to run the suite.

## Patterns

### Mocking Slicer (unit tests)

Use `respx` to mock the HTTP surface. The base URL must match the client's `--url` (default `http://127.0.0.1:2016`).

```python
import respx
from httpx import Response
from typer.testing import CliRunner
from slicer_cli.cli.app import app

def test_x(runner: CliRunner) -> None:
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        mock.get("/slicer/system/version").mock(return_value=Response(200, json={...}))
        result = runner.invoke(app, ["--json", "status"])
    assert result.exit_code == 0
```

### Asserting on `E_*` codes

Always assert on `payload["error"]["code"]` (string) rather than the exception class. The string is the *public contract*; the class is internal. Same goes for exit codes — assert on the integer, not the `ErrorCode` enum.

### Invoking the CLI in tests

`runner.invoke(app, args)` calls Typer directly — it does **not** go through `hoist_global_flags()`. So in tests pass args in canonical Click order (`["--json", "status"]`, not `["status", "--json"]`). To exercise the hoister itself, `from slicer_cli.cli._internal.argv import hoist_global_flags` and assert on its output.

### Integration test gating

```python
import pytest

pytestmark = pytest.mark.integration

@pytest.mark.skipif(not _gated(), reason="set SLICER_INTEGRATION=1 to run")
def test_x_live(runner): ...
```

Two layers of gating because `pytest -m integration` *selects* by marker, but a developer running `pytest` without the marker filter still gets the skip behaviour.

### Test naming

`test_<unit>_<expectation>` — e.g., `test_status_connection_refused_returns_e_not_running`. Verbose is fine; agents and humans both scan the names.

## What tests should cover (per command, before the phase ticks done)

| Layer | Asserts |
|---|---|
| Unit (happy path) | exit 0, `ok=true`, expected payload fields, correct endpoint hit |
| Unit (4xx) | `E_HTTP_4XX`, exit 2, `http_status` field set |
| Unit (5xx) | `E_HTTP_5XX`, exit 2, `http_status` field set, message extracted from body |
| Unit (refused) | `E_NOT_RUNNING`, exit 3 |
| Unit (timeout) | `E_TIMEOUT`, exit 3 |
| Unit (destructive without confirm) | `E_DESTRUCTIVE`, exit 6, no HTTP call made |
| Unit (empty selector) | `E_EMPTY_SELECTOR`, exit 6, no HTTP call made |
| Integration | command runs end-to-end against live Slicer with a known scene state |

## Things to watch

- **`CliRunner`'s API moved.** Newer Click (8.2+) removed `mix_stderr=False` — `result.stderr` is always separate now. Don't pass `mix_stderr=` to the constructor.
- **Pydantic-settings reads from `os.environ` by default.** `tests/unit/test_config.py` passes an explicit `env={...}` so we don't pick up the developer's shell env. Always pass `env=` and `user_config_path=` in tests touching `load_config`.
- **Don't assert on rich-rendered pretty output beyond keyword presence.** Format may shift between rich versions; just check that the relevant strings appear.
- **`respx.mock(...)` as a context manager auto-asserts that all routes were called** if `assert_all_called=True` (default). If your test only triggers some routes, register the un-hit ones with `respx.route(...).pass_through()` or set `assert_all_called=False`.
- **`api raw` against a destructive `(method, path)` requires `--confirm`** (read from `client.routes.DESTRUCTIVE_RAW`). When testing happy-path `api raw` calls that hit destructive routes (`POST /slicer/exec`, `DELETE /slicer/mrml`, `DELETE /slicer/system`), pass `--confirm` in the args or the test fails with "RESPX: some routes were not called!".
- **Integration tests against destructive ops must never touch the user's session.** The pattern in `test_destructive_live.py` is: capture `scene ids` before, run a `sample load` of a *distinct* sample, capture `scene ids` after, and only `node delete` the *new* ids. Never call `scene clear` or `system shutdown` against live Slicer — only verify their `--confirm` guard fires.
- **Doctor's "down Slicer" test simulates failure with `respx ... .mock(side_effect=httpx.ConnectError(...))`** rather than absence-of-mock — the latter raises `RESPX: an unmocked request was made`, the former propagates a real `ConnectError` that the client maps to `E_NOT_RUNNING` so each probe degrades cleanly.
- **PNG fixture bytes must look like a real PNG to `validate_png`.** The validator checks magic + size >= 256 + IHDR width/height non-zero. Use the `_make_png(width, height, body_size)` helper in `test_render.py` / `test_doctor.py` to synthesize a valid header — a string like `b"\x89PNG\r\n\x1a\nfake"` will be rejected (zero IHDR dims), causing tests to fail with "PNG too small" instead of the case you meant to test.
- **Templated `/slicer/exec` payload tests must NOT run the rendered Python.** Use `ast.parse(rendered_source)` to confirm syntactic validity only; never evaluate the templated body — both because real evaluation would need Slicer's runtime AND because pre-commit hooks flag the relevant builtins. See `tests/unit/test_exec.py` for the parse-only pattern.
- **DICOM JSON fixtures should mirror PS3.18 §F shape.** Tag values are dicts: `{"vr": "...", "Value": [...]}`. PN values are objects: `{"Alphabetic": "..."}`. Empty / missing tags are common in the wild — `tests/unit/test_dicom_tags.py` covers the absence cases. When mocking QIDO endpoints, use the `_TEST_*` fixture shape from `test_dicom.py` as a starting point (synthetic data only — names, IDs, and UIDs in unit fixtures must never be real PHI; UIDs use the reserved `2.25.*` root per DICOM PS3.5 §B.2). Real DICOM UIDs for live integration tests are read from gitignored `tests/integration/.env` — see `.env.example`.
- **Orthanc round-trip integration tests should `pytest.skip` if the prerequisite (`dicom pull`) fails.** Slicer's `/slicer/exec` may be disabled in some environments; the test should detect `E_HTTP_5XX` from the pull and skip rather than asserting on downstream state. See `test_dicom_live.py::test_dicom_pull_then_query_round_trip` for the pattern.
