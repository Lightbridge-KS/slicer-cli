# `slicer-cli` — Implementation Tracker

| Field | Value |
|---|---|
| Last updated | 2026-05-03 |
| Plan | `/Users/kittipos/.claude/plans/glimmering-painting-lagoon.md` |
| PRD | [`Slicer-CLI-PRD.md`](./Slicer-CLI-PRD.md) |
| Status | **Phase 1 complete ✓ — 128 tests green (111 unit + 17 integration)** |

---

## How to use this file

- Each phase mirrors PRD §13. Tick boxes as you finish.
- Update the `Status` field above when entering a new phase.
- When a checkbox is ticked, prefer **also** referencing the commit / PR that did it (Conventional Commits, e.g. `feat(cli): status command`) so the audit trail is one click away.
- Out-of-MVP items live in the "Deferred" section — they exist here only so they don't get forgotten, not because they're scheduled.

---

## Phase 0 — Scaffolding

**Goal:** `uv run slicer-cli status --json` succeeds against a live Slicer; everything else returns `E_NOT_IMPLEMENTED` cleanly.

### Repo bootstrap

- [x] `uv init --lib --name slicer-cli .` (preserves `docs/` and `AGENTS.md`)
- [x] `pyproject.toml` — `requires-python = ">=3.11"`
- [x] `pyproject.toml` — runtime deps: `httpx>=0.27`, `typer>=0.12`, `pydantic>=2.6`, `pydantic-settings>=2.2`, `rich>=13.7`
- [x] `pyproject.toml` — dev deps via `[dependency-groups]`: `pytest`, `respx`, `pytest-httpx`, `ruff`, `mypy`, plus `pytest-cov`
- [x] `pyproject.toml` — `[project.scripts]`: `slicer-cli`, `slcli` (alias)
- [x] `pyproject.toml` — `[tool.ruff]` (line-length 100, py311 target, sensible rules)
- [x] `pyproject.toml` — `[tool.mypy]` (`strict = true`)
- [x] `pyproject.toml` — `[tool.pytest.ini_options]` (markers: `integration`)
- [x] `.gitignore` — uv default plus `_playground/` (per global CLAUDE.md)
- [x] `uv sync` clean

### Module skeleton

- [x] `src/slicer_cli/__init__.py` — `__version__ = "0.1.0"`
- [x] `src/slicer_cli/config.py` — pydantic-settings model + layered loader (PRD §7.1)
- [x] `src/slicer_cli/output.py` — JSON envelope + rich pretty formatter (PRD §6.2/§6.3)
- [x] `src/slicer_cli/client/__init__.py`
- [x] `src/slicer_cli/client/base.py` — `SlicerClient` (httpx.Client wrapper)
- [x] `src/slicer_cli/client/errors.py` — `SlicerError` + stable `E_*` codes (PRD §6.4)
- [x] `src/slicer_cli/client/models.py` — pydantic models (`SystemVersion`, `NodeRef`)
- [ ] `src/slicer_cli/client/routes.py` — placeholder for Phase-1 route data *(deferred to Phase 1 — we don't need it yet)*
- [ ] `src/slicer_cli/client/system.py` — *(client method `system_version()` lives on `SlicerClient` directly; standalone module not needed yet)*
- [ ] `src/slicer_cli/client/{scene,volume,render,dicom,markup,exec_}.py` *(deferred to phases that need them; CLI stubs at the cli/ layer suffice for Phase 0)*
- [x] `src/slicer_cli/cli/__init__.py`
- [x] `src/slicer_cli/cli/app.py` — root Typer with global flags + argv hoister so flags work after the subcommand too
- [x] `src/slicer_cli/cli/_context.py` — `CliContext` + `build_context`
- [x] `src/slicer_cli/cli/_stub.py` — shared `E_NOT_IMPLEMENTED` helper
- [x] `src/slicer_cli/cli/status.py` — functional
- [x] `src/slicer_cli/cli/system.py` — `version` functional, `shutdown` Phase-1 stub
- [x] `src/slicer_cli/cli/config.py` — `show / get / path` functional
- [x] `src/slicer_cli/cli/{scene,node,volume,sample,render,markup,dicom,exec_,api,doctor}.py` — stubs returning `E_NOT_IMPLEMENTED`

### Tests

- [x] `tests/unit/test_status.py` — respx mock of `/slicer/system/version` (+ argv hoister tests)
- [x] `tests/unit/test_status_offline.py` — refused/timeout/5xx mapped to E_*, correct exit codes
- [x] `tests/unit/test_config.py` — flag > env > project-toml > user-toml > built-in
- [x] `tests/unit/test_output.py` — JSON envelope shape (success + error) + pretty smoke test
- [x] `tests/integration/test_status_live.py` — gated on `SLICER_INTEGRATION=1`

### Project meta

- [x] `AGENTS.md` filled in with project conventions (commands, layout, DoD)
- [x] `docs/Slicer-CLI-PRD.md` §14.2 locked with user's answers
- [x] `docs/Slicer-CLI-PRD.md` §7.2 `exec.enabled` default → `true` (YOLO)
- [x] `docs/Slicer-CLI-PRD.md` metadata block: `Status: Locked v0.2`

### Acceptance gates (Phase 0 complete when all green)

- [x] `uv sync` clean
- [x] `uv run slicer-cli status --json` against live Slicer returns the version envelope
- [x] `uv run slicer-cli status --url http://127.0.0.1:9999 --json` (down Slicer) → `E_NOT_RUNNING`, exit code **3**
- [x] `uv run pytest -m "not integration"` green (18 tests)
- [x] `SLICER_INTEGRATION=1 uv run pytest -m integration` green (1 test)
- [x] `uv run ruff check` clean
- [x] `uv run ruff format --check` clean
- [x] `uv run mypy` clean (33 source files)

---

## Phase 1 — Core read/write

**Goal:** End-to-end MRHead workflow works: load sample, list volumes, export, scene-clear (guarded).

**Plan file:** `~/.claude/plans/glimmering-painting-lagoon.md` (5 batches)

### Batch 1 — Infrastructure ✓

- [x] Models added: `Volume`, `LoadResult`, `DeleteResult` (+ `NodeRef.class_` optional)
- [x] `client/routes.py` data file (32 endpoints, destructive flags, phase tags)
- [x] `client/_id_helpers.py` (`id_to_class`, `attach_class_to_refs`)
- [x] `cli/_internal/safety.py` (`require_confirm`, `require_nonempty_id`)
- [x] `cli/mrml/_helpers.py` (`parse_class_filter`, `format_node_table`)
- [x] Tests: routes / safety / helpers — 38 new unit tests

### Batch 2 — Read-only commands ✓

- [x] `volume list` / `volume show <id>`
- [x] `scene nodes [--class C] [--name N]` / `scene ids [--class C] [--name N]`
- [x] `node show <id>` (with empty-id guard)
- [x] `sample list` (curated 7-sample allow-list, offline)
- [x] Unit tests (respx) for all 5 commands — 15 new tests
- [x] Integration test_phase1_readonly.py against live MRHead — 5 tests pass

### Batch 3 — Load operations ✓

- [x] `sample load <name>`
- [x] `volume import <path> [--name N]` (POST `/slicer/mrml?filetype=VolumeFile`)
- [x] `scene load <path>` (POST `/slicer/mrml?filetype=SceneFile`)
- [x] Unit + integration tests

### Batch 4 — Export / save / reload ✓

- [x] `volume export <id> --out path|-` (NRRD bytes)
- [x] `scene save <path>` (templated power-tool payload per locked Q-A)
- [x] `node reload <id>` (PUT `/slicer/mrml?id=...`)
- [x] `output.render_meta_to_stderr()` helper for binary commands

### Batch 5 — Destructive + meta ✓

- [x] `scene clear --confirm` (without `--confirm` → `E_DESTRUCTIVE`, exit 6)
- [x] `node delete <id>` / `volume delete <id>` (rejects empty)
- [x] `system shutdown --confirm`
- [x] `doctor` capability matrix (PRD §7.3)
- [x] `api routes` (offline introspection, with `--method` / `--destructive` / `--phase` filters)
- [x] `api raw <method> <path>` (with destructive guards via `routes.DESTRUCTIVE_RAW`)

### User Manual

- [x] Write User Manual for AI Agent and Human at `docs/Slicer-CLI-UserManual.md` (up to this stage)

### Cross-cutting

- [x] PRD-Appendix-A coverage check: every Phase-1 row ticked
- [x] Update relevant AGENTS.md (root + `src/slicer_cli/AGENTS.md` + `tests/AGENTS.md`)

---

## Phase 2 — Rendering + DICOM

**Goal:** Render slices/3D to PNG; QIDO/WADO and OrthanC pull both work.

- [ ] `render slice [--view --orientation --offset --scrollTo --size] [--out path|-]`
- [ ] `render threed [--look A|P|L|R|S|I] [--out]`
- [ ] `render screenshot [--out]` (warns if main-window absent)
- [ ] `render gltf [--widget 0] [--out]`
- [ ] Binary output handling: `--out path` or `-` (stdout); JSON envelope to stderr in `--json` mode
- [ ] Empty/black-PNG detection (catches headless-without-Mesa) → `E_BAD_RESPONSE` with hint
- [ ] `dicom studies [--patient --limit --offset]`
- [ ] `dicom series <studyUID>`
- [ ] `dicom instances <studyUID> <seriesUID>`
- [ ] `dicom instance <studyUID> <seriesUID> <sopUID> [--out path]` (WADO-RS)
- [ ] `dicom meta <studyUID> [<seriesUID> [<sopUID>]]`
- [ ] `dicom pull --orthanc <prefix> --study <UID> [--store dicom-web] [--token T]`
- [ ] `dicom pull` fallback hint surfaces on the known Slicer-side bug (surface-report §8.1)
- [ ] Unit + integration tests

---

## Phase 3 — Markup + exec + gui

**Goal:** Templated `/exec`-backed markups; gated `exec` with audit log.

- [ ] `markup list [--type fiducial|line|...]`
- [ ] `markup fiducial-set --id ID --index N --r R --a A --s S` (PUT `/slicer/fiducial`)
- [ ] `markup line --p1 R,A,S --p2 R,A,S [--name N]` (templated `/exec`)
- [ ] `exec --code '...'` / `exec --file path.py`
- [ ] Audit log writer at `~/.local/state/slicer-cli/exec.log` (mkdir parents on first write)
- [ ] Audit-log line format: `<iso8601>  rev=<rev>  url=<url>  hash=sha256:<hex>  preview="<first 200 chars>"`
- [ ] `--no-audit-log` flag emits stderr warning but still proceeds (YOLO honours it)
- [ ] `gui layout fourup|oneup3d|... [--contents full|viewers]` (PUT `/slicer/gui`)
- [ ] Unit tests including audit-log assertions
- [ ] Integration tests

---

## Phase 4 — Companion skill

**Goal:** A single skill at `.claude/skills/slicer-cli/SKILL.md` that triggers Claude to use the CLI on Slicer-related prompts.

- [ ] `.claude/skills/slicer-cli/SKILL.md` written per PRD §12 format
- [ ] Frontmatter `description:` field carefully tuned for Claude trigger matching
- [ ] Body: when-to-invoke, safety rules (no `scene clear` / `system shutdown` / `exec` without explicit user instruction), JSON-mode reminder, 3-5 worked examples
- [ ] Cross-links to `slicer-cli api routes --json` and `slicer-cli doctor --json`
- [ ] Manual smoke test: prompt Claude with "load MRHead in Slicer and render an axial slice at offset 12 mm" — verify it auto-invokes the skill and runs the right commands

---

## Deferred (post-MVP — tracked so we don't forget)

| Item | Notes |
|---|---|
| `slicer_module/AgentTools.py` | Slicer-side helper module to keep `/exec` payloads tiny. Same repo, separate folder; ships when MVP is stable. |
| Lifecycle (`slicer-cli serve start/stop/status`) | Spawn Slicer headless; needs Mesa on Linux, app-bundle paths on macOS, registry on Windows. |
| Multi-instance (Slicer on 2016 + 2017) | Auto-port-discovery + config profiles. |
| GUI control beyond `gui layout` | Window switching, module switching. |
| Advanced markups | `angle`, `plane`, `roi`, `curve` — all templated `/exec` wrappers. |
| Render caching | Key on `(scene_revision, viewer, params)`; needs a scene-revision counter via `/exec`. |
| MCP server | Wraps the same `SlicerClient`; trivial once that's stable. |

---

## Cross-cutting checklist (per-phase definition-of-done)

For every phase before ticking the phase header:

- [ ] All in-scope commands have **unit** tests with `respx` mocks
- [ ] All in-scope commands have **integration** tests gated on `SLICER_INTEGRATION=1`
- [ ] Each new command's `--help` reviewed for agent-readability
- [ ] `client/routes.py` updated for any newly wrapped endpoint
- [ ] `slicer-cli doctor` covers any new capability
- [ ] PRD updated if scope shifted
- [ ] Conventional Commits style used (`feat(cli): …`, `fix(client): …`, `docs(prd): …`)
