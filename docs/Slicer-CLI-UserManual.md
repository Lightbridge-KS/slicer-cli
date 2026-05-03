# `slicer-cli` — User Manual

> Audience: **AI agents (primary)** and humans (secondary).
> Scope: everything that ships in **Phase 1** (core read/write surface).
> Status: 2026-05-04 — Phase 1 complete; Phase 2/3 features (render, DICOMweb, markup, exec) are stubs that emit `E_NOT_IMPLEMENTED` until those phases land.

This is a working manual, not a tutorial — it is meant to be skimmed by an
agent on first contact and used as a lookup table afterward. If a section
applies only to humans, it is marked **(human)**; if only to agents, it is
marked **(agent)**.

---

## 1. Install / first contact

```bash
# From the repo root, no global install needed:
uv run slicer-cli status                         # pretty (TTY default)
uv run slicer-cli --json status                  # JSON envelope (agent default)

# Or once installed via pip / uv tool:
slicer-cli status
slcli status                                     # short alias
```

A successful response means Slicer is running with its WebServer module
started on port 2016. To start the WebServer **(human)**: open Slicer →
*Welcome to Slicer* module → search "Web Server" → click **Start server**.

For agents the very first thing to run on every fresh task is:

```bash
slicer-cli --json status
```

If that returns `ok: false` with `code: E_NOT_RUNNING`, **stop** and surface
the failure — do not fabricate Slicer state.

---

## 2. The two output modes

| Mode | When | What stdout looks like |
|---|---|---|
| `--json` (or `--json` resolved from config) | always for agents | one-line `{"ok": true, ...}` envelope |
| `--pretty` (the human default) | TTY humans | rich-formatted tables / panels |

Switch is purely cosmetic — every command supports both. Agents should pass
`--json` explicitly on every call. The flag may appear *before or after* the
verb (`slicer-cli status --json` works because the CLI hoists global flags
before Click parses args).

### JSON envelope contract (PRD §6.2/§6.3)

Success:
```json
{"ok": true, "<key>": ..., "<key>": ...}
```

Failure:
```json
{
  "ok": false,
  "error": {
    "code": "E_HTTP_5XX",
    "message": "...",
    "hint": "...",
    "endpoint": "/slicer/...",
    "http_status": 500
  }
}
```

### Stable error codes → exit codes (agents: branch on these)

| Code | Exit | Meaning |
|---|---|---|
| `E_BAD_INPUT` | 1 | CLI argument problem (bad method, malformed `--query`, etc.) |
| `E_HTTP_4XX` / `E_HTTP_5XX` / `E_BAD_RESPONSE` | 2 | Slicer accepted the call but returned an error |
| `E_NOT_RUNNING` / `E_NETWORK` / `E_TIMEOUT` | 3 | Could not reach Slicer |
| `E_CONFIG` | 4 | Bad config file or env var |
| `E_EXEC_DISABLED` | 5 | `/slicer/exec` is gated off (Phase 3 mainly) |
| `E_DESTRUCTIVE` / `E_EMPTY_SELECTOR` | 6 | A safety guard fired *before* any HTTP call |
| `E_NOT_IMPLEMENTED` | 7 | Feature lives in a later phase — see `hint` |

Code names are **public API** — they will not change. Exit codes are stable
within a phase but a code may grow new exit codes between major versions.

---

## 3. Global flags

| Flag | Where it goes | Notes |
|---|---|---|
| `--url URL` | server.url override | default `http://127.0.0.1:2016` |
| `--timeout SECONDS` | server.timeout_seconds override | default `30` |
| `--json` / `--pretty` | output mode | `--json` wins if both given |
| `--quiet` | reserved | partial; suppresses non-error chatter |
| `--version` | print version and exit | |

Layered precedence (highest first): flag → env var (`SLICER_URL`,
`SLICER_TIMEOUT`, `SLICER_EXEC_ENABLED`) → project `.slicer-cli.toml` (cwd
or first ancestor) → `~/.config/slicer-cli/config.toml` → built-in defaults.

`uv run slicer-cli config show --json` prints the merged result.

---

## 4. Phase-1 command surface

Tier 1 = ready to use. Tier 2 = stub (returns `E_NOT_IMPLEMENTED` with a
`Phase N` hint).

### 4.1 Liveness / introspection

| Command | Description |
|---|---|
| `slicer-cli status` | One-call liveness + version probe (the canonical "is it on?"). |
| `slicer-cli system version` | Same data as `status`, scoped under the `system` group. |
| `slicer-cli doctor` | Capability matrix (reachable, slicer-api, dicomweb, power-tool, render). Each probe is independent; one failure does not abort the rest. |
| `slicer-cli api routes [--method M] [--destructive] [--phase "Phase N"]` | Pure-offline route inventory (32 entries, derived from PRD Appendix A). Use this to discover the underlying HTTP surface. |
| `slicer-cli config show / get / path` | Inspect merged configuration. |

### 4.2 MRML scene & nodes

| Command | Description |
|---|---|
| `slicer-cli scene nodes [--class C] [--name N]` | All MRML nodes as `{id, name, class}` (zips `/mrml/ids` + `/mrml/names`, derives class from id). |
| `slicer-cli scene ids [--class C] [--name N]` | Just ids — terse, ideal for piping. |
| `slicer-cli scene clear --confirm` | Wipes the entire scene (destructive). Without `--confirm` returns `E_DESTRUCTIVE`. |
| `slicer-cli scene save <path>` | Save scene to `.mrb` / `.mrml`. **Note:** uses `/slicer/exec` under the hood (Slicer has no native save endpoint); requires power-tool enabled on the server. |
| `slicer-cli scene load <path>` | Load a `.mrb` / `.mrml` from a server-readable path. |
| `slicer-cli node show <id>` | Full property dict for one node. |
| `slicer-cli node delete <id>` | Delete one node. Empty/whitespace `<id>` → `E_EMPTY_SELECTOR`. |
| `slicer-cli node reload <id>` | Re-load node from its underlying file. |

### 4.3 Volumes

| Command | Description |
|---|---|
| `slicer-cli volume list` | All scalar/labelmap volumes (id, name, class). |
| `slicer-cli volume show <id>` | Property dict for one volume node. |
| `slicer-cli volume import <path> [--name N]` | Load a NRRD/NIfTI/etc. from a server-readable path as a new volume node. |
| `slicer-cli volume export <id> --out path` | Stream NRRD bytes to disk. **`--out` is required.** Pass `--out -` for stdout (binary safe — JSON envelope goes to stderr). |
| `slicer-cli volume delete <id>` | Delete one volume node (same empty-id guard as `node delete`). |

### 4.4 Sample data

| Command | Description |
|---|---|
| `slicer-cli sample list` | Curated catalogue of 4 verified Slicer samples. Pure offline. |
| `slicer-cli sample load <name>` | Triggers Slicer's `SampleData` module to download/load. Accepts any string (Slicer's actual list is larger than the curated 4). |

### 4.5 Escape hatch

| Command | Description |
|---|---|
| `slicer-cli api raw <method> <path> [--query K=V ...] [--body @file] [--out path] [--confirm]` | Issue an arbitrary HTTP call. JSON responses are parsed into the envelope; non-JSON requires `--out`. Destructive `(method, path)` pairs (per `routes.DESTRUCTIVE_RAW`) require `--confirm`. |

### 4.6 Stubs (Phase 2/3, return `E_NOT_IMPLEMENTED` for now)

`render slice/threed/screenshot/gltf` (Phase 2), `dicom studies/series/instances/meta/instance/pull` (Phase 2), `markup list/fiducial-set/line/...` (Phase 3), `exec` (Phase 3), `gui layout` (Phase 3).

---

## 5. Worked examples

The user's live Slicer is at `http://127.0.0.1:2016` with **MRHead** loaded
in the canonical examples below.

### 5.1 The MRHead read path (agent-friendly)

```bash
# 1. Verify Slicer is up.
slicer-cli --json status \
  | jq -r '.applicationName + " " + .applicationVersion'
# → "Slicer 5.11.0"

# 2. Find the MRHead volume id.
MR_ID=$(slicer-cli --json volume list \
  | jq -r '.volumes[] | select(.name == "MRHead") | .id')
echo "$MR_ID"
# → "vtkMRMLScalarVolumeNode1"

# 3. Inspect its properties.
slicer-cli --json volume show "$MR_ID" \
  | jq '.node.properties | {Name, Spacing, Origin}'

# 4. Filter the scene to volume nodes only.
slicer-cli --json scene nodes --class vtkMRMLScalarVolumeNode \
  | jq '.nodes | length'
```

### 5.2 Export MRHead to disk

```bash
slicer-cli --json volume export vtkMRMLScalarVolumeNode1 \
  --out /tmp/mr.nrrd
ls -lh /tmp/mr.nrrd               # ~16 MB
file /tmp/mr.nrrd                 # NRRD0004 ...
```

For piping to another process, use `--out -`. The success envelope still
gets emitted in JSON mode — to **stderr**, so stdout stays pure binary:

```bash
slicer-cli --json volume export vtkMRMLScalarVolumeNode1 --out - \
  2> /tmp/meta.json \
  | itk-something --input -
jq '.bytes' /tmp/meta.json
```

### 5.3 Round-trip: load a sample, then clean it up

```bash
# Load CTAAbdomenPanoramix as a throwaway.
BEFORE=$(slicer-cli --json scene ids | jq -r '.ids[]' | sort)
slicer-cli --json sample load CTAAbdomenPanoramix
AFTER=$(slicer-cli --json scene ids | jq -r '.ids[]' | sort)

# Find the new ids.
NEW=$(comm -13 <(echo "$BEFORE") <(echo "$AFTER"))
echo "$NEW"

# Delete them by id (each one safely guarded against empty input).
for id in $NEW; do
  slicer-cli --json node delete "$id"
done
```

### 5.4 Capability check before doing real work (agent)

```bash
slicer-cli --json doctor | jq '.checks[] | select(.ok == false)'
# Empty output → all six probes green.
# Non-empty → branch on the failing probe; e.g., if "render" is FAIL,
# don't try Phase-2 render commands.
```

### 5.5 Discover the underlying HTTP surface

```bash
# What can the CLI talk to?
slicer-cli --json api routes --phase "Phase 1" | jq '.routes | length'

# Which ones are destructive?
slicer-cli --json api routes --destructive | jq '.routes[] | "\(.method) \(.path)"'

# Bypass the typed wrapper for an experiment:
slicer-cli --json api raw GET /slicer/mrml/ids --query class=vtkMRMLViewNode \
  | jq '.response'
```

---

## 6. Safety model (read this once, agent)

The CLI is built so that an agent acting in good faith **cannot** wipe the
user's scene without being explicit:

1. **Empty selectors are refused at the client layer.** `node delete ""`
   returns `E_EMPTY_SELECTOR` (exit 6); the corresponding HTTP call is
   never sent. This is a defence-in-depth against Slicer's
   `DELETE /slicer/mrml` semantics, where an empty `id` means "clear the
   whole scene".
2. **Destructive ops require `--confirm`.** `scene clear`, `system shutdown`,
   and any `api raw` call whose `(method, path)` appears in
   `client.routes.DESTRUCTIVE_RAW`. Without `--confirm` you get
   `E_DESTRUCTIVE` (exit 6).
3. **`volume export` requires `--out` explicitly.** No accidental binary on
   stdout. Pass `--out -` if you genuinely want bytes piped.
4. **The `exec` command is gated** by `config.exec.enabled` (Phase 3).

Rule of thumb for agents: never re-run a command "just to retry" if it
returned `E_DESTRUCTIVE` or `E_EMPTY_SELECTOR` — the user did not authorize
the destructive action; surface it instead.

---

## 7. Configuration **(human)**

Layered, with later sources winning (PRD §7.1):

1. CLI flags (`--url`, `--timeout`, `--json`, …)
2. Environment variables: `SLICER_URL`, `SLICER_TIMEOUT`, `SLICER_EXEC_ENABLED`
3. Project-local `.slicer-cli.toml` (cwd or any ancestor)
4. User-level `~/.config/slicer-cli/config.toml`
5. Built-in defaults

Example project config:

```toml
# .slicer-cli.toml
[server]
url = "http://127.0.0.1:2017"   # second Slicer instance
timeout_seconds = 60.0

[output]
default = "json"                # default to JSON for this project

[exec]
enabled = false                 # belt-and-braces: ALSO requires --i-understand-the-risk per call
```

Inspect the merged result:

```bash
slicer-cli config show --json
slicer-cli config get server.url
slicer-cli config path           # which TOMLs were loaded
```

---

## 8. Tips for AI agents

- **Default to `--json` on every invocation.** Pretty mode is for humans.
- **Read `doctor` once at the start of a session**; cache the result. Don't
  spam `status` between every command.
- **Discover commands via `api routes --json`**, not from training data.
  The wrapper coverage may have advanced past what you remember.
- **Branch on `error.code`**, not `error.message`. Codes are stable; messages
  may be reworded.
- **Treat `E_NOT_IMPLEMENTED` as a hard stop**: do not retry, do not try to
  emulate via `api raw` unless the user explicitly asks. The `hint` tells
  you which phase will land it.
- **Idempotency**: most reads are safe. `volume export`, `node reload`, and
  `sample load` are also idempotent in practice. Loads with `--name` are
  **not** — re-running adds a new node with a `_N` suffix on collision.
- **Server-side paths**: `volume import`, `scene load`, `scene save`, and
  the server-side variants of save endpoints all expect paths that **the
  Slicer process** can read/write — not the CLI host filesystem if Slicer
  is remote. By contrast, `volume export --out` writes to the **CLI host**
  because it streams bytes through the HTTP response.
- **Cleanup after load**: see §5.3 — capture ids before/after `sample load`
  and `node delete` only the new ones.

---

## 9. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `E_NOT_RUNNING` on `status` | WebServer not started in Slicer | Start it from the *Web Server* module. |
| `E_HTTP_5XX` on `scene save` with body containing `unknown command "b'/exec'"` | `/slicer/exec` is disabled in this Slicer build | Either enable it (Slicer's WebServer settings) or skip `scene save`. |
| `E_HTTP_5XX` on `volume export` with unknown id | The volume isn't loaded | `volume list` first; verify the id. |
| `volume export` writes a 0-byte file | Slicer responded but the volume was empty | Check `volume show <id>` for `Spacing` / `Origin` sanity. |
| `api raw` blocks with `E_DESTRUCTIVE` even though method is `GET` | Path matches a destructive override | Run `api routes --destructive` to see the list. |
| `pytest` complains about respx routes not called when testing guards | The guard fired before the HTTP call (correct behaviour) | Use `respx.mock(..., assert_all_called=False)` in those tests. |

---

## 10. What's NOT in Phase 1

These return `E_NOT_IMPLEMENTED` until their phase ships:

- **Phase 2:** `render slice/threed/screenshot/gltf`, `dicom studies/series/instances/meta/instance/pull`.
- **Phase 3:** `markup list/fiducial-set/line/...`, `exec`, `gui layout`.
- **Phase 4:** the companion Claude skill at `.claude/skills/slicer-cli/`.

Use `slicer-cli api routes --json` to see the full route table including
which ones are wrapped now and which are deferred.

---

## 11. Pointers

- PRD: [`Slicer-CLI-PRD.md`](./Slicer-CLI-PRD.md) — locked decisions, contracts, rationale.
- Implementation tracker: [`TODOS.md`](./TODOS.md) — what's done, what's next.
- Surface report (Slicer side): [`3d-slicer-webserver-surface-report.md`](./3d-slicer-webserver-surface-report.md) — every endpoint, fragility notes.
- Project conventions: [`AGENTS.md`](../AGENTS.md) (root) and the per-tree `AGENTS.md` files under `src/slicer_cli/` and `tests/`.
