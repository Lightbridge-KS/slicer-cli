# Slicer CLI

> A convenient CLI wrapper around 3D Slicer's in-process HTTP Web Server (port 2016), so that an AI coding agent and a human developer can drive Slicer from outside the application

## Project

- **Name:** `slicer-cli`
- **Goal:** Agent-first CLI wrapper around 3D Slicer's HTTP server (`127.0.0.1:2016` by default).
- **Primary language:** Python 3.11+ (managed by `uv`).

## Where to learn more

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


## How to work in this repo

- Keep changes small and incremental. One command at a time, with tests beside it.
- Update `docs/TODOS.md` checkboxes as items land. Reference the commit hash in the line you tick.
- Update `docs/Slicer-CLI-PRD.md` if a scope decision changes — never silently drift.

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
- **Docstrings:** casual one-liners by default; NumPy style only for public APIs that warrant it.
- **Comments:** only when *why* is non-obvious. Don't paraphrase the code.
- **Class layout:** public methods before private.
- **No emojis** unless the user asks for them. (Rich markup like `[bold]…[/]` is a different thing — see `src/slicer_cli/AGENTS.md` for where it's allowed.)
