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
│   │   ├── stub.py               ← `stub(ctx, what, phase=...)` → E_NOT_IMPLEMENTED
│   │   └── argv.py               ← hoist_global_flags() — lifts --json/--url etc. before the verb
│   ├── status.py, doctor.py      ← top-level commands (not under any group)
│   ├── system.py, config.py      ← app-level groups (system, the CLI's own config)
│   ├── api.py, dicom.py,         ← independent groups (api raw/routes, DICOMweb)
│   │   render.py, exec_.py
│   └── mrml/                     ← MRML-flavored commands cluster (share _helpers.py in Phase 1+)
│       ├── _helpers.py           ← empty-selector / class-filter / node-table helpers
│       ├── scene.py, node.py
│       ├── volume.py, sample.py
│       └── markup.py
├── client/                       ← typed Python API for Slicer. Reusable on its own
│                                   (a future MCP server will import this directly).
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

1. New endpoint? Add the route to `client/routes.py` with the right `phase`, `destructive`, and `stub` flags. `api routes` and `api raw`'s destructive guard read it directly.
2. Add a typed method to `SlicerClient` (or a dedicated `client/<topic>.py` if the topic has multiple methods).
3. Define a pydantic response model in `client/models.py` if the response is structured.
4. Map any new failure modes to a `SlicerError` subclass in `client/errors.py` with a fresh `ErrorCode`.
5. If the endpoint is destructive (mutates scene state, shuts Slicer down, runs arbitrary code), the *client* method itself must refuse empty/missing selectors — defence-in-depth above the CLI guard. See `SlicerClient.delete_node` for the pattern.

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
