# `src/slicer_cli/` — source-tree guide

This file is symlinked from `CLAUDE.md` in the same directory.
Read [`/AGENTS.md`](../../AGENTS.md) first for project-wide context; this file adds rules that apply only when editing source under `src/slicer_cli/`.

## Architecture (you are here)

```
src/slicer_cli/
├── config.py                     ← layered config loader (flag > env > project > user > built-in).
│                                   Truly cross-cutting — stays at package root.
├── cli/                          ← thin Typer glue. NO http knowledge. Calls into client/ only.
│   ├── app.py                    ← root Typer + global flags + main()
│   ├── output.py                 ← the *only* place stdout/stderr writes happen.
│   ├── _internal/                ← scaffolding (not part of the public surface)
│   │   ├── context.py            ← CliContext + build_context (typer.Context.obj)
│   │   ├── safety.py             ← require_confirm, require_nonempty_id, require_exec_enabled
│   │   ├── stub.py               ← `stub(ctx, what, phase=...)` → E_NOT_IMPLEMENTED
│   │   ├── argv.py               ← hoist_global_flags() — lifts --json/--url etc. before the verb
│   │   └── mrml_helpers.py       ← class-filter / node-table helpers (id_to_class, parse_class_filter)
│   ├── status.py, doctor.py      ← top-level commands (not under any group)
│   ├── system.py, config.py      ← app-level groups (system, the CLI's own config)
│   ├── api.py, dicom.py,         ← independent groups (api raw/routes, DICOMweb, render, exec, gui)
│   │   render.py, exec_.py, gui.py
│   ├── scene.py, node.py,        ← MRML-domain commands — flat (the cli surface itself is flat)
│   │   volume.py, sample.py,
│   │   markup.py
├── client/                       ← typed Python API for Slicer. Reusable on its own.
│   ├── base.py                   ← `SlicerClient` composes per-domain mixins
│   ├── errors.py                 ← SlicerError hierarchy + stable E_* codes (the public contract)
│   ├── routes.py                 ← Route inventory (data file) — Route has `note` for caveats
│   ├── models.py                 ← thin re-export shim — keeps `from slicer_cli.client.models import …` working
│   ├── _internal/                ← spine + ≥2-caller utilities only
│   │   ├── http.py               ← `_HttpClient` parent: httpx state + error mapping
│   │   ├── audit.py              ← AuditLogger (PRD §8.3)
│   │   ├── exec_template.py      ← build_exec_payload (templating helper for /slicer/exec callers)
│   │   ├── validators.py         ← validate_png / validate_binary (binary-content gates)
│   │   └── models_base.py        ← `_SlicerModel` base (extra=ignore, frozen=True)
│   ├── system.py                 ← SystemMixin + SystemVersion (flat domain)
│   ├── volume.py                 ← VolumeMixin + Volume (flat)
│   ├── sample.py                 ← SampleMixin (flat, no models)
│   ├── render.py                 ← RenderMixin (flat, no models)
│   ├── gui.py                    ← GuiMixin (flat, no models)
│   ├── raw.py                    ← RawMixin (flat, no models)
│   ├── mrml/                     ← BUNDLED domain
│   │   ├── __init__.py           ← re-exports MrmlMixin, LOAD_FILETYPES, NodeRef, …
│   │   ├── mixin.py              ← MrmlMixin
│   │   ├── models.py             ← NodeRef, LoadResult, DeleteResult
│   │   └── id_helpers.py         ← MRML id ↔ class derivation
│   ├── dicom/                    ← BUNDLED domain
│   │   ├── __init__.py           ← re-exports DicomMixin, StudyRef, SeriesRef, InstanceRef
│   │   ├── mixin.py              ← DicomMixin
│   │   ├── models.py             ← StudyRef, SeriesRef, InstanceRef
│   │   └── tags.py               ← DICOM JSON Model tag IDs + extraction helpers
│   └── markup/                   ← BUNDLED domain
│       ├── __init__.py           ← re-exports MarkupMixin + all markup models
│       ├── mixin.py              ← MarkupMixin
│       └── models.py             ← FiducialNode, FiducialPoint, SegmentationNode, MarkupRef, LineMarkupResult
```

The library spine is `client/`; the CLI is one of its consumers. Keep that layering — anything in `cli/*.py` that imports `httpx` or builds Slicer URLs is a smell.

The user-facing CLI surface is **flat** (`slicer-cli scene ...`, `slicer-cli volume ...`); each command file lives directly under `cli/`. There is no `cli/<group>/` subpackage as of the codebase-org-1 refactor.

## Bundle-vs-flat threshold (load-bearing principle)

**A domain becomes its own subpackage** (folder with `__init__.py` re-exporting the public surface) **when it has either:**

- **(a)** ≥2 owned files beyond the mixin (e.g. its own `models.py` AND a `tags.py` / `id_helpers.py`), OR
- **(b)** >200 LOC of mixin code.

**Otherwise it stays a single flat file** with its model defined inline next to the mixin.

As of the refactor: `mrml`, `dicom`, `markup` are bundled; `system`, `volume`, `sample`, `render`, `gui`, `raw` are flat. When a flat domain crosses the threshold, graduate it to a folder — and add `__init__.py` re-exports so the public surface (`from slicer_cli.client.<domain> import …`) stays stable.

This rule is the principle behind every "where does this go?" question in `client/`. If you're tempted to put a domain helper in `_internal/`, ask: is it shared by ≥2 mixins? If yes → `_internal/`. If no → it belongs next to its single owner (in the bundle if bundled, or just inline in the flat mixin file).

## Hard rules

These exist for safety/contract reasons. Don't relax them without updating the PRD.

- **Never call `print()` or write to `sys.stdout` directly from a command.** Always go through `cli.output.render_success` / `cli.output.render_error` so the JSON envelope contract (PRD §6.2/§6.3) stays stable. Rich markup (`[bold]…[/]`) is allowed *inside* `cli/output.py` only. The one exception: commands that intentionally emit binary on stdout (`volume export --out -`, `api raw … --out -`) write bytes via `sys.stdout.buffer` and route the success envelope to **stderr** through `cli.output.render_meta_to_stderr` — keeping the stdout binary clean.
- **Never raise generic `Exception` from the client or CLI layers.** Raise a `SlicerError` subclass with a stable `ErrorCode`. The root CLI in `cli/app.py` maps `error.code` → exit code via `errors.exit_code_for`.
- **Destructive ops** (`scene clear`, `system shutdown`, `node delete`, `exec`) must follow the safety rules in PRD §8 — `--confirm` flags, empty-selector refusal, audit logs. The `SlicerEmptySelectorError` and `SlicerDestructiveError` exception types are the contract.
- **`E_*` codes are public API.** Once shipped, never rename or repurpose them. Add new ones rather than reusing.
- **All response models extend `_SlicerModel`** (from `client/_internal/models_base.py`) which sets `model_config = ConfigDict(extra="ignore", frozen=True, populate_by_name=True)` — so we tolerate Slicer's schema drift between releases (PRD §14.1 R1). Keep this on every response model.

## Patterns to follow

### Adding a new CLI command group

CLI groups live flat under `cli/<group>.py`. There's no semantic grouping subdirectory — the user-facing surface is `slicer-cli <group> <verb>`, the file path mirrors that.

1. Create `cli/<group>.py`. Define `app = typer.Typer(no_args_is_help=True, help="...")` at module top.
2. Each command is `def <verb>_command(ctx: typer.Context, ...)`. Pull `cli_ctx: CliContext = ctx.obj` and `with cli_ctx.make_client() as client:` for HTTP work.
3. On error, `render_error(error, mode=cli_ctx.output_mode); raise typer.Exit(code=exit_code_for(error.code))`.
4. On success, `render_success(payload, mode=cli_ctx.output_mode, renderer=...)`.
5. Register in `cli/app.py` via `app.add_typer(<group>_cli.app, name="<group>")` — add to the existing aliased-imports block (combine-as-imports stays `true`).

### Adding a new client method

1. **New endpoint?** Add the route to `client/routes.py` with the right `phase`, `destructive`, and `stub` flags. The optional `note: str | None` field is for Slicer-side bugs or CLI workarounds.
2. **Pick the right home for the mixin.** Apply the bundle-vs-flat threshold above:
   - **Bundled domain** (`mrml/`, `dicom/`, `markup/`)? Edit the existing `mixin.py` in that folder; add to `models.py` if response is structured; if the new method needs a domain helper, add it as a new file in the bundle and add to `__init__.py`'s re-exports.
   - **Flat domain** (`system.py`, `volume.py`, …)? Edit the file directly; if the response model is new, define it inline in the same file (right above the mixin class).
   - **Brand-new domain?** Start flat. Promote to a bundle later when the threshold is crossed.
3. Map any new failure modes to a `SlicerError` subclass in `client/errors.py` with a fresh `ErrorCode`. **Never reuse codes** across semantically-different failures — codes are public API.
4. If the endpoint is destructive (mutates scene state, shuts Slicer down, runs arbitrary code), the *client* method itself must refuse empty/missing selectors — defence-in-depth above the CLI guard. See `MrmlMixin.delete_node` for the pattern.

### Where helpers live (the `_internal/` rule)

`client/_internal/` holds **only** the spine (`http.py`, `audit.py`, `models_base.py`) and **multi-caller utilities** (`validators.py`, `exec_template.py` — both used by ≥2 mixins).

**Domain-specific helpers go next to their domain**, not in `_internal/`:
- `mrml/id_helpers.py` (only MrmlMixin uses it)
- `dicom/tags.py` (only DicomMixin uses it for live calls; the cli/output renderer reaches in via the bundle's public re-export when needed)

When you write a helper, ask: does ≥2 mixin import it? If yes → `_internal/`. If no → next to its owner.

### Validating binary responses (PNG / glTF / DICOM)

`client/_internal/validators.py` holds shared response gates (used by render mixin AND `cli/doctor.py:_probe_render`):

- `validate_png(content, *, endpoint)` — magic bytes + size ≥ 256 + non-zero IHDR width/height. Raises `SlicerBadResponseError` with a hint that **literally contains `GALLIUM_DRIVER=llvmpipe`** (PRD §14 R3 — agents copy-paste it). Used by all 3 PNG render methods AND the doctor probe (single source of truth — don't re-implement the magic-byte check inline).
- `validate_binary(content, *, endpoint, min_bytes)` — generic non-empty guard for endpoints without a known magic header (e.g., glTF, where Slicer may return JSON or `.glb` depending on build).

When adding a new binary-content endpoint: pick the closest validator and use it; only add a new validator function here if you have ≥ 2 callers. (One-caller-only validators live next to that caller.)

### Templated `/slicer/exec` payloads

Two cooperating helpers:

- **`client/_internal/exec_template.py::build_exec_payload(template, **kwargs)`** templates a Python source string with `repr()`-quoted kwargs, returns bytes.
- **`_HttpClient._post_exec(source, *, op_label)`** is the **single funnel** for every POST to `/slicer/exec`. It writes one audit-log line via `self._audit_logger` (if attached), THEN sends the POST.

Every `/slicer/exec` caller MUST use `_post_exec` — never POST directly via `self._request("POST", "/slicer/exec", ...)`. The four current callers are `MrmlMixin.save_scene`, `DicomMixin.pull_from_dicomweb`, `MarkupMixin.add_line`, and `_HttpClient.run_python` (the public method behind `slicer-cli exec`). Adding a fifth caller? Just template + `_post_exec` — audit happens automatically.

Two rules when authoring a template:
1. **All kwargs get `repr()`-quoted before substitution** — defend against quote-escape attacks. User-supplied paths, UIDs, URLs, tokens cannot break Python syntax.
2. **Use `{{` / `}}` for literal braces** in the rendered Python (e.g., the `__execResult` dict literal). Templates use `str.format` exactly once.

The template MUST set `__execResult` to a JSON-serializable value — Slicer returns that as the response body.

### Audit log

`client/_internal/audit.py::AuditLogger` writes PRD §8.3-shaped lines to `~/.local/state/slicer-cli/exec.log` (configurable via `config.exec.audit_log`). Filesystem I/O lives only here — `_HttpClient` just *holds* an `AuditLogger | None` and calls `.log(...)` from `_post_exec`. The CLI factory `cli/_internal/context.py::CliContext.make_client(disable_audit=False)` constructs and injects a logger from config; callers that want to opt out (e.g. `exec --no-audit-log`) pass `disable_audit=True`.

Tests should never touch the real `~/.local/state/...` — `tests/conftest.py` autouse-redirects to a per-test tmp dir; tests that want to *inspect* the audit output request the `audit_log_path` fixture.

### Gating `slicer-cli exec` (formal command)

`cli/_internal/safety.py::require_exec_enabled(config, *, override)` enforces `config.exec.enabled` for the user-invoked `exec` command only. Internal users (`save_scene`, `pull_from_dicomweb`, `add_line`) are vetted operations and bypass the gate — they're audited but not gated. The override flag is the verbose `--i-understand-the-risk` (locked Q-A in the Phase 3 plan; deliberately friction-y).

### DICOM JSON Model handling

`client/dicom/tags.py` holds tag constants + extraction helpers (`dicom_tag_value`, `dicom_value_list`, `dicom_person_name`, `coerce_int`). Lives in the `dicom/` bundle as a domain helper. The CLI's `cli/output.py` pretty-renderer reaches in via `from slicer_cli.client.dicom.tags import …` when it needs to render DICOM responses — that's still cli → client direction (no boundary violation).

Pattern for new DICOM-shaped models:

```python
class FooRef(_SlicerModel):
    foo_uid: str                    # always-present "key"
    common_field_1: str | None = None   # flatten the most useful tags
    common_field_2: int | None = None
    raw: dict[str, Any]             # ALWAYS preserve the full DICOM JSON blob
```

Power-tool callers can read `.raw["00100010"]` etc. for exotic tags; everyone else uses the friendly fields.

### Adding a new `doctor` probe

Probes live in `cli/doctor.py` as `_probe_<name>(client) -> CheckResult`. Each must:

1. Run independently — never raise; catch `SlicerError` and return a FAIL `CheckResult` with `_short(error.message)`.
2. Use `client.raw(method, path, ...)` for endpoints that don't have a typed wrapper yet (e.g. `/dicom/studies`, `/slicer/exec`, `/slicer/slice`). That keeps the probe future-proof against router refactors.
3. Append the probe to `run_checks()` in the order the user reads the matrix (top-to-bottom = roughly cheapest/most-foundational first).
4. The "doctor" pretty renderer in `cli/output.py` keys off `name` / `ok` / `detail` — keep `detail` short (under 80 chars) so the table stays readable.

### Stub commands for not-yet-implemented work

Use `slicer_cli.cli._internal.stub.stub(ctx, "<group> <verb>", phase="Phase N")`. This emits `E_NOT_IMPLEMENTED` with a phase pointer — agents see the surface in `--help` but get a clear "wait until Phase N" signal at runtime.

### Global flag UX (the argv hoister)

`cli/_internal/argv.py` defines `hoist_global_flags()` so `slicer-cli status --json` works the same as `slicer-cli --json status`. If you add a new global flag (in `@app.callback`), also add its name to `GLOBAL_FLAGS_BOOL` or `GLOBAL_FLAGS_VALUE` in that module. The hoister is independently importable for tests.

## Things that look fine but aren't

- **Sync `httpx`, not async.** Slicer's WebServer is single-threaded inside the Qt event loop — async parallelism buys nothing and complicates testing. Don't introduce `httpx.AsyncClient`.
- **Substring routing in Slicer is positionally fragile** (PRD §4.1, surface report §4.1). Always send full canonical paths from the client. Never let a user-supplied path reach `/slicer/...` outside `api raw` (Phase 1).
- **Empty selectors on `DELETE /slicer/mrml` clear the whole scene** (surface report §4.1, PRD §8.1). Any client method that builds `/mrml`-shaped URLs must refuse empty selectors at the *client* layer, not just the CLI layer.
- **Aliased imports get split by ruff isort by default.** We set `combine-as-imports = true` in `pyproject.toml` so `from slicer_cli.cli import (a as a_cli, b as b_cli, ...)` stays grouped. If you add new aliased imports, keep the same shape.
- **Some Slicer endpoints have known bugs.** Surface report §8 catalogues them; `client/routes.py` flags them with `note=`. The canonical example is `/slicer/accessDICOMwebStudy` — its handler does `request = json.loads(...), b"application/json"` (a tuple) and crashes on `request["dicomWEBPrefix"]`. The CLI bypasses by templating /exec; `api routes --json` exposes the note so agents see the hazard. Add new `note=` entries when wrapping any endpoint with a known footgun.
- **`/slicer/threeDGraphics` returns JSON glTF, not binary `.glb`** in Slicer 5.11 — despite its content-type and the surface report calling it "binary geometry stream". Use `validate_binary(min_bytes=1024)` (no magic-byte check) for this endpoint. Don't try to be clever about glTF format detection.
- **`client/models.py` is a re-export shim, not a place to add new models.** Define new models next to their owner (in the bundle's `models.py` for bundled domains, inline in the mixin file for flat domains). Then re-export from `client/models.py` only if existing call sites need to find them via the legacy `from slicer_cli.client.models import …` path.
