# Slicer CLI

> A convenient CLI for AI Agent and human to interact with 3D Slicer Webserver.

This file is the project-local agent guide for the **whole repo**. It is symlinked from `CLAUDE.md`, so editing either propagates to both.

## Where to learn more

Progressive disclosure — load only what's relevant to where you're editing:

| When working in | Read this file (auto-loaded) |
|---|---|
| Anywhere in repo | `AGENTS.md` (this file) |
| `src/slicer_cli/**` | `src/slicer_cli/AGENTS.md` (source-tree rules) |
| `tests/**` | `tests/AGENTS.md` (testing patterns) |

For the *what* and *why*, not the *how*:

- [`docs/Slicer-CLI-PRD.md`](./docs/Slicer-CLI-PRD.md) — vision, command surface, output contract, safety guardrails, architecture
- [`docs/Slicer-CLI-UserManual.md`](./docs/Slicer-CLI-UserManual.md) — agent-and-human-facing manual for the Phase-1 surface (commands, error codes, worked examples)
- [`docs/TODOS.md`](./docs/TODOS.md) — live phase tracker (what's done, what's next)
- [`docs/3d-slicer-webserver-surface-report.md`](./docs/3d-slicer-webserver-surface-report.md) — authoritative reference for Slicer's HTTP surface

## Project

- **Name:** `slicer-cli`
- **Goal:** Agent-first CLI wrapper around 3D Slicer's HTTP server (`127.0.0.1:2016` by default).
- **Primary language:** Python 3.11+ (managed by `uv`).
- **Status:** Phases 0 + 1 + 2 + 3 complete (read/write + render + DICOMweb + markup + gated/audited `exec` + `gui layout` ship); Phase 4 (`doctor` extensions, alt-port discovery, MCP server) is next per `docs/TODOS.md`.

## How to work in this repo

- Keep changes small and incremental. One command at a time, with tests beside it.
- Update `docs/TODOS.md` checkboxes as items land. Reference the commit hash in the line you tick.
- Update `docs/Slicer-CLI-PRD.md` if a scope decision changes — never silently drift.
- Add/update tests for behaviour changes (PRD §13 DoD).

## Commands

| What | Command |
|---|---|
| Install / sync deps | `uv sync` |
| Run CLI | `uv run slicer-cli <args>` |
| Unit tests | `uv run pytest -m "not integration"` |
| Integration tests (needs live Slicer) | `SLICER_INTEGRATION=1 uv run pytest` |
| Lint | `uv run ruff check` |
| Format | `uv run ruff format` |
| Type check | `uv run mypy` |
| Smoke test | `uv run slicer-cli status --json` |

## Coding conventions (project-wide)

- **Conventional Commits.** Examples: `feat(cli): add scene clear`, `fix(client): map 400 to E_HTTP_4XX`, `docs(prd): lock §14.2`.
- **Strict typing.** `mypy --strict` clean. No `Any` in the public client API. Use `from __future__ import annotations` and modern union syntax (`X | None`).
- **Docstrings:** casual one-liners by default; NumPy style only for public APIs that warrant it (per `~/.claude/CLAUDE.md`).
- **Comments:** only when *why* is non-obvious. Don't paraphrase the code.
- **Class layout:** public methods before private (per `~/.claude/CLAUDE.md`).
- **No emojis** unless the user asks for them. (Rich markup like `[bold]…[/]` is a different thing — see `src/slicer_cli/AGENTS.md` for where it's allowed.)

## Definition of done (per checklist item)

- [ ] Code works for the requested scope
- [ ] Unit tests pass (`respx` mocks)
- [ ] Integration test passes against live Slicer (when applicable)
- [ ] `ruff check` + `ruff format --check` clean
- [ ] `mypy` clean
- [ ] PRD / TODOS updated if scope shifted
- [ ] Conventional Commits message
