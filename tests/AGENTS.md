# `tests/` — testing guide

Read [`/AGENTS.md`](../AGENTS.md) first for project-wide context. This file covers rules that apply when editing tests under `tests/`.

## Layout

```
tests/
├── conftest.py            shared fixtures: `runner`, `slicer_app`, `audit_log_path`
│                          (autouse: redirect audit-log writes to tmp)
├── unit/                  hermetic, fast. respx mocks Slicer. No network.
└── integration/           hits real Slicer (and optionally Orthanc).
    ├── conftest.py        autouse Orthanc-probe + skip fixture
    └── test_*_live.py     feature-named files (NOT `test_phaseN_*`)
```

Run them with:

```
uv run pytest -m "not integration"        # unit only (default for CI)
SLICER_INTEGRATION=1 uv run pytest        # both — needs Slicer running with WebServer
```

Tests marked `@pytest.mark.requires_orthanc` additionally need a local Orthanc with the DICOMweb plugin at `http://localhost:8042`. They skip cleanly otherwise.

## Patterns

### Mocking Slicer (unit tests)

Use `respx` to mock the HTTP surface. Base URL must match the client's `--url` (default `http://127.0.0.1:2016`).

```python
import respx
from httpx import Response
from slicer_cli.cli.app import app

def test_x(runner) -> None:
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        mock.get("/slicer/system/version").mock(return_value=Response(200, json={...}))
        result = runner.invoke(app, ["--json", "status"])
    assert result.exit_code == 0
```

### Asserting on `E_*` codes and exit codes

Always assert on `payload["error"]["code"]` (string) — that's the public contract. The exception class and `ErrorCode` enum are internal. Same for exit codes: assert on the integer.

### Invoking the CLI in tests

`runner.invoke(app, args)` calls Typer directly — it does **not** go through `hoist_global_flags()`. Pass args in canonical Click order (`["--json", "status"]`, not `["status", "--json"]`). To test the hoister itself, import `from slicer_cli.cli._internal.argv import hoist_global_flags` and assert on its output.

### Integration test gating

```python
import pytest
pytestmark = pytest.mark.integration

@pytest.mark.skipif(not _gated(), reason="set SLICER_INTEGRATION=1 to run")
def test_x_live(runner): ...
```

Two layers because `pytest -m integration` *selects* by marker, but a developer running plain `pytest` still gets the skip behaviour.

### Audit-log inspection

Audit writes are autouse-redirected to a tmp dir by `conftest.py::_redirect_audit_log_to_tmp`. To *inspect* the audit output, request the `audit_log_path: Path` fixture — it overrides the autouse redirect with a per-test path. For `--no-audit-log` tests, request the same fixture and assert `not audit_log_path.exists()` after the call.

```python
def test_my_caller_writes_audit(runner, audit_log_path):
    ...invoke...
    assert "op=mymodule.myop" in audit_log_path.read_text()
```

### Test naming

`test_<unit>_<expectation>` — e.g., `test_status_connection_refused_returns_e_not_running`. Verbose is fine; agents and humans both scan the names.

## Coverage matrix (per command, before phase ticks done)

| Layer | Asserts |
|---|---|
| Unit (happy path) | exit 0, `ok=true`, expected payload fields, correct endpoint hit |
| Unit (4xx / 5xx) | `E_HTTP_4XX` / `E_HTTP_5XX`, exit 2, `http_status` set |
| Unit (refused / timeout) | `E_NOT_RUNNING` / `E_TIMEOUT`, exit 3 |
| Unit (destructive without confirm) | `E_DESTRUCTIVE`, exit 6, no HTTP call made |
| Unit (empty selector) | `E_EMPTY_SELECTOR`, exit 6, no HTTP call made |
| Integration | runs end-to-end against live Slicer with a known scene state |

## Footguns

- **`CliRunner` API moved.** Newer Click (8.2+) removed `mix_stderr=False` — `result.stderr` is always separate. Don't pass `mix_stderr=` to the constructor.
- **Pydantic-settings reads `os.environ` by default.** Tests touching `load_config` must pass explicit `env={...}` and `user_config_path=` so they don't pick up the developer's shell.
- **Don't assert on rich-rendered pretty output beyond keyword presence.** Format may shift between rich versions; check that relevant strings appear, not exact layout.
- **`respx.mock(...)` auto-asserts all routes were called** if `assert_all_called=True` (default). For partial-coverage tests, use `respx.route(...).pass_through()` or `assert_all_called=False`.
- **`api raw` against destructive `(method, path)` requires `--confirm`** (see `client.routes.DESTRUCTIVE_RAW`). Happy-path tests against destructive routes (`POST /slicer/exec`, `DELETE /slicer/mrml`, `DELETE /slicer/system`) must pass `--confirm`, or you'll get "RESPX: some routes were not called!".
- **Integration tests against destructive ops must never touch the user's session.** Pattern in `test_destructive_live.py`: capture `scene ids` before, `sample load` a *distinct* sample, capture after, only `node delete` the *new* ids. Never call `scene clear` or `system shutdown` against live Slicer — only verify their `--confirm` guard fires.
- **Doctor's "down Slicer" tests use `respx ... .mock(side_effect=httpx.ConnectError(...))`** — absence-of-mock raises `RESPX: an unmocked request was made`, but the side-effect form propagates a real `ConnectError` which the client maps to `E_NOT_RUNNING`, so each probe degrades cleanly.
- **PNG fixture bytes must look real to `validate_png`.** Magic + size ≥ 256 + IHDR width/height non-zero. Use `_make_png(width, height, body_size)` from `test_render.py` / `test_doctor.py`. A naïve `b"\x89PNG\r\n\x1a\nfake"` fails with "PNG too small" instead of the case you meant to test.
- **Templated `/slicer/exec` payload tests must NOT execute the rendered Python.** Use `ast.parse(rendered_source)` for syntactic validity only (real evaluation needs Slicer's runtime AND pre-commit hooks flag the relevant builtins). See `tests/unit/test_exec.py`.
- **DICOM JSON fixtures mirror PS3.18 §F shape.** Tag values are dicts (`{"vr": "...", "Value": [...]}`); PN values are objects (`{"Alphabetic": "..."}`); empty/missing tags are common in the wild. Synthetic data only — names, IDs, and UIDs in unit fixtures must never be real PHI; UIDs use the reserved `2.25.*` root per DICOM PS3.5 §B.2. Real UIDs for live integration tests are read from gitignored `tests/integration/.env`.
- **Orthanc round-trip integration tests should `pytest.skip` if the prerequisite `dicom pull` fails.** `/slicer/exec` may be disabled in some environments; detect `E_HTTP_5XX` from the pull and skip rather than asserting on downstream state. See `test_dicom_live.py::test_dicom_pull_then_query_round_trip`.
- **`--i-understand-the-risk` gating** is tested with `monkeypatch.setenv("SLICER_EXEC_ENABLED", "false")`. Without the override, `slicer-cli exec` returns `E_EXEC_DISABLED` (exit 5); with it, the call proceeds. Do NOT mutate `cli_ctx.config` directly — go through env so the layered loader runs.
