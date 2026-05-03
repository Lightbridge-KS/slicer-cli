# `tests/` — testing guide

This file is symlinked from `CLAUDE.md` in the same directory.
Read [`/AGENTS.md`](../AGENTS.md) first for project-wide context; this file adds rules that apply only when editing tests under `tests/`.

## Layout

```
tests/
├── conftest.py            shared fixtures (currently: `runner`, `slicer_app`)
├── unit/                  hermetic, fast. respx mocks Slicer. No network.
└── integration/           hits real Slicer. Gated on SLICER_INTEGRATION=1.
```

Run them with:

```
uv run pytest -m "not integration"        # unit only (default for CI)
SLICER_INTEGRATION=1 uv run pytest        # both — needs Slicer running with WebServer started
```

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
