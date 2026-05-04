"""Audit log writer for every `/slicer/exec` POST.

Per PRD §8.3, every successful `/slicer/exec` invocation lands one line in
`~/.local/state/slicer-cli/exec.log` (configurable via `config.exec.audit_log`).
The line format is intentionally one-line-per-call, append-only, easy to grep,
and keyed by a SHA-256 of the source so two identical scripts collide.

Format (mirrors PRD §8.3 verbatim):

    <iso8601-Z>  rev=<rev>  url=<url>  hash=sha256:<hex>  preview="<first 200 chars>"

Where `rev` is the first 7 chars of `git rev-parse HEAD` if the working
tree is a git checkout, else the literal `unknown` (e.g. when slicer-cli
is installed via `pip install` from a wheel).

This module owns ALL filesystem I/O for the audit trail. `_HttpClient`
holds an optional `AuditLogger` and calls `.log(...)` from `_post_exec`
just before sending the POST. Failures to write the log surface as
`SlicerConfigError` (E_CONFIG, exit 4) — the user sees actionable text
rather than a generic OSError.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from slicer_cli.client.errors import SlicerConfigError

_PREVIEW_CHARS: int = 200


class AuditLogger:
    """Writes one line per `/slicer/exec` POST to a configurable log file."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def log(self, source: bytes, *, url: str, op_label: str) -> None:
        """Append one PRD-§8.3-shaped line for this exec invocation.

        `op_label` (e.g. "mrml.save_scene", "cli.exec") is currently informational
        only — it isn't part of the canonical line format but may be used by
        future log-parsing tooling. We compute hash and preview from the raw
        source bytes so two identical scripts have identical hashes regardless
        of caller.
        """
        line = self._format_line(source=source, url=url, op_label=op_label)
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        except OSError as exc:
            raise SlicerConfigError(f"Could not write audit log to {self.path}: {exc}") from exc

    # ------------------------------------------------------------- internals

    @staticmethod
    def _format_line(*, source: bytes, url: str, op_label: str) -> str:
        timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        digest = hashlib.sha256(source).hexdigest()
        preview = _make_preview(source)
        rev = _git_rev()
        # op_label is appended at the end so the canonical PRD §8.3 prefix
        # (`<iso>  rev=  url=  hash=  preview=`) is preserved for any tool
        # that grep/awks the early columns.
        return (
            f"{timestamp}  rev={rev}  url={url}  hash=sha256:{digest}  "
            f'preview="{preview}"  op={op_label}'
        )


def _make_preview(source: bytes) -> str:
    """First 200 chars of source with newlines and quotes escaped to keep one line."""
    try:
        text = source.decode("utf-8", errors="replace")
    except Exception:
        text = repr(source)
    head = text[:_PREVIEW_CHARS]
    # Keep the line greppable: collapse newlines/CR to literal \n, escape "
    return head.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r")


def _git_rev() -> str:
    """Return short git SHA of the slicer-cli source tree, or 'unknown'."""
    # Resolve the repo root from this file's location so we don't accidentally
    # report the user's CWD repo when slicer-cli is installed elsewhere.
    here = Path(__file__).resolve()
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short=7", "HEAD"],
            cwd=here.parent,
            capture_output=True,
            text=True,
            timeout=2.0,
            check=False,
            env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
        )
    except (FileNotFoundError, subprocess.SubprocessError, OSError):
        return "unknown"
    if result.returncode != 0:
        return "unknown"
    return result.stdout.strip() or "unknown"
