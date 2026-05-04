# `src/slicer_cli/` — source-tree guide

This file is symlinked from `CLAUDE.md` in the same directory.
Read [`/AGENTS.md`](../../AGENTS.md) first for project-wide context; this file adds rules that apply only when editing source under `src/slicer_cli/`.

## Architecture (you are here)

```
src/slicer_cli/
├── cli/                          ← thin Typer glue. NO http knowledge. Calls into client/ only.
│   ├── app.py                    ← root Typer + global flags + main()
│   ├── _internal/                ← scaffolding (not part of the public surface)
│   │   ├── context.py            ← CliContext + build_context (typer.Context.obj)
│   │   ├── safety.py             ← require_confirm, require_nonempty_id
│   │   ├── stub.py               ← `stub(ctx, what, phase=...)` → E_NOT_IMPLEMENTED
│   │   └── argv.py               ← hoist_global_flags() — lifts --json/--url etc. before the verb
│   ├── status.py, doctor.py      ← top-level commands (not under any group)
│   ├── system.py, config.py      ← app-level groups (system, the CLI's own config)
│   ├── api.py, dicom.py,         ← independent groups (api raw/routes, DICOMweb, render, exec)
│   │   render.py, exec_.py
│   └── mrml/                     ← MRML-flavored commands cluster (share _helpers.py)
│       ├── _helpers.py           ← class-filter / node-table helpers
│       ├── scene.py, node.py
│       ├── volume.py, sample.py
│       └── markup.py
├── client/                       ← typed Python API for Slicer. Reusable on its own
│                                   (a future MCP server will import this directly).
│   ├── _http.py                  ← `_HttpClient` parent: httpx state + error mapping
│   ├── _validators.py            ← validate_png / validate_binary (binary-content gates)
│   ├── _exec.py                  ← build_exec_payload (templated /slicer/exec — Phase 3 gate)
│   ├── _id_helpers.py            ← MRML id ↔ class derivation
│   ├── _dicom_tags.py            ← DICOM JSON Model tag IDs + extraction helpers
│   ├── base.py                   ← `SlicerClient` composes per-domain mixins
│   ├── system.py, mrml.py,       ← per-domain mixins (each extends _HttpClient)
│   │   volume.py, sample.py,
│   │   render.py, dicom.py, raw.py
│   ├── routes.py                 ← Route inventory (data file) — Route has `note` for caveats
│   ├── models.py                 ← Pydantic response models
│   └── errors.py                 ← SlicerError hierarchy + stable E_* codes
├── config.py                     ← layered config loader (flag > env > project > user > built-in).
└── output.py                     ← the *only* place stdout/stderr writes happen.
```

The library spine is `client/`; the CLI is one of its consumers. Keep that layering — anything in `cli/*.py` that imports `httpx` or builds Slicer URLs is a smell.

The user-facing CLI surface is **flat** (`slicer-cli scene ...`, `slicer-cli volume ...`); the `cli/mrml/` folder is code organisation only. Sub-apps from `cli/mrml/` are still registered at the root in `cli/app.py`.

## Hard rules

These exist for safety/contract reasons. Don't relax them without updating the PRD.

- **Never call `print()` or write to `sys.stdout` directly from a command.** Always go through `output.render_success` / `output.render_error` so the JSON envelope contract (PRD §6.2/§6.3) stays stable. Rich markup (`[bold]…[/]`) is allowed *inside* `output.py` only. The one exception: commands that intentionally emit binary on stdout (`volume export --out -`, `api raw … --out -`) write bytes via `sys.stdout.buffer` and route the success envelope to **stderr** through `output.render_meta_to_stderr` — keeping the stdout binary clean.
- **Never raise generic `Exception` from the client or CLI layers.** Raise a `SlicerError` subclass with a stable `ErrorCode`. The root CLI in `cli/app.py` maps `error.code` → exit code via `errors.exit_code_for`.
- **Destructive ops** (`scene clear`, `system shutdown`, `node delete`, `exec`) must follow the safety rules in PRD §8 — `--confirm` flags, empty-selector refusal, audit logs. The `SlicerEmptySelectorError` and `SlicerDestructiveError` exception types are the contract.
- **`E_*` codes are public API.** Once shipped, never rename or repurpose them. Add new ones rather than reusing.
- **Pydantic models (`client/models.py`) use `model_config = ConfigDict(extra="ignore", frozen=True)`** so we tolerate Slicer's schema drift between releases (PRD §14.1 R1). Keep this on every response model.

## Patterns to follow

### Adding a new CLI command group

Pick the right home:
- **MRML-flavored** (manipulates `vtkMRMLNode`-derived state)? → `cli/mrml/<group>.py`. Reuse `_helpers.py` for selector validation and table formatting.
- **Independent** (rendering, DICOM, exec, api, system, config)? → `cli/<group>.py` at the top level.

Then:

1. Define `app = typer.Typer(no_args_is_help=True, help="...")` at module top.
2. Each command is `def <verb>_command(ctx: typer.Context, ...)`. Pull `cli_ctx: CliContext = ctx.obj` and `with cli_ctx.make_client() as client:` for HTTP work.
3. On error, `render_error(error, mode=cli_ctx.output_mode); raise typer.Exit(code=exit_code_for(error.code))`.
4. On success, `render_success(payload, mode=cli_ctx.output_mode, renderer=...)`.
5. Register in `cli/app.py` via `app.add_typer(<group>_cli.app, name="<group>")` — keep the user-facing name flat (`slicer-cli volume`, never `slicer-cli mrml volume`).

### Adding a new client method

1. New endpoint? Add the route to `client/routes.py` with the right `phase`, `destructive`, and `stub` flags. The optional `note: str | None` field is for Slicer-side bugs or CLI workarounds (e.g., `accessDICOMwebStudy` is bypassed via `/exec`). `api routes` and `api raw`'s destructive guard read it directly.
2. **Pick the right mixin file.** `client/system.py`, `mrml.py`, `volume.py`, `sample.py`, `render.py`, `dicom.py`, `raw.py` are per-domain mixins extending `_HttpClient`. New endpoint group? New file with `class <Topic>Mixin(_HttpClient)`. Add it to `SlicerClient`'s parents list in `client/base.py`.
3. Define a pydantic response model in `client/models.py` if the response is structured. All models extend `_SlicerModel` which has `extra="ignore", frozen=True, populate_by_name=True` — keep it that way.
4. Map any new failure modes to a `SlicerError` subclass in `client/errors.py` with a fresh `ErrorCode`. **Never reuse codes** across semantically-different failures — codes are public API.
5. If the endpoint is destructive (mutates scene state, shuts Slicer down, runs arbitrary code), the *client* method itself must refuse empty/missing selectors — defence-in-depth above the CLI guard. See `MrmlMixin.delete_node` for the pattern.

### Validating binary responses (PNG / glTF / DICOM)

`client/_validators.py` holds shared response gates:

- `validate_png(content, *, endpoint)` — magic bytes + size ≥ 256 + non-zero IHDR width/height. Raises `SlicerBadResponseError` with a hint that **literally contains `GALLIUM_DRIVER=llvmpipe`** (PRD §14 R3 — agents copy-paste it). Used by all 3 PNG render methods AND `cli/doctor.py:_probe_render` (single source of truth — don't re-implement the magic-byte check inline).
- `validate_binary(content, *, endpoint, min_bytes)` — generic non-empty guard for endpoints without a known magic header (e.g., glTF, where Slicer may return JSON or `.glb` depending on build).

When adding a new binary-content endpoint: pick the closest validator and use it; only add a new validator function here if you have ≥ 2 callers.

### Templated `/slicer/exec` payloads

`client/_exec.py::build_exec_payload(template, **kwargs)` is the **single insertion point** for every templated /exec call. Both `mrml.save_scene` and `dicom.pull_from_dicomweb` route through it. Phase 3's `exec` audit-log machinery (PRD §8.3) will wrap this one helper, NOT the call sites.

Two rules when authoring a template:
1. **All kwargs get `repr()`-quoted before substitution** — defend against quote-escape attacks. User-supplied paths, UIDs, URLs, tokens cannot break Python syntax.
2. **Use `{{` / `}}` for literal braces** in the rendered Python (e.g., the `__execResult` dict literal). Templates use `str.format` exactly once.

The template MUST set `__execResult` to a JSON-serializable value — Slicer returns that as the response body.

### DICOM JSON Model handling

`client/_dicom_tags.py` (NOT inside `client/dicom.py`) holds tag constants + extraction helpers (`dicom_tag_value`, `dicom_value_list`, `dicom_person_name`, `coerce_int`). Lives next to `models.py` so `output.py` can import it for pretty-rendering without crossing the cli → client boundary.

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
4. The "doctor" pretty renderer in `output.py` keys off `name` / `ok` / `detail` — keep `detail` short (under 80 chars) so the table stays readable.

### Stub commands for not-yet-implemented work

Use `slicer_cli.cli._internal.stub.stub(ctx, "<group> <verb>", phase="Phase N")`. This emits `E_NOT_IMPLEMENTED` with a phase pointer — agents see the surface in `--help` but get a clear "wait until Phase N" signal at runtime.

### Global flag UX (the argv hoister)

`cli/_internal/argv.py` defines `hoist_global_flags()` so `slicer-cli status --json` works the same as `slicer-cli --json status`. If you add a new global flag (in `@app.callback`), also add its name to `GLOBAL_FLAGS_BOOL` or `GLOBAL_FLAGS_VALUE` in that module. The hoister is independently importable for tests.

### When does a flat group file (`cli/<group>.py`) graduate to a folder (`cli/<group>/`)?

Trigger to split — *don't pre-split for stubs*:

- A single command exceeds ~80 lines, OR
- The group accumulates ≥2 internal helpers (e.g., audit-log writer + payload templater).

When you split, mirror the `mrml/` shape: `cli/<group>/__init__.py` (registers Typer app), `cli/<group>/_helpers.py` (shared internals), one file per command. Do *not* split the user-facing surface — keep `slicer-cli <group> <verb>` flat.

## Things that look fine but aren't

- **Sync `httpx`, not async.** Slicer's WebServer is single-threaded inside the Qt event loop — async parallelism buys nothing and complicates testing. Don't introduce `httpx.AsyncClient` unless we're adding an MCP server that genuinely needs it.
- **Substring routing in Slicer is positionally fragile** (PRD §4.1, surface report §4.1). Always send full canonical paths from the client. Never let a user-supplied path reach `/slicer/...` outside `api raw` (Phase 1).
- **Empty selectors on `DELETE /slicer/mrml` clear the whole scene** (surface report §4.1, PRD §8.1). Any client method that builds `/mrml`-shaped URLs must refuse empty selectors at the *client* layer, not just the CLI layer.
- **Aliased imports get split by ruff isort by default.** We set `combine-as-imports = true` in `pyproject.toml` so `from slicer_cli.cli import (a as a_cli, b as b_cli, ...)` stays grouped. If you add new aliased imports, keep the same shape.
- **Some Slicer endpoints have known bugs.** Surface report §8 catalogues them; `client/routes.py` flags them with `note=`. The canonical example is `/slicer/accessDICOMwebStudy` — its handler does `request = json.loads(...), b"application/json"` (a tuple) and crashes on `request["dicomWEBPrefix"]`. The CLI bypasses by templating /exec; `api routes --json` exposes the note so agents see the hazard. Add new `note=` entries when wrapping any endpoint with a known footgun.
- **`/slicer/threeDGraphics` returns JSON glTF, not binary `.glb`** in Slicer 5.11 — despite its content-type and the surface report calling it "binary geometry stream". Use `validate_binary(min_bytes=1024)` (no magic-byte check) for this endpoint. Don't try to be clever about glTF format detection.
