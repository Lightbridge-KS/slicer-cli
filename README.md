# Slicer CLI

> Unofficial agent-first CLI for [3D Slicer](https://www.slicer.org/)'s
> in-process HTTP WebServer (default `127.0.0.1:2016`), so AI coding agents
> and humans can drive Slicer from outside the application.

The CLI speaks JSON envelopes with stable error codes (`E_*`), refuses
empty MRML selectors, gates destructive operations behind `--confirm`,
and ships an [Agent Skills Spec](https://agentskills.io/specification)–
compliant skill so any compatible AI agent can learn the surface on first
contact.

```bash
slicer-cli --json status            # is Slicer up?
slicer-cli --json volume list       # what's loaded?
slicer-cli --json render slice \
  --orientation axial --offset 12 \
  --out /tmp/ax.png                 # render an axial slice
```

## Features

- **Agent-first JSON output** — one envelope per call; branch on stable
  `error.code` strings, never on message text.
- **Safe by default** — `scene clear`, `system shutdown`, `node delete ""`,
  and `exec` are all gated by explicit flags or refused outright.
- **Reusable typed Python client** — `slicer_cli.client.SlicerClient` is
  importable on its own; the CLI is just one consumer.
- **Bundled AI agent skill** — drop-in skill at
  `.agents/skills/slicer-cli/` for any [Agent Skills](https://agentskills.io)–
  compatible agent (Claude Code, Codex, Cursor, Goose, OpenHands, …).

## Prerequisites

- [3D Slicer](https://download.slicer.org/) **5.x**, with the **Web Server**
  module started (Slicer → *Welcome* → search "Web Server" → **Start
  server**).
- **Python 3.11+** and [`uv`](https://docs.astral.sh/uv/).

## Installation

For now (alpha; not yet on PyPI), install from source:

```bash
git clone https://github.com/Lightbridge-KS/slicer-cli.git
cd slicer-cli
uv sync
```

Verify against your running Slicer:

```bash
uv run slicer-cli status
# ✓ Slicer is up at http://127.0.0.1:2016
#   applicationName     Slicer
#   applicationVersion  5.11.0-...
```

Once published, the planned distribution path is:

```bash
uv tool install slicer-cli      # persistent
uvx slicer-cli status           # ephemeral
```

The CLI binary registers two console entry points: `slicer-cli` and the
short alias `slcli`.

## Basic CLI usage

```bash
# Liveness probe + version.
slicer-cli status

# Capability matrix (render, dicomweb, power-tool-endpoint, ...).
slicer-cli doctor

# What's loaded?
slicer-cli volume list
slicer-cli scene nodes --class vtkMRMLScalarVolumeNode

# Render a sagittal slice 12 mm anterior of origin from the green viewer.
slicer-cli render slice \
  --view green --orientation sagittal --offset 12 --size 512 \
  --out /tmp/sag.png

# Export a volume to NRRD on disk.
slicer-cli volume export vtkMRMLScalarVolumeNode1 --out /tmp/mr.nrrd

# Discover the underlying HTTP surface, offline.
slicer-cli api routes --json | jq '.routes[] | select(.note != null)'
```

Pass `--json` for one-line JSON envelopes (the agent default); leave it
off for human-friendly tables on a TTY. The full surface and every flag
lives in [`docs/Slicer-CLI-UserManual.md`](./docs/Slicer-CLI-UserManual.md).

## AI agent skill

This repo bundles an [Agent Skills Spec](https://agentskills.io/specification)–
compliant skill at:

```
.agents/skills/slicer-cli/
├── SKILL.md
└── references/
    ├── commands.md         # full command surface
    ├── errors.md           # E_* codes ↔ exit codes
    ├── safety.md           # destructive ops, exec gating, audit log
    ├── dicomweb.md         # Orthanc → Slicer pull → QIDO/WADO
    └── troubleshooting.md  # symptom → cause → fix
```

The skill is **agent-agnostic** — it is plain Markdown with YAML
frontmatter per the spec, so any compatible agent can load it.

### Use with Claude Code

A symlink at `.claude/skills/slicer-cli → ../../.agents/skills/slicer-cli`
is already wired in this repo, so opening this directory in Claude Code
picks the skill up automatically. To enable it in **other** repos on the
same machine, symlink it into your user skills directory once:

```bash
ln -s "$(pwd)/.agents/skills/slicer-cli" ~/.claude/skills/slicer-cli
```

### Use with other agents

Point your agent's skills directory at `.agents/skills/slicer-cli/`. The
[Agent Skills client list](https://agentskills.io/) covers the loading
mechanism for each one (Claude, Codex, Cursor, Gemini CLI, Goose,
OpenHands, OpenCode, GitHub Copilot, Roo, Kiro, and many more).

### Try the skill

Once the skill is wired into your agent of choice, prompt it with
something like:

> *"Load MRHead in Slicer and render an axial slice at offset 12 mm."*

A compatible agent should auto-activate the skill, run
`slicer-cli --json status` first, find the volume by name, and write a
PNG to disk — branching on `error.code` if anything fails.

## Documentation

| Doc | Audience | Purpose |
|---|---|---|
| [`docs/Slicer-CLI-UserManual.md`](./docs/Slicer-CLI-UserManual.md) | agents + humans | full command surface, error codes, examples |
| [`docs/Slicer-CLI-PRD.md`](./docs/Slicer-CLI-PRD.md) | maintainers | locked design decisions, contracts, rationale |
| [`docs/3d-slicer-webserver-surface-report.md`](./docs/3d-slicer-webserver-surface-report.md) | maintainers | authoritative reference for Slicer's HTTP surface (incl. known bugs) |
| [`AGENTS.md`](./AGENTS.md) | AI coding agents | repo-wide project conventions |
| [`.agents/skills/slicer-cli/SKILL.md`](./.agents/skills/slicer-cli/SKILL.md) | AI coding agents | when/how to invoke the CLI |

## Status

Alpha — Phases 0–3 shipped (core read/write + render + DICOMweb + markup
+ formal `exec` + GUI layout + audit log). Phase 4 (this skill) is the
current iteration. See [`docs/TODOS.md`](./docs/TODOS.md) for the live
phase tracker.

## License

[MIT](./LICENSE)
