# Slicer CLI — Product Requirements Document

| Field | Value |
|---|---|
| Status | **Locked v0.2 — implementation underway** (open questions in §14.2 answered; plan at `~/.claude/plans/glimmering-painting-lagoon.md`; tracker at [`TODOS.md`](./TODOS.md)) |
| Author | Claude (drafted), Kittipos (owner) |
| Last updated | 2026-05-03 |
| Repo | `tools/slicer-cli/` |
| Related docs | [`3d-slicer-webserver-surface-report.md`](./3d-slicer-webserver-surface-report.md) (authoritative API surface), [`3d-slicer-web-server-scrape.md`](./3d-slicer-web-server-scrape.md) (Slicer's own index page) |

---

## 1. Vision

Build **`slicer-cli`** — a thin, typed, agent-first CLI wrapper around 3D Slicer's in-process HTTP server (port 2016), so that an AI coding agent (and, secondarily, a human developer) can drive Slicer from outside the application without writing `curl` boilerplate, without memorising substring-routing rules, and without ever accidentally clearing a scene by sending an empty `DELETE`.

The CLI is one of two co-shipped artifacts:

```
┌────────────────────────────┐    ┌─────────────────────────────┐
│   slicer-cli (this PRD)    │    │   slicer-cli skill (sibling)│
│   Python package + binary  │    │   Markdown SKILL.md telling │
│   that wraps the REST API  │    │   Claude when/how to use it │
└──────────────┬─────────────┘    └─────────────┬───────────────┘
               │                                │
               └────────────► used together ◄───┘
```

This PRD covers the CLI. The skill artifact is summarised in §12.

---

## 2. Goals & non-goals

### 2.1 Goals (MVP)

1. **Cover the high-value 80% of `/slicer/*` and `/dicom/*` routes** — liveness, sample data, scene/node listing, volume I/O, file load/save, slice/3D rendering, DICOMweb QIDO/WADO, DICOMweb pull from Orthanc, gated `exec`, system shutdown.
2. **Be safe-by-default** — no command can wipe a scene, run arbitrary Python, or shut down Slicer without an explicit, named flag.
3. **Be agent-first** — JSON output is a first-class citizen with stable schemas; help text is dense and machine-parseable; errors carry typed codes; no interactive prompts; deterministic exit codes.
4. **Be human-friendly enough** — TTY-aware pretty output; `--help` reads naturally; reasonable defaults.
5. **Ship as a `uv tool install`-able package**, with `uvx slicer-cli` for ephemeral use.

### 2.2 Non-goals (explicit)

- **Not** a Slicer module. We do not author Python code that runs *inside* Slicer (except as templated `/slicer/exec` payloads for a few specific tools).
- **Not** an MCP server (Phase 5+ candidate, but the CLI is the foundation, and an MCP can wrap it later).
- **Not** a GUI / TUI. Stdout text only.
- **Not** a DICOM viewer. We hand off to OHIF/VolView via URLs when relevant.
- **Not** a multi-instance orchestrator in MVP — single Slicer on a known port. Multi-instance discovery is Phase 4.
- **Not** a write-back DICOMweb (STOW) implementation by ourselves; we rely on Slicer's bundled `dicomweb_client` via templated `exec`.

---

## 3. Personas

### 3.1 Primary — Claude / Codex / OpenClaw / Etc. (the AI agent)

**What it needs.** Predictable, parseable output. Self-describing help. Zero ambiguity about what's destructive. Error messages that tell it the *fix*, not the symptom. Stable command names that don't churn.

**What it should have:** Pretty colours (keep it ergonomic for human too)

**What it does NOT need.** Progress bars, ASCII art in normal output, interactive Y/N prompts, environment-variable surprises.

### 3.2 Secondary — Kittipos (radiologist / developer)

**What it needs.** Quick keystrokes for common probes (`slicer-cli status`), readable defaults at the terminal, `--json` to drop into `jq`/`yq` pipelines. Fits with existing tools (`rg`, `fd`, `jq`).

### 3.3 Tertiary — future MCP server author

**What it needs.** Stable internal Python API (`slicer_cli.client.SlicerClient`) so the MCP server can import the same code that backs the CLI, instead of shelling out to the binary.

---

## 4. UX principles (agent-first)

These are the design rules every command must obey. They are derived from the constraints documented in the surface report.

| # | Principle | Why |
|---|---|---|
| P1 | **Resource-verb taxonomy** (`slicer-cli volume list`, not `slicer-cli list-volumes`). | Mirrors REST mental model; agent can predict commands it hasn't seen. |
| P2 | **JSON output on `--json`; human output on a TTY by default.** | Humans see tables, agents pipe JSON. Both happy. |
| P3 | **Destructive operations require a named flag** (`--confirm`, `--yes`, `--allow-exec`). | An agent that forgets the flag gets an error, not a wiped scene. |
| P4 | **No interactive prompts.** Ever. | Agents can't answer them. |
| P5 | **Stable JSON schemas.** Documented, versioned, never changed silently. | Agents pattern-match on field names. Renaming = breakage. |
| P6 | **Errors are typed.** `{error: {code, message, hint}}` with stable `code` strings (`E_NOT_RUNNING`, `E_EXEC_DISABLED`, `E_EMPTY_SELECTOR`, ...). | Agent branches on `code`, shows `message` to user, applies `hint`. |
| P7 | **Deterministic exit codes.** `0` ok, `1` user error, `2` slicer error, `3` network error, `4` config error, `5` exec disabled, `>=10` reserved. | Shell pipelines and agent retry logic both depend on this. |
| P8 | **Discoverability via `--help`, `doctor`, and a route-to-command index.** | Agents discover capability without external docs. |
| P9 | **No magic environment defaults beyond `SLICER_URL`.** Hostname is explicit when not loopback. | Avoids "wait, *which* Slicer did I just talk to?" |
| P10 | **Idempotency where possible.** `volume import` of the same file twice is fine; `system shutdown` on a dead Slicer is a no-op-success. | Agent retries are safe. |

---

## 5. User-facing CLI surface

### 5.1 Naming & invocation

- **Package name:** `slicer-cli`
- **Binary name:** `slicer-cli` (avoids collision with the actual Slicer.app brew binary `slicer`; alias `slcli` registered as a console-script for fast typing — to be confirmed in §14).
- **Module name:** `slicer_cli` (Python convention).
- **Help system:** `slicer-cli --help`, `slicer-cli <group> --help`, `slicer-cli <group> <verb> --help`. All sections are <100 lines.

```
slicer-cli [--url URL] [--json|--pretty] [--quiet] [--timeout N] <group> <verb> [args]
```

### 5.2 Command taxonomy

```
slicer-cli
├── status                       liveness probe + version (the "is it on?" command)
├── doctor                       run a battery of capability probes
├── version                      CLI's own version
│
├── system
│   ├── version                  GET  /slicer/system/version
│   ├── shutdown   --confirm     DELETE /slicer/system        (destructive)
│   └── settings   (Phase 2)     introspect WebServer module flags
│
├── scene
│   ├── nodes      [--class C] [--name N]      list MRML nodes  (id+name+class)
│   ├── ids        [--class C] [--name N]      ids only (terse, for piping)
│   ├── clear      --confirm                   wipe scene       (destructive)
│   ├── save       <path>                      save scene to .mrb / .mrml
│   └── load       <path>                      load scene file  (filetype=SceneFile)
│
├── node
│   ├── show       <id>                        properties of one node
│   ├── delete     <id>                        delete by id (rejects empty)
│   └── reload     <id>                        reload from original file
│
├── volume
│   ├── list                                   list scalar+labelmap volumes (id, name)
│   ├── show       <id>                        node properties for one volume
│   ├── export     <id> [--format nrrd]        stream volume bytes (NRRD; saves to --out or stdout)
│   │             [--out path]
│   ├── import     <path> [--name N]           load file as volume (POST /mrml ?filetype=VolumeFile)
│   └── delete     <id>                        delete volume node
│
├── sample
│   ├── list                                   curated allow-list of SampleData names
│   └── load       <name>                      GET /slicer/sampledata?name=...
│
├── render
│   ├── slice      [--view red|yellow|green]   GET /slicer/slice
│   │             [--orientation axial|sagittal|coronal]
│   │             [--offset MM] [--scrollTo 0..1]
│   │             [--size PX] [--out path|-]
│   ├── threed     [--look A|P|L|R|S|I]        GET /slicer/threeD
│   │             [--out path|-]
│   ├── screenshot [--out path|-]              GET /slicer/screenshot   (warn: needs main window)
│   └── gltf       [--widget 0] [--out path]   GET /slicer/threeDGraphics
│
├── markup
│   ├── list       [--type fiducial|line|...]  templated /exec → JSON
│   ├── fiducial-set --id ID --index N         PUT /slicer/fiducial
│   │              --r R --a A --s S
│   ├── line       --p1 R,A,S --p2 R,A,S       templated /exec creating vtkMRMLMarkupsLineNode
│   │              [--name N]
│   └── (Phase 2)  angle, plane, roi, curve    all templated /exec wrappers
│
├── dicom
│   ├── studies    [--patient PID] [--limit N] [--offset N]
│   ├── series     <studyUID>
│   ├── instances  <studyUID> <seriesUID>
│   ├── instance   <studyUID> <seriesUID> <sopUID> [--out path]   (WADO-RS retrieve)
│   ├── meta       <studyUID> [<seriesUID> [<sopUID>]]            (QIDO/WADO metadata)
│   └── pull       --orthanc <prefix> --study <UID>               (POST /slicer/accessDICOMwebStudy)
│                  [--store dicom-web] [--token T]
│
├── gui            (Phase 2)
│   └── layout     fourup|oneup3d|... [--contents full|viewers]   PUT /slicer/gui
│
├── exec           --code '...' | --file path.py
│                  --i-understand-the-risk     (required, see §8)
│                  [--audit-log path]
│
├── api
│   ├── routes                  list known endpoints (offline, from package)
│   └── raw        <method> <path> [--query K=V ...] [--body @file]
│                                  escape hatch for endpoints we haven't wrapped
│
└── config
    ├── show
    ├── set        <key> <value>
    ├── get        <key>
    └── path                     print config file location
```

### 5.3 Worked examples

Agent-flavoured (with `--json`):

```bash
# 1. Probe and assert Slicer is live before doing anything else
$ slicer-cli status --json
{"ok": true, "url": "http://127.0.0.1:2016", "applicationName": "Slicer",
 "applicationVersion": "5.11.0-2026-04-25", "releaseType": "Preview"}

# 2. Load a sample, then list resulting volumes
$ slicer-cli sample load MRHead --json
{"ok": true, "name": "MRHead"}

$ slicer-cli volume list --json
{"volumes": [{"id": "vtkMRMLScalarVolumeNode1", "name": "MRHead", "class": "vtkMRMLScalarVolumeNode"}]}

# 3. Render an axial slice at offset 12 mm to a file
$ slicer-cli render slice --orientation axial --offset 12 --size 512 --out /tmp/mr.png --json
{"ok": true, "path": "/tmp/mr.png", "bytes": 84102, "view": "red", "offset": 12.0}

# 4. Pull a study from Orthanc
$ slicer-cli dicom pull --orthanc http://localhost:8042 --study 1.2.840... --json
{"ok": true, "studyUID": "1.2.840...", "loaded": true}

# 5. Save a volume to disk on the Slicer host
$ slicer-cli volume export vtkMRMLScalarVolumeNode1 --out /tmp/mr.nrrd --json
{"ok": true, "path": "/tmp/mr.nrrd", "format": "nrrd", "bytes": 4196352}
```

Human-flavoured (TTY, no `--json`):

```
$ slicer-cli status
✓ Slicer is up at http://127.0.0.1:2016
  applicationName     Slicer
  applicationVersion  5.11.0-2026-04-25 (Preview)
  arch / os           amd64 / macosx

$ slicer-cli volume list
ID                              NAME       CLASS
vtkMRMLScalarVolumeNode1        MRHead     vtkMRMLScalarVolumeNode
```

Destructive guardrails:

```
$ slicer-cli scene clear
Error: scene clear is destructive. Pass --confirm to proceed.
       This will call DELETE /slicer/mrml with no selectors, which clears the
       entire MRML scene (slicer.mrmlScene.Clear()).
[exit 1]

$ slicer-cli node delete
Error: missing required argument <id>.
       Empty selectors on DELETE /slicer/mrml clear the scene; this CLI never
       sends an empty DELETE. Use `slicer-cli scene clear --confirm` for that.
[exit 1]

$ slicer-cli exec --code 'import slicer; slicer.app.quit()'
Error: exec is disabled. /slicer/exec runs arbitrary Python with the privileges
       of the user running Slicer.
       Enable per-call: --i-understand-the-risk
       Enable in config: slicer-cli config set exec.enabled true
[exit 5]
```

---

## 6. Output contract

### 6.1 Modes

| Mode | When | Format |
|---|---|---|
| `--json` (or stdout not a TTY *and* config `output.auto_json=true`) | Agent / pipeline | One JSON object per invocation, ending with `\n`. |
| `--pretty` (default on TTY) | Human at terminal | Tables, colour, headings via `rich`. |
| `--quiet` | Health checks in scripts | Empty stdout on success; stderr unaffected. |

> **Default policy:** human on TTY, JSON when piped is *not* automatic in MVP — too surprising. We default to human and require `--json` explicitly. The skill (§12) instructs Claude to always pass `--json`.

### 6.2 JSON envelope (success)

```json
{
  "ok": true,
  "<resource>": ...,
  "_meta": {
    "endpoint": "/slicer/volumes",
    "elapsed_ms": 12,
    "slicer_version": "5.11.0-2026-04-25"
  }
}
```

`_meta` is opt-in via `--meta` to avoid bloat.

### 6.3 JSON envelope (error)

```json
{
  "ok": false,
  "error": {
    "code": "E_EXEC_DISABLED",
    "message": "exec is disabled by configuration",
    "hint": "pass --i-understand-the-risk or run: slicer-cli config set exec.enabled true",
    "endpoint": "/slicer/exec",
    "http_status": null
  }
}
```

### 6.4 Stable error codes (initial set)

```
E_NOT_RUNNING      — couldn't reach Slicer at the configured URL
E_NETWORK          — TCP/HTTP error other than refused
E_HTTP_4XX         — Slicer returned a 4xx
E_HTTP_5XX         — Slicer returned a 5xx (often /exec failures)
E_EMPTY_SELECTOR   — refused to send a DELETE/GET with empty mrml selectors
E_DESTRUCTIVE      — refused destructive op without --confirm
E_EXEC_DISABLED    — /exec gated off
E_BAD_INPUT        — argument validation failed locally
E_BAD_RESPONSE     — JSON we couldn't parse (Slicer schema drift)
E_TIMEOUT          — exceeded --timeout
E_CONFIG           — config file invalid
E_NOT_IMPLEMENTED  — endpoint exists in Slicer but is a known stub (segmentation, gridTransform POST)
```

### 6.5 Exit codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | User error (bad args, missing flag, validation) |
| 2 | Slicer-side error (4xx/5xx with a sensible code) |
| 3 | Network / connectivity (E_NOT_RUNNING, E_NETWORK, E_TIMEOUT) |
| 4 | Config (E_CONFIG) |
| 5 | Exec disabled (E_EXEC_DISABLED) |
| 6 | Destructive without confirm (E_DESTRUCTIVE, E_EMPTY_SELECTOR) |
| 7 | Not implemented in current Slicer build (E_NOT_IMPLEMENTED) |
| 10+ | Reserved for future categories |

---

## 7. Configuration

### 7.1 Sources, in precedence order

1. CLI flags (`--url`, `--timeout`, ...)
2. Environment (`SLICER_URL`, `SLICER_TIMEOUT`, `SLICER_EXEC_ALLOW`, ...)
3. Project-local `.slicer-cli.toml` (cwd or first ancestor)
4. User config `~/.config/slicer-cli/config.toml` (XDG)
5. Built-in defaults

### 7.2 Defaults

```toml
# ~/.config/slicer-cli/config.toml
[server]
url = "http://127.0.0.1:2016"
timeout_seconds = 30
discover_alt_ports = false       # Phase 4

[output]
default = "pretty"               # "pretty" | "json"
include_meta = false

[exec]
enabled = true                   # YOLO default — /slicer/exec runs without --i-understand-the-risk
                                 # Flip to false for stricter posture (re-enables risk-flag gating)
audit_log = "~/.local/state/slicer-cli/exec.log"   # written unconditionally on every successful exec

[render]
default_size = 512
default_view = "red"
```

### 7.3 `slicer-cli doctor` output

```
$ slicer-cli doctor
Slicer reachable           ✓  http://127.0.0.1:2016
Slicer API enabled         ✓
DICOMweb API enabled       ✓
exec endpoint reachable    ✓  (enabled in Slicer's WebServer module)
exec gating in CLI         OFF (config.exec.enabled=true — YOLO default; risk flag not required)
main window present        ✓  (screenshot will work)
sample data: MRHead        ✓
render /slicer/slice       ✓  (returned 84102-byte PNG)
render /slicer/threeD      ✓
DICOM database             ✓  (3 studies, 8 series, 412 instances)
```

This single command answers most "what's broken?" questions for both humans and agents.

---

## 8. Safety guardrails

These are the rules that justify "agent-first" and prevent the failure modes called out in the surface report.

### 8.1 Empty selectors

Any wrapper around `/slicer/mrml` (GET / DELETE / PUT) **must** require at least one of `--id`, `--class`, `--name`, OR an explicit `--all` flag. Empty CLI args → `E_EMPTY_SELECTOR`. We never let an agent type `slicer-cli node delete` and have it mean "delete every node".

### 8.2 Scene clear

Only `slicer-cli scene clear --confirm` is allowed to send `DELETE /slicer/mrml` with no selectors. The `--confirm` flag is mandatory; there's no env override for it.

### 8.3 `exec` gating

```
                      ┌────────────────────────────────────────┐
                      │   slicer-cli exec invocation flow      │
                      └────────────────────────────────────────┘

  call → check config.exec.enabled
         │
         ├── enabled = true  ──► run
         │
         └── enabled = false ──► is --i-understand-the-risk set?
                                  │
                                  ├── yes ──► run + write audit-log line
                                  │            with timestamp + hash + first 200 chars
                                  │
                                  └── no  ──► E_EXEC_DISABLED, exit 5
```

Every successful `exec` call (whether via flag or config) emits one line to the audit log:
```
2026-05-03T19:42:11Z  rev=34516  url=http://127.0.0.1:2016  hash=sha256:1a2b…  preview="import slicer; __execResult={'volumes': …}"
```
The hash lets us verify exactly what ran without flooding the log with code.

### 8.4 Destructive endpoints listed once

The CLI internally tags these endpoints as "destructive":

| Endpoint | CLI command | Guard |
|---|---|---|
| `DELETE /slicer/mrml` (empty selectors) | `scene clear` | `--confirm` |
| `DELETE /slicer/mrml?id=…` | `node delete <id>` | `<id>` required, no empty |
| `DELETE /slicer/system` | `system shutdown` | `--confirm` |
| `POST /slicer/exec` | `exec` | gating in §8.3 |
| `POST /slicer/volume` (replaces a node) | `volume import-bytes` (Phase 2) | `--replace` flag |

### 8.5 Known-stub endpoints

`/slicer/segmentation` and `POST /slicer/gridTransform` return `E_NOT_IMPLEMENTED` proactively without making the call (we encode known-stub state per Slicer version in the package). The `api raw` escape hatch still allows hitting them if the user really wants to.

### 8.6 The `api raw` escape hatch

```
slicer-cli api raw GET /slicer/foo --query a=1 --query b=2
slicer-cli api raw POST /slicer/exec --body @code.py --i-understand-the-risk
```

Same gating still applies (e.g., `api raw POST /slicer/exec` requires the risk flag). The escape hatch is for *new* endpoints we haven't wrapped, not for *bypassing* safety.

---

## 9. Discovery & introspection

### 9.1 `slicer-cli api routes`

Prints the package's known route table (from a versioned data file generated from the surface report) — offline, no Slicer required.

```
$ slicer-cli api routes --json | jq '.routes[0]'
{
  "method": "GET",
  "path": "/slicer/system/version",
  "purpose": "App identity + version",
  "cli_command": "slicer-cli system version",
  "destructive": false,
  "stub": false
}
```

This is the agent's offline map of what's possible.

### 9.2 `--help`

Each `--help` follows the same shape:

```
slicer-cli volume export <id>

  Stream a volume node as bytes (currently NRRD only).

Arguments:
  <id>                  vtkMRMLScalarVolumeNode ID

Options:
  --format nrrd         output format (only nrrd is implemented in Slicer)
  --out PATH | -        write bytes here ('-' = stdout)
  --json                JSON envelope output

Endpoint:
  GET /slicer/volume?id=<id>

Notes:
  Slicer's POST /slicer/volume only accepts 3D / LPS / little-endian / raw /
  signed-short. For arbitrary uploads use `volume import` (file-based).
```

The `Endpoint:` and `Notes:` lines mean an agent reading `--help` learns the *underlying* call and its sharp edges, not just our wrapper.

### 9.3 `slicer-cli doctor`

Already shown in §7.3. Agent uses this when something doesn't work to localise the failure layer.

---

## 10. Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│  CLI layer (Typer)                                                       │
│   slicer_cli/cli/                                                        │
│   - one module per group: scene.py, volume.py, render.py, dicom.py, ...  │
│   - thin: parses flags → calls client method → formats output            │
└─────────────────────────────────┬────────────────────────────────────────┘
                                  │
                                  ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  Client layer (typed Python API)                                         │
│   slicer_cli/client/                                                     │
│     base.py           SlicerClient(httpx.Client)                         │
│     scene.py          .list_nodes(class_), .clear_scene(confirm=True)    │
│     volume.py         .list_volumes(), .export_volume(id), ...           │
│     render.py         .render_slice(...), .render_threed(...)            │
│     dicom.py          .qido_studies(), .pull_study(...)                  │
│     exec_.py          .execute(code, allow=False) → ExecResult           │
│     models.py         pydantic models for every response                 │
│     errors.py         SlicerError hierarchy → maps to E_* codes          │
│     routes.py         the route table data file                          │
└─────────────────────────────────┬────────────────────────────────────────┘
                                  │  HTTP (httpx, sync)
                                  ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  3D Slicer  WebServer module @ 127.0.0.1:2016                            │
│  (out of our control — single-threaded Qt event loop)                    │
└──────────────────────────────────────────────────────────────────────────┘
```

### 10.1 Why this split

- The **client layer is consumable on its own** — Phase-5 MCP server, Jupyter scratch-work in `_playground/`, integration tests. The CLI is *one* of its consumers.
- The **CLI layer has no HTTP knowledge** — it can be rewritten or wrapped without touching the client.
- **Pydantic models are the spine.** Every endpoint maps to a request model + response model. JSON Schema can be exported for the skill doc.

### 10.2 Module layout (proposed)

```
slicer-cli/
├── pyproject.toml
├── src/
│   └── slicer_cli/
│       ├── __init__.py
│       ├── client/
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── scene.py
│       │   ├── volume.py
│       │   ├── render.py
│       │   ├── dicom.py
│       │   ├── markup.py
│       │   ├── exec_.py
│       │   ├── models.py
│       │   ├── errors.py
│       │   └── routes.py
│       ├── cli/
│       │   ├── __init__.py
│       │   ├── app.py           # root Typer
│       │   ├── status.py
│       │   ├── doctor.py
│       │   ├── scene.py
│       │   ├── volume.py
│       │   ├── render.py
│       │   ├── dicom.py
│       │   ├── markup.py
│       │   ├── exec_.py
│       │   ├── api.py
│       │   └── config.py
│       ├── config.py            # toml + env + flag merging
│       └── output.py            # rich/json formatters
├── tests/
│   ├── unit/                    # respx-mocked
│   └── integration/             # real Slicer, gated by SLICER_INTEGRATION=1
├── docs/                        # this PRD lives here
└── skills/
    └── slicer-cli/
        └── SKILL.md             # the companion skill (§12)
```

### 10.3 Sequence — a typical command

```
agent or user  →  slicer-cli volume list --json
                       │
                       ▼
        cli/volume.py: list()
                       │ parse flags
                       ▼
        client/volume.py: SlicerClient.list_volumes()
                       │
                       ▼
        client/base.py: GET http://127.0.0.1:2016/slicer/volumes
                       │
                       ▼
        client/models.py: parse → list[Volume]
                       │
                       ▼
        cli/volume.py: format → JSON envelope
                       │
                       ▼
                    stdout
```

### 10.4 Error flow

```
httpx error                  → SlicerError(code=E_NETWORK, http=None)
HTTP 4xx/5xx with JSON body  → SlicerError(code=E_HTTP_*, http=status, message=body.message)
non-JSON body                → SlicerError(code=E_BAD_RESPONSE, ...)
local validation failure     → SlicerError(code=E_BAD_INPUT, ...)
                               │
                               ▼
              cli/output.py: render to JSON envelope or pretty stderr
                               │
                               ▼
                        sys.exit(map_code_to_exit(code))
```

---

## 11. Technology stack

| Layer | Choice | Why |
|---|---|---|
| Language | **Python 3.11+** | tomllib stdlib, modern type-hint syntax, matches user pref |
| Package mgr | **uv** | per user pref; `uv tool install slicer-cli` distribution; fast dev loop |
| Project layout | `uv init --lib` (src layout) | clean importability, plays nicely with `uv tool install` |
| HTTP | **httpx (sync)** | Slicer is single-threaded; sync is honest about that. Better testing story (`respx`) than `requests`. |
| CLI framework | **Typer** | type-hint-driven, mature, great `--help` rendering, well-known to LLMs. (Cyclopts is a more modern alternative — see §14 Q1.) |
| Validation/models | **pydantic v2** | typed responses, `model_dump()` → JSON envelope, JSON Schema export for the skill |
| Pretty output | **rich** | tables + TTY detection out of the box |
| Config | **tomllib** + **pydantic-settings** | env-var merging is built-in |
| Tests | **pytest** + **respx** + **pytest-httpx** | mocked unit tests; integration tier toggled by env var |
| Lint/format | **ruff** + **ruff format** | one tool, fast, industry-default |
| Type check | **mypy --strict** | matches user pref for explicit typing, no `Any` |

### 11.1 Packaging

- Console scripts: `slicer-cli`, `slcli` (alias).
- Distribution: PyPI. Install: `uv tool install slicer-cli`. Ephemeral: `uvx slicer-cli status`.
- No system-Python pollution (per user's Python execution policy).

### 11.2 Dev loop

```
uv sync                            # install
uv run slicer-cli status           # smoke test
uv run pytest                      # unit tests
SLICER_INTEGRATION=1 uv run pytest # integration tests (needs running Slicer)
uv run ruff check && uv run mypy
```

---

## 12. Companion skill

The skill artifact (`skills/slicer-cli/SKILL.md`) is what teaches Claude to use this CLI. It follows the standard Claude Code skill format:

```markdown
---
name: slicer-cli
description: Drive 3D Slicer (medical imaging app) over HTTP via the slicer-cli
             tool. Use when the user mentions Slicer, MRML, DICOM viewing/loading
             from a Slicer scene, or asks to render a slice/3D view from a volume
             they have loaded in Slicer.
---

# Always
- Run `slicer-cli status --json` first; bail with a friendly message if not OK.
- Pass `--json` to every command — the human-mode output is for the user, not you.
- Never call `slicer-cli scene clear` or `slicer-cli system shutdown` without
  explicit user instruction. The `--confirm` flag is a safety, not a checkbox.
- Treat `slicer-cli exec` as the last resort. Prefer named tools.
  ...
```

The skill cross-links to:
- `slicer-cli api routes --json` (offline route table)
- `slicer-cli doctor --json` (capability probe)
- The PRD's §8 (safety guardrails) so Claude understands *why* the rules exist.

This is in scope for the slicer-cli repo but technically a separate artifact; we'll author it in Phase 5.

---

## 13. Phasing

```
Phase 0  — scaffolding                              ~ 1 day
   uv init, src layout, Typer skeleton, config, output formatter,
   error types, status + version + doctor (no other endpoints).

Phase 1  — core read/write                          ~ 2–3 days
   volume list/show/export/import/delete
   scene nodes/ids/clear/save/load
   sample list/load
   system shutdown

Phase 2  — rendering + DICOM                        ~ 2–3 days
   render slice/threed/screenshot/gltf
   dicom studies/series/instances/instance/meta/pull

Phase 3  — markup + exec + raw                      ~ 2 days
   markup line/fiducial-set/list (templated /exec)
   exec --code/--file (gated)
   api raw (escape hatch)
   gui layout

Phase 4  — discovery + multi-instance               ~ 1–2 days
   port-discovery (probe 2016, 2017, ... when --discover)
   multi-instance config profiles

Phase 5  — companion skill + MCP groundwork         ~ 1 day for skill
   skill markdown
   pydantic JSON Schema export for MCP authors
```

Definition-of-done per phase:

- [ ] All commands in scope have unit tests with `respx` mocks
- [ ] All commands have integration tests (gated by env var) hitting a real Slicer
- [ ] `--help` for every command is reviewed for agent-readability
- [ ] Route table data file updated for any new wrapped endpoint
- [ ] `slicer-cli doctor` covers any new capability
- [ ] PRD updated if scope shifts

---

## 14. Risks & open questions

### 14.1 Risks

| # | Risk | Mitigation |
|---|---|---|
| R1 | Slicer endpoint surface drift between versions | Pin a `slicer_min_version` in package; `doctor` warns if mismatch; route table is versioned data, not code |
| R2 | `/exec` becomes the agent's hammer for everything | Hide it behind gating + audit log; cover the common cases with named commands so agents don't *need* exec |
| R3 | A render endpoint silently returns a black PNG (headless without Mesa) | `doctor` probes a render and checks PNG size/byte-entropy; surface explicit `E_BAD_RESPONSE` with a Mesa hint |
| R4 | Empty `DELETE` slip-through on `api raw` | The `api raw` route table tags `/slicer/mrml` DELETE as "needs selector"; refuse if none |
| R5 | TYpo / case-substring routing in Slicer (e.g., `/slicer/volume` matched before `/slicer/volumes`) | We always send full canonical paths; never let the user provide a path on commands other than `api raw` |
| R6 | Long-running `exec` blocks event loop and breaks subsequent calls | `--timeout` is mandatory on `exec`; default 30 s; doc explains "Slicer is single-threaded" |
| R7 | Agent over-uses `volume export` / `render slice` and saturates I/O | Cache layer (Phase 6 candidate); skill nudges agent toward "render once, reason many times" |

### 14.2 Locked decisions (was: open questions)

> **Status:** All resolved 2026-05-03. Audit trail preserved below in original Q + ANSWER form.
> Forward-looking artifacts: [`TODOS.md`](./TODOS.md) and `~/.claude/plans/glimmering-painting-lagoon.md`.

**Decision matrix (summary):**

| # | Topic | Locked answer |
|---|---|---|
| Q1 | CLI framework | **Typer** |
| Q2 | Binary name | **`slicer-cli`** + `slcli` alias |
| Q3 | Headless lifecycle (`serve start/stop`) | **OUT of MVP** |
| Q4 | JSON output default on non-TTY | Keep **pretty default**, explicit `--json` |
| Q5 | MCP server | **Deferred** (post-MVP) |
| Q6 | `exec.enabled` shipped default | **`true`** (YOLO; audit log unconditional) |
| Q7 | `AgentTools.py` Slicer-side helper | Same repo (`slicer_module/`), **deferred to Phase 3+** |
| Q8 | Multi-instance / extra GUI / advanced markups / render caching | **All OUT of MVP** |

---



1. **CLI framework — Typer or Cyclopts?**
   I picked Typer for breadth/maturity and because LLM training data covers it well. Cyclopts is more modern (better type inference, less ceremony). If you prefer Cyclopts, I'll switch — adds maybe a day of dev-loop adjustment.

ANSWER: Typer

2. **Binary name — `slicer-cli` (long, unambiguous) plus `slcli` alias?**
   Or do you prefer just `slcli`? Or `slicerctl` (kubectl style)?

ANSWER: `slicer-cli`

3. **Lifecycle management — should the CLI be able to spawn Slicer headless (`slicer-cli serve start`)?**
   Surface report covers the recipe (§2.3). It's high value but adds OS-specific complexity (Mesa on Linux, app-bundle paths on macOS, registry on Windows). I scoped this *out* of MVP. Agree?

ANSWER: YES, out of MVP Scope

4. **JSON output default on non-TTY?**
   I left default = `pretty`, with explicit `--json`. Auto-switching is more "agent-magical" but also more surprising for humans. The skill nudges Claude to pass `--json` always, so I think we're fine.

ANSWER: AGREE

5. **MCP server now or later?**
   I scoped MCP to Phase 5+ because the CLI is the foundation. If you want agent-via-MCP from day 1, we'd duplicate effort. I recommend CLI first, MCP second (the client library makes the MCP layer trivial when we get there).

ANSWER: No MCP yet

6. **`exec` enabled by default?**
   I left `enabled = false`. For your own dev loop you may want it on. The right answer is probably: off in shipped defaults, on in your local config. Confirm.

ANSWER: YOLO mode, let's enable `exec` by default.

7. **Custom Slicer-side helper module?**
   The surface report's §10.2.4 recommendation: drop a tiny `AgentTools.py` into Slicer's startup path so `/exec` payloads stay tiny. This is a force multiplier but it's a *separate artifact* (a Slicer module). Should it ship in this repo (`slicer-cli/slicer_module/AgentTools.py`) or in a separate `slicer-agent-tools` repo? My lean: same repo, separate folder, deferred to Phase 3+.

ANSWER: Same Repo separate folder (`slicer-cli/slicer_module/AgentTools.py`), deferred to Phase 3+

8. **Out-of-scope confirmation — tell me if any of these *should* be in MVP:**
   - Multi-instance (two Slicers on 2016 + 2017)
   - GUI control beyond layout (windows, modules)
   - Markups beyond line + fiducial-set (angle, plane, ROI, curve)
   - Headless lifecycle
   - Caching layer for renders/exports

ANSWER: NO. Keep them out of MVP

---

## Appendix A — Endpoint → command map

This is the canonical mapping; both the route data file (`client/routes.py`) and `slicer-cli api routes` derive from this table.

| Method | Endpoint | CLI command | Notes |
|---|---|---|---|
| GET | `/slicer/system/version` | `status` / `system version` | Liveness probe |
| DELETE | `/slicer/system` | `system shutdown --confirm` | 1 s deferred |
| PUT | `/slicer/gui` | `gui layout` (Phase 2) | |
| GET | `/slicer/screenshot` | `render screenshot` | Needs `--main-window` |
| GET | `/slicer/slice` | `render slice` | |
| GET | `/slicer/threeD` | `render threed` | |
| GET | `/slicer/threeDGraphics` | `render gltf` | Undocumented in user docs |
| GET | `/slicer/timeimage` | `api raw` only | Debug-only |
| GET | `/slicer/mrml/names` | `scene nodes --fields name` | |
| GET | `/slicer/mrml/ids` | `scene ids` | |
| GET | `/slicer/mrml/properties` | `node show <id>` | |
| GET | `/slicer/mrml/file` | `node export <id> --out` (Phase 2) | Server-side write |
| POST | `/slicer/mrml` | `volume import` / `scene load` / `node load --type ...` | Polymorphic by `filetype` |
| PUT | `/slicer/mrml` | `node reload <id>` | |
| DELETE | `/slicer/mrml` | `node delete <id>` / `scene clear --confirm` | Empty selector blocked |
| GET | `/slicer/sampledata` | `sample load <name>` | |
| GET | `/slicer/volumes` | `volume list` | |
| GET | `/slicer/volume` | `volume export <id>` | NRRD bytes |
| POST | `/slicer/volume` | (Phase 2) `volume import-bytes` | LPS / signed-short only |
| GET | `/slicer/gridTransforms` | `transform list` (Phase 3) | |
| GET | `/slicer/gridTransform` | `transform export <id>` (Phase 3) | |
| POST | `/slicer/gridTransform` | — | E_NOT_IMPLEMENTED |
| GET | `/slicer/fiducials` | `markup list --type fiducial` | |
| PUT | `/slicer/fiducial` | `markup fiducial-set` | |
| GET | `/slicer/segmentations` | `markup list --type segmentation` | List only |
| GET | `/slicer/segmentation` | — | E_NOT_IMPLEMENTED (stub) |
| GET | `/slicer/tracking` | `api raw` only | Niche |
| GET | `/slicer/volumeSelection` | `volume cycle next\|previous` (Phase 2) | |
| POST | `/slicer/exec` | `exec` | Gated |
| POST | `/slicer/accessDICOMwebStudy` | `dicom pull` | Watch out: report §8.1 bug |
| GET | `/dicom/studies` | `dicom studies` | |
| GET | `/dicom/studies/{u}/series` | `dicom series <studyUID>` | |
| GET | `/dicom/studies/{u}/series/{s}/instances` | `dicom instances` | |
| GET | `/dicom/studies/{u}/series/{s}/instances/{i}` | `dicom instance` | WADO-RS retrieve |
| GET | `/dicom/studies/{u}/.../metadata` | `dicom meta` | |

---

## Appendix B — minimal `pyproject.toml` sketch

```toml
[project]
name = "slicer-cli"
version = "0.1.0"
description = "Agent-first CLI for 3D Slicer's in-process HTTP server"
requires-python = ">=3.11"
dependencies = [
  "httpx>=0.27",
  "typer>=0.12",
  "pydantic>=2.6",
  "pydantic-settings>=2.2",
  "rich>=13.7",
]

[project.scripts]
slicer-cli = "slicer_cli.cli.app:main"
slcli      = "slicer_cli.cli.app:main"

[dependency-groups]
dev = ["pytest", "respx", "pytest-httpx", "ruff", "mypy"]
```

---

*End of PRD v0.1. Awaiting answers to §14.2 before locking the design and starting Phase 0.*
