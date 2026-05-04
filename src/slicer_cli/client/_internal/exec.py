"""Templated `/slicer/exec` payload builder — shared by `save_scene`, `pull_from_dicomweb`.

Every templated /exec call goes through `build_exec_payload` so Phase 3's
audit-log machinery has a single insertion point. The kwargs are
`repr()`-quoted before substitution to defend against quote-escape attacks
and accidental syntax breakage from filenames or UIDs containing
characters that would otherwise corrupt the Python source we send.

Templates use the standard `str.format` mini-language. Use `{{ }}` to emit
literal braces (e.g., for the `__execResult` dict literal) — the helper
applies `.format(**repr_kwargs)` exactly once.
"""

from __future__ import annotations

from typing import Any


def build_exec_payload(template: str, **kwargs: Any) -> bytes:
    """Render a Python source template with safe-repr substitution.

    Each `kwarg` value is quoted via `repr()` before being substituted into
    the template, so user-supplied strings (paths, UIDs, URLs) cannot break
    Python syntax. The template's literal braces (e.g. for a dict literal
    in the response payload) must be escaped as `{{` / `}}`.

    Templates MUST set `__execResult` to a JSON-serializable value — Slicer
    returns that as the response body.

    Phase 3 will wrap this helper with an audit-log writer (PRD §8.3) once
    the formal `exec` command lands; until then both `mrml.save_scene` and
    `dicom.pull_from_dicomweb` route through here so the migration is a
    single-file change.
    """
    safe_kwargs = {key: repr(value) for key, value in kwargs.items()}
    rendered = template.format(**safe_kwargs)
    return rendered.encode()
