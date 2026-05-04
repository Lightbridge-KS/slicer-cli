# Slicer CLI

> Agent-first CLI wrapper around 3D Slicer's in-process HTTP server (`127.0.0.1:2016` by default), so an AI coding agent and a human developer can drive Slicer from outside the application.

## Project

- **Name:** `slicer-cli`
- **Language:** Python 3.11+ (managed by `uv`)
- **Mental model:** `cli/` is thin Typer glue; `client/` is a reusable typed Python API. Both ship together.

## Where to learn more

| When working in | Read this (auto-loaded) |
|---|---|
| Anywhere in repo | `AGENTS.md` (this file) |
| `src/slicer_cli/**` | `src/slicer_cli/AGENTS.md` |
| `tests/**` | `tests/AGENTS.md` |

For *what* and *why* (not auto-loaded — read on demand):

- [`docs/Slicer-CLI-PRD.md`](./docs/Slicer-CLI-PRD.md) — vision, command surface, output contract, safety guardrails
- [`docs/Slicer-CLI-UserManual.md`](./docs/Slicer-CLI-UserManual.md) — agent-and-human-facing manual (commands, error codes, examples)
- [`docs/TODOS.md`](./docs/TODOS.md) — live phase tracker
- [`docs/3d-slicer-webserver-surface-report.md`](./docs/3d-slicer-webserver-surface-report.md) — authoritative reference for Slicer's HTTP surface (incl. known bugs)

## Commands

| What | Command |
|---|---|
| Install / sync deps | `uv sync` |
| Run CLI | `uv run slicer-cli <args>` |
| Unit tests | `uv run pytest -m "not integration"` |
| Integration tests (live Slicer) | `SLICER_INTEGRATION=1 uv run pytest` |
| Lint / format / typecheck | `uv run ruff check` · `uv run ruff format` · `uv run mypy` |
| Smoke test | `uv run slicer-cli status --json` |

## Project-wide conventions

- **Strict typing.** `mypy --strict` clean. No `Any` in the public client API. Use `from __future__ import annotations` and `X | None` syntax.
- **Docstrings:** casual one-liners by default; NumPy style for public APIs that warrant it.
- **Comments:** only when *why* is non-obvious. Don't paraphrase code.
- **Class layout:** public methods before private.
- **No emojis** unless the user asks. (Rich markup like `[bold]…[/]` is allowed inside `cli/output.py` only — see `src/slicer_cli/AGENTS.md`.)
- **Commits:** Conventional Commits (`feat(cli): …`, `fix(client): …`, `docs: …`).
