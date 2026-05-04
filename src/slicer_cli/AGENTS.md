# `src/slicer_cli/` — source-tree guide

Read [`/AGENTS.md`](../../AGENTS.md) first for project-wide context. This file covers rules that apply when editing source under `src/slicer_cli/`.

## Architecture

```
src/slicer_cli/
├── config.py                 layered config loader (flag > env > project > user > built-in)
├── cli/                      thin Typer glue. NO http knowledge — calls into client/ only
│   ├── app.py                root Typer + global flags + main()
│   ├── output.py             the *only* place stdout/stderr writes happen
│   ├── _internal/            scaffolding (context, safety, stub, argv, mrml_helpers)
│   ├── status.py, doctor.py  top-level commands (no subgroup)
│   ├── system.py, config.py  app-level groups
│   ├── api.py, dicom.py,     domain command modules — flat (the surface itself is flat:
│   │   render.py, exec_.py,  `slicer-cli scene ...`, no `cli/<group>/` subpackages)
│   │   gui.py, scene.py,
│   │   node.py, volume.py,
│   │   sample.py, markup.py
└── client/                   typed Python API — reusable on its own
    ├── base.py               `SlicerClient` composes per-domain mixins
    ├── errors.py             `SlicerError` hierarchy + stable `E_*` codes (public contract)
    ├── routes.py             route inventory (data file); `Route.note` flags Slicer-side caveats
    ├── models.py             thin re-export shim — DO NOT add new models here
    ├── _internal/            spine + ≥2-caller utilities only:
    │   ├── http.py           `_HttpClient` parent: httpx state + error mapping + post-exec funnel
    │   ├── audit.py          `AuditLogger` — only place that writes to the audit log
    │   ├── exec_template.py  `build_exec_payload` — repr-quoted templating for /slicer/exec
    │   ├── validators.py     `validate_png` / `validate_binary` — binary response gates
    │   └── models_base.py    `_SlicerModel` base (extra=ignore, frozen=True)
    ├── system.py, volume.py, FLAT domains: mixin + inline models in one file
    │   sample.py, render.py,
    │   gui.py, raw.py
    └── mrml/, dicom/,        BUNDLED domains: subpackage with mixin.py + models.py + helpers
        markup/               `__init__.py` re-exports the public surface
```

The library spine is `client/`; the CLI is one of its consumers. Anything in `cli/*.py` that imports `httpx` or builds Slicer URLs is a layering smell.

## Bundle-vs-flat threshold (load-bearing)

**A domain becomes its own subpackage** (folder with `__init__.py` re-exporting the public surface) **when it has either:**

- **(a)** ≥2 owned files beyond the mixin (e.g. its own `models.py` AND a `tags.py` / `id_helpers.py`), OR
- **(b)** >200 LOC of mixin code.

**Otherwise it stays a single flat file** with its model defined inline next to the mixin.

When a flat domain crosses the threshold, graduate it to a folder and add `__init__.py` re-exports so the public surface (`from slicer_cli.client.<domain> import …`) stays stable.

This is the principle behind every "where does this go?" question in `client/`. Corollary for helpers: **does ≥2 mixin import it?** Yes → `_internal/`. No → next to its single owner (in the bundle if bundled, inline if flat).

## Hard rules

These exist for safety/contract reasons. Don't relax without updating the PRD.

1. **Never `print()` or write to `sys.stdout` directly from a command.** Always go through `cli.output.render_success` / `render_error` so the JSON envelope (PRD §6.2/§6.3) stays stable. Rich markup (`[bold]…[/]`) is allowed *inside* `cli/output.py` only. Exception: commands that emit binary on stdout (`volume export --out -`, `api raw … --out -`) write bytes via `sys.stdout.buffer` and route the success envelope to **stderr** through `render_meta_to_stderr`.
2. **Every POST to `/slicer/exec` MUST go through `_HttpClient._post_exec(source, *, op_label)`.** It writes one audit-log line then sends the POST. Never POST to `/slicer/exec` via `_request` directly. Current callers: `MrmlMixin.save_scene`, `DicomMixin.pull_from_dicomweb`, `MarkupMixin.add_line`, `_HttpClient.run_python` (the `slicer-cli exec` backend).
3. **Never raise generic `Exception` from client/CLI layers.** Raise a `SlicerError` subclass with a stable `ErrorCode`. `cli/app.py` maps `error.code` → exit code via `errors.exit_code_for`.
4. **`E_*` codes are public API.** Once shipped, never rename or repurpose. Add new ones rather than reusing.
5. **All response models extend `_SlicerModel`** (from `client/_internal/models_base.py`) — `extra="ignore"`, `frozen=True`, `populate_by_name=True`. This tolerates Slicer schema drift between releases (PRD §14.1 R1).
6. **Destructive ops** (`scene clear`, `system shutdown`, `node delete`, exec) follow PRD §8 — `--confirm` flags, empty-selector refusal, audit logs. The `SlicerEmptySelectorError` and `SlicerDestructiveError` types are the contract. Defence in depth: client methods that build `/mrml`-shaped URLs must refuse empty selectors at the *client* layer too (see `MrmlMixin.delete_node`).

## Patterns

### Templated `/slicer/exec` payloads

Two cooperating helpers:

- **`_internal/exec_template.py::build_exec_payload(template, **kwargs)`** — `repr()`-quotes every kwarg before substitution (defends against quote-escape attacks); use `{{` / `}}` for literal braces. The template MUST set `__execResult` to a JSON-serializable value — Slicer returns that as the response body.
- **`_HttpClient._post_exec`** is the single funnel (see hard rule 2). Adding a fifth caller? Just template + `_post_exec` — audit happens automatically.

### Validating binary responses

`_internal/validators.py` is the single source of truth for binary gates:

- `validate_png(content, *, endpoint)` — magic + size ≥ 256 + non-zero IHDR. Hint string **literally contains `GALLIUM_DRIVER=llvmpipe`** (PRD §14 R3 — agents copy-paste it). Used by all PNG callers AND `cli/doctor.py:_probe_render`.
- `validate_binary(content, *, endpoint, min_bytes)` — generic non-empty guard for endpoints without a known magic header (e.g. glTF).

Add a new validator only when ≥2 callers need it. One-caller validators live next to the caller.

### DICOM JSON Model

`client/dicom/tags.py` holds tag constants + extraction helpers (`dicom_tag_value`, `dicom_value_list`, `dicom_person_name`, `coerce_int`). `cli/output.py` may import from there directly — that's still cli → client direction.

Pattern for new DICOM-shaped models:

```python
class FooRef(_SlicerModel):
    foo_uid: str                       # always-present "key"
    common_field_1: str | None = None  # flatten the most useful tags
    raw: dict[str, Any]                # ALWAYS preserve the full DICOM JSON blob
```

### Stub commands

Use `cli._internal.stub.stub(ctx, "<group> <verb>", phase="Phase N")` — emits `E_NOT_IMPLEMENTED` with a phase pointer. Surfaces in `--help`; clear runtime signal.

### Global flag UX

`cli/_internal/argv.py::hoist_global_flags()` lifts `--json`/`--url`/etc. before the verb, so `slicer-cli status --json` works the same as `slicer-cli --json status`. New global flag in `@app.callback`? Add its name to `GLOBAL_FLAGS_BOOL` or `GLOBAL_FLAGS_VALUE`.

### Audit log

`AuditLogger` writes PRD §8.3-shaped lines to `~/.local/state/slicer-cli/exec.log` (configurable via `config.exec.audit_log`). Filesystem I/O lives only here — `_HttpClient` holds an `AuditLogger | None` and calls `.log(...)` from `_post_exec`. CLI factory `cli/_internal/context.py::CliContext.make_client(disable_audit=False)` injects the logger; `slicer-cli exec --no-audit-log` passes `disable_audit=True`.

## Footguns

- **Sync `httpx`, not async.** Slicer's WebServer is single-threaded inside the Qt event loop — async buys nothing and complicates testing. Don't introduce `httpx.AsyncClient`.
- **Substring routing in Slicer is positionally fragile** (PRD §4.1, surface report §4.1). Always send full canonical paths from the client. Never let user-supplied paths reach `/slicer/...` outside `api raw`.
- **Empty selectors on `DELETE /slicer/mrml` clear the whole scene.** Refuse them at the *client* layer, not just the CLI layer.
- **Aliased imports get split by ruff isort by default.** We set `combine-as-imports = true` in `pyproject.toml` so `from slicer_cli.cli import (a as a_cli, ...)` stays grouped — keep the same shape when adding new ones.
- **Some Slicer endpoints have known bugs** (surface report §8). Flag them with `Route.note=` in `client/routes.py`. Canonical example: `/slicer/accessDICOMwebStudy`'s handler crashes on `request["dicomWEBPrefix"]`; the CLI bypasses by templating /exec. `api routes --json` exposes notes so agents see hazards.
- **`/slicer/threeDGraphics` returns JSON glTF, not binary `.glb`** in Slicer 5.11 — despite content-type. Use `validate_binary(min_bytes=1024)` (no magic-byte check).
- **`client/models.py` is a re-export shim.** Define new models next to their owner (in the bundle's `models.py` for bundled, inline in the mixin file for flat). Re-export from `client/models.py` only if legacy import paths require it.
