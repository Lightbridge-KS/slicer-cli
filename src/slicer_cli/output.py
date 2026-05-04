"""Output formatters — JSON envelope (PRD §6.2/§6.3) and rich pretty mode.

CLI commands hand a *payload dict* and a *mode* to render_success/render_error;
they never call print() directly. This keeps the JSON contract stable and
isolates TTY/colour decisions.

JSON mode writes a single-line `json.dumps(envelope)` to stdout (no rich).
Pretty mode uses rich and writes errors to stderr.
"""

from __future__ import annotations

import json
import sys
from typing import Any, Literal

from rich.console import Console
from rich.table import Table

from slicer_cli.client.errors import SlicerError

OutputMode = Literal["json", "pretty"]

_OK_PREFIX = "[bold green]✓[/]"
_ERR_PREFIX = "[bold red]✗[/]"


def render_success(
    payload: dict[str, Any],
    *,
    mode: OutputMode,
    renderer: str | None = None,
) -> None:
    """Emit a success envelope to stdout in the requested mode."""
    if mode == "json":
        envelope: dict[str, Any] = {"ok": True}
        envelope.update(payload)
        _emit_json(envelope)
        return

    _render_pretty_payload(_stdout_console(), payload, renderer)


def render_meta_to_stderr(payload: dict[str, Any], *, mode: OutputMode) -> None:
    """Emit a success envelope to stderr — used by binary-output commands.

    `volume export` writes raw bytes to stdout (or `--out path`), so the
    success envelope can't go to stdout in `--json` mode without garbling
    the binary. We write the envelope to stderr instead.
    """
    if mode == "json":
        envelope: dict[str, Any] = {"ok": True}
        envelope.update(payload)
        sys.stderr.write(json.dumps(envelope) + "\n")
        sys.stderr.flush()
        return

    err = _stderr_console()
    err.print(f"{_OK_PREFIX} wrote {payload.get('bytes', '?')} bytes to {payload.get('out', '?')}")


def render_error(error: SlicerError, *, mode: OutputMode) -> None:
    """Emit an error envelope. JSON to stdout; pretty to stderr."""
    if mode == "json":
        _emit_json({"ok": False, "error": error.to_dict()})
        return

    err = _stderr_console()
    err.print(f"{_ERR_PREFIX} [bold]{error.code.value}[/]: {error.message}")
    if error.endpoint:
        err.print(f"   endpoint: [dim]{error.endpoint}[/]")
    if error.http_status is not None:
        err.print(f"   http:     [dim]{error.http_status}[/]")
    if error.hint:
        err.print(f"   hint:     {error.hint}")


# ----------------------------------------------------------------- pretty renderers


def _render_pretty_payload(console: Console, payload: dict[str, Any], renderer: str | None) -> None:
    """Pick a pretty layout based on the renderer hint, falling back to k=v lines."""
    if renderer == "status":
        _render_status(console, payload)
        return
    if renderer == "version":
        _render_version(console, payload)
        return
    if renderer in {"nodes", "volumes"}:
        _render_node_table(console, payload, key="nodes" if renderer == "nodes" else "volumes")
        return
    if renderer == "ids":
        _render_string_list(console, payload.get("ids", []))
        return
    if renderer == "samples":
        _render_samples(console, payload.get("samples", []))
        return
    if renderer == "node-properties":
        _render_node_properties(console, payload.get("node", {}))
        return
    if renderer == "routes":
        _render_routes(console, payload.get("routes", []))
        return
    if renderer == "doctor":
        _render_doctor(console, payload.get("checks", []))
        return
    if renderer == "studies":
        _render_studies(console, payload.get("studies", []))
        return
    if renderer == "series":
        _render_series(console, payload.get("series", []))
        return
    if renderer == "instances":
        _render_instances(console, payload.get("instances", []))
        return
    if renderer == "dicom-meta":
        _render_dicom_meta(console, payload)
        return

    for key, value in payload.items():
        console.print(f"[bold]{key}[/]: {value}")


def _render_status(console: Console, payload: dict[str, Any]) -> None:
    url = payload.get("url", "")
    console.print(f"{_OK_PREFIX} Slicer is up at [bold]{url}[/]")
    table = Table.grid(padding=(0, 2))
    table.add_column(style="dim")
    table.add_column()
    for key in ("applicationName", "applicationVersion", "releaseType", "arch", "os"):
        value = payload.get(key)
        if value is not None:
            table.add_row(key, str(value))
    console.print(table)


def _render_version(console: Console, payload: dict[str, Any]) -> None:
    table = Table.grid(padding=(0, 2))
    table.add_column(style="dim")
    table.add_column()
    for key, value in payload.items():
        if value is None:
            continue
        table.add_row(key, str(value))
    console.print(table)


def _render_node_table(console: Console, payload: dict[str, Any], *, key: str) -> None:
    """Render a list of {id, name, class} as a table; used for `volume list` and `scene nodes`."""
    rows = payload.get(key, [])
    if not rows:
        console.print(f"[dim](no {key})[/]")
        return
    table = Table(show_header=True, header_style="bold")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Name")
    table.add_column("Class", style="dim")
    for row in rows:
        table.add_row(
            str(row.get("id", "")),
            str(row.get("name", "")),
            str(row.get("class") or "—"),
        )
    console.print(table)


def _render_string_list(console: Console, items: list[Any]) -> None:
    """Render a flat list (e.g., `scene ids`) one entry per line."""
    if not items:
        console.print("[dim](empty)[/]")
        return
    for item in items:
        console.print(str(item))


def _render_samples(console: Console, samples: list[dict[str, Any]]) -> None:
    if not samples:
        console.print("[dim](no curated samples)[/]")
        return
    table = Table(show_header=True, header_style="bold")
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Description")
    for s in samples:
        table.add_row(str(s.get("name", "")), str(s.get("description", "")))
    console.print(table)


def _render_routes(console: Console, rows: list[dict[str, Any]]) -> None:
    """Render the route table from `api routes`."""
    if not rows:
        console.print("[dim](no matching routes)[/]")
        return
    table = Table(show_header=True, header_style="bold")
    table.add_column("Method", style="cyan", no_wrap=True)
    table.add_column("Path", no_wrap=True)
    table.add_column("Purpose")
    table.add_column("CLI", style="dim")
    table.add_column("Phase", style="dim", no_wrap=True)
    table.add_column("Flags", no_wrap=True)
    for row in rows:
        flags = []
        if row.get("destructive"):
            flags.append("[red]destructive[/]")
        if row.get("stub"):
            flags.append("[yellow]stub[/]")
        table.add_row(
            str(row.get("method", "")),
            str(row.get("path", "")),
            str(row.get("purpose", "")),
            str(row.get("cli_command") or "—"),
            str(row.get("phase") or "—"),
            " ".join(flags),
        )
    console.print(table)


def _render_doctor(console: Console, checks: list[dict[str, Any]]) -> None:
    """Render the doctor capability matrix."""
    if not checks:
        console.print("[dim](no checks ran)[/]")
        return
    table = Table(show_header=True, header_style="bold")
    table.add_column("Check", no_wrap=True)
    table.add_column("Status", no_wrap=True)
    table.add_column("Detail")
    for c in checks:
        ok = bool(c.get("ok"))
        status = "[green]OK[/]" if ok else "[red]FAIL[/]"
        table.add_row(str(c.get("name", "")), status, str(c.get("detail", "")))
    console.print(table)


def _render_studies(console: Console, rows: list[dict[str, Any]]) -> None:
    if not rows:
        console.print("[dim](no studies in Slicer's DICOM DB)[/]")
        return
    table = Table(show_header=True, header_style="bold")
    table.add_column("PatientName")
    table.add_column("PatientID", style="dim")
    table.add_column("StudyUID", style="cyan", no_wrap=False)
    table.add_column("Date", style="dim")
    table.add_column("Description")
    table.add_column("Accession", style="dim")
    table.add_column("Modalities")
    for row in rows:
        modalities = ", ".join(str(m) for m in row.get("modalities_in_study") or [])
        table.add_row(
            str(row.get("patient_name") or "—"),
            str(row.get("patient_id") or "—"),
            str(row.get("study_uid") or ""),
            str(row.get("study_date") or "—"),
            str(row.get("study_description") or "—"),
            str(row.get("accession_number") or "—"),
            modalities or "—",
        )
    console.print(table)


def _render_series(console: Console, rows: list[dict[str, Any]]) -> None:
    if not rows:
        console.print("[dim](no series)[/]")
        return
    table = Table(show_header=True, header_style="bold")
    table.add_column("SeriesUID", style="cyan")
    table.add_column("Modality", style="dim")
    table.add_column("#", justify="right")
    table.add_column("Description")
    for row in rows:
        table.add_row(
            str(row.get("series_uid") or ""),
            str(row.get("modality") or "—"),
            str(row.get("series_number") if row.get("series_number") is not None else "—"),
            str(row.get("series_description") or "—"),
        )
    console.print(table)


def _render_instances(console: Console, rows: list[dict[str, Any]]) -> None:
    if not rows:
        console.print("[dim](no instances)[/]")
        return
    table = Table(show_header=True, header_style="bold")
    table.add_column("SOPUID", style="cyan")
    table.add_column("InstanceNumber", justify="right")
    for row in rows:
        table.add_row(
            str(row.get("sop_uid") or ""),
            str(row.get("instance_number") if row.get("instance_number") is not None else "—"),
        )
    console.print(table)


def _render_dicom_meta(console: Console, payload: dict[str, Any]) -> None:
    """`dicom meta` returns DICOM JSON Model — verbose by design.

    Pretty mode just prints a header + tag count and tells the user how to
    inspect it (jq for agents, --json for full dump). The full blob is
    always available in --json mode.
    """
    level = str(payload.get("level", "?"))
    meta = payload.get("meta") or []
    n_tags = sum(len(entry) if isinstance(entry, dict) else 0 for entry in meta)
    console.print(f"[bold]{level} metadata[/] — {len(meta)} entries, {n_tags} tags total")
    console.print("[dim]Use --json for the full DICOM JSON Model blob.[/]")


def _render_node_properties(console: Console, node: dict[str, Any]) -> None:
    """Render `{id, properties: {...}}` as a panel + key/value grid."""
    node_id = node.get("id", "")
    properties = node.get("properties", {}) or {}
    console.print(f"[bold]Node[/] [cyan]{node_id}[/]  ({len(properties)} properties)")
    if not properties:
        return
    table = Table.grid(padding=(0, 2))
    table.add_column(style="dim")
    table.add_column()
    for k, v in properties.items():
        rendered = str(v)
        if len(rendered) > 200:
            rendered = rendered[:200] + "…"
        table.add_row(str(k), rendered)
    console.print(table)


# ------------------------------------------------------------------- internals


def _emit_json(envelope: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(envelope) + "\n")
    sys.stdout.flush()


def _stdout_console() -> Console:
    return Console(file=sys.stdout, soft_wrap=True)


def _stderr_console() -> Console:
    return Console(file=sys.stderr, soft_wrap=True)
