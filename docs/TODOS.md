# `slicer-cli` — Implementation Tracker

| Field | Value |
|---|---|
| Last updated | 2026-05-04 |
| Plan | `/Users/kittipos/.claude/plans/glimmering-painting-lagoon.md` |
| PRD | [`Slicer-CLI-PRD.md`](./Slicer-CLI-PRD.md) |
| Status | **Phase 3 complete ✓ — 238 tests green (208 unit + 30 integration; live `markup line`, `exec --code`, and `gui layout` round-trips verified against running Slicer)** |

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

## Phase 2 — Rendering + DICOM ✓

**Goal:** Render slices/3D to PNG; QIDO/WADO and Orthanc pull both work.

### Batch 1 — Render ✓

- [x] `render slice [--view --orientation --offset --scroll-to --size] --out path|-` (commit `a67f114`)
- [x] `render threed [--look A|P|L|R|S|I] --out path|-` (`a67f114`)
- [x] `render screenshot --out path|-` (warns via 5xx if main-window absent) (`a67f114`)
- [x] `render gltf [--widget 0] --out path|-` (`a67f114`)
- [x] Binary output handling: `--out path` or `-` (stdout); JSON envelope to stderr in `--json` mode (reused Phase-1 `render_meta_to_stderr`)
- [x] Empty/black-PNG detection (catches headless-without-Mesa) → `E_BAD_RESPONSE` with literal `GALLIUM_DRIVER=llvmpipe` hint (`a67f114`)

### Batch 2 — DICOMweb read ✓

- [x] `dicom studies [--patient --limit --offset]` (commit `9dcaf2f`)
- [x] `dicom series <studyUID>` (`9dcaf2f`)
- [x] `dicom instances <studyUID> <seriesUID>` (`9dcaf2f`)
- [x] `dicom instance <studyUID> <seriesUID> <sopUID> --out path|-` (WADO-RS) (`9dcaf2f`)
- [x] `dicom meta <studyUID> [<seriesUID> [<sopUID>]]` (variadic CLI, three client methods) (`9dcaf2f`)
- [x] `Route` dataclass `note` field + `accessDICOMwebStudy` flagged with §8.1 bug pointer (`9dcaf2f`)
- [x] DICOM JSON tag-flatten helpers in `client/_dicom_tags.py` (`9dcaf2f`)
- [x] `StudyRef` / `SeriesRef` / `InstanceRef` pydantic models with `.raw` blob preserved (`9dcaf2f`)

### Batch 3 — `dicom pull` via /exec ✓

- [x] `dicom pull --orthanc <prefix> --study <UID> [--store dicom-web] [--token T]` (commit `b3be863`)
- [x] `client/_exec.py::build_exec_payload` — single insertion point for Phase 3's audit-log; `mrml.save_scene` refactored to use it (`b3be863`)
- [x] `dicom pull` 5xx hint surfaces cleanly when /exec disabled (the documented Slicer-side bug workaround) (`b3be863`)
- [x] Orthanc autouse skip fixture in `tests/integration/conftest.py` + `requires_orthanc` marker (`b3be863`)
- [x] End-to-end Orthanc → Slicer round-trip integration test against a developer-supplied CXR fixture (UIDs read from gitignored `tests/integration/.env`; skips cleanly if Orthanc DICOMweb or the env vars are unavailable) (`b3be863`)
- [x] Unit + integration tests

### Cross-cutting ✓

- [x] Update User Manual `docs/Slicer-CLI-UserManual.md`: promote render/dicom out of §4.6, add §5.6 render workflows, §5.7 Orthanc workflow (placeholder UIDs only; PHI kept out)
- [x] Update `src/slicer_cli/AGENTS.md`: validators / exec / DICOM tag-flatten patterns documented
- [x] Update `tests/AGENTS.md`: PNG fixture pattern + Orthanc skip pattern + DICOM JSON shape notes
- [x] Update root `AGENTS.md`: status line bumped to Phases 0+1+2 complete

---

## Phase 3 — Markup + exec + gui ✓

**Goal:** Templated `/exec`-backed markups; gated `exec` with audit log.

**Plan file:** `~/.claude/plans/glimmering-painting-lagoon.md` (3 batches)

### Batch 1 — Audit infrastructure ✓

- [x] `client/_internal/audit.py::AuditLogger` — PRD §8.3 line format with `rev`, `url`, `hash`, `preview`, `op` (mkdir parents on first write)
- [x] Audit-log line format: `<iso8601>  rev=<rev>  url=<url>  hash=sha256:<hex>  preview="<first 200 chars>"  op=<label>`
- [x] `_HttpClient.audit_logger` kwarg + `_post_exec(source, *, op_label)` funnel — single insertion point for all `/slicer/exec` POSTs
- [x] `mrml.save_scene` and `dicom.pull_from_dicomweb` retroactively routed through the audited funnel (audit happens automatically)
- [x] `tests/conftest.py` autouse-redirects audit writes to per-session tmp dir; `audit_log_path` fixture for tests that inspect output
- [x] 8 new unit tests for `AuditLogger` (format, mkdir, append, permission errors); 1 dicom-pull audit assertion

### Batch 2 — Markup commands ✓

- [x] `markup list [--type fiducial|segmentation]` (merged view by default; per-type for full detail)
- [x] `markup fiducial-set --id ID --index N --r R --a A --s S` (PUT `/slicer/fiducial`; refuses empty id)
- [x] `markup line --p1 R,A,S --p2 R,A,S [--name N]` (templated `/slicer/exec`; audited via the funnel)
- [x] `MarkupMixin` + `models/markup.py` (`FiducialNode`, `SegmentationNode`, `MarkupRef`, `LineMarkupResult`)
- [x] `_render_markup_list` renderer in `output.py`
- [x] 13 unit tests + integration test (live `markup line` create + `node delete` cleanup)

### Batch 3 — Formal exec + gui layout + cross-cutting ✓

- [x] `exec --code '...'` / `exec --file path.py` via `_HttpClient.run_python` (audited)
- [x] `--no-audit-log` flag emits stderr warning but still proceeds (YOLO honours it)
- [x] `--i-understand-the-risk` flag required when `config.exec.enabled = false`
- [x] `cli/_internal/safety.py::require_exec_enabled(config, *, override)` gate
- [x] `gui layout LAYOUT [--contents full|viewers]` (PUT `/slicer/gui`); `GuiMixin` + `_render_gui_layout`
- [x] `_render_exec_result` renderer (k=v fallback for ad-hoc Slicer payloads)
- [x] `render_warning(...)` helper in `output.py` for the `--no-audit-log` stderr line
- [x] 13 new unit tests (`test_gui.py`, `test_exec_command.py`); 2 integration tests (formal-exec round-trip, `gui layout` switch+restore)

### Cross-cutting ✓

- [x] User Manual: §4.8 (markup), §4.9 (formal exec + audit), §4.10 (gui), §5.8 (templated workflows + audit log), §5.9 (markup workflows), §5.10 (gui layout switching); status bumped to Phases 0–3 complete
- [x] `src/slicer_cli/AGENTS.md`: documented audited POST funnel rule, AuditLogger pattern, `require_exec_enabled` gate
- [x] `tests/AGENTS.md`: documented `audit_log_path` fixture pattern + `--i-understand-the-risk` gating-test pattern

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
