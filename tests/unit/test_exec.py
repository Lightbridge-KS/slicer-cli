"""Unit tests for `client/_exec.py` — templated /slicer/exec payload builder.

These tests validate two properties:

1. **Syntactic validity** — the rendered source compiles via `ast.parse()`,
   which only parses (no execution).
2. **Injection defence** — every kwarg is `repr()`-quoted, so the rendered
   source contains exactly `repr(value)` at the substitution point. We check
   this by string comparison; we never run the rendered code in tests.
"""

from __future__ import annotations

import ast

from slicer_cli.client._internal.exec import build_exec_payload


def _assert_parses(source: str) -> None:
    """Confirm the source is syntactically valid Python (parse only, no execution)."""
    ast.parse(source)


def test_build_exec_payload_basic_substitution() -> None:
    """String kwargs get repr()-quoted before substitution."""
    body = build_exec_payload("x = {value}\n", value="hello")
    assert body == b"x = 'hello'\n"
    _assert_parses(body.decode())


def test_build_exec_payload_escapes_quotes_in_value() -> None:
    """A user-supplied value containing single quotes is rendered as repr() output."""
    body = build_exec_payload("x = {value}\n", value="it's a test")
    rendered = body.decode()
    # The value is whatever Python's repr() produces — different versions may
    # pick double or single quotes, but the result must always parse cleanly
    # AND must contain the safely-quoted form of the input.
    _assert_parses(rendered)
    assert repr("it's a test") in rendered


def test_build_exec_payload_double_brace_emits_literal_brace() -> None:
    """Templates use `{{` / `}}` to emit literal braces (e.g., dict literals)."""
    body = build_exec_payload("result = {{'a': {value}}}\n", value=42).decode()
    assert body == "result = {'a': 42}\n"
    _assert_parses(body)


def test_build_exec_payload_repr_quotes_path_with_backslashes() -> None:
    """Windows-style paths must round-trip through repr safely (no syntax breakage)."""
    body = build_exec_payload("p = {path}\n", path=r"C:\Users\test\scene.mrb").decode()
    _assert_parses(body)
    assert repr(r"C:\Users\test\scene.mrb") in body


def test_build_exec_payload_empty_string_arg() -> None:
    body = build_exec_payload("token = {access_token}\n", access_token="").decode()
    assert body == "token = ''\n"
    _assert_parses(body)


def test_build_exec_payload_multiple_kwargs() -> None:
    body = build_exec_payload(
        "endpoint = {url}\nstudy = {study_uid}\n",
        url="http://localhost:8042",
        study_uid="1.2.840.X",
    ).decode()
    assert "endpoint = 'http://localhost:8042'" in body
    assert "study = '1.2.840.X'" in body
    _assert_parses(body)


def test_build_exec_payload_dicom_pull_template_compiles() -> None:
    """The actual `pull_from_dicomweb` template must produce valid Python source."""
    template = (
        "from DICOMLib import DICOMUtils\n"
        "_token = {access_token}\n"
        "loaded = DICOMUtils.importFromDICOMWeb(\n"
        "    dicomWebEndpoint={endpoint_url},\n"
        "    studyInstanceUID={study_uid},\n"
        "    accessToken=(_token if _token else None),\n"
        ")\n"
        "__execResult = {{\n"
        "    'imported_count': len(loaded or []),\n"
        "    'study_uid': {study_uid},\n"
        "    'endpoint': {endpoint_url},\n"
        "}}\n"
    )
    body = build_exec_payload(
        template,
        endpoint_url="http://localhost:8042/dicom-web",
        study_uid="2.25.123456789012345678901234567890123456",
        access_token="",
    )
    _assert_parses(body.decode())


def test_build_exec_payload_save_scene_template_compiles() -> None:
    """The actual `save_scene` template must produce valid Python source."""
    template = (
        "import slicer\n"
        "saved = slicer.util.saveScene({path})\n"
        "__execResult = {{'saved': bool(saved), 'path': {path}}}\n"
    )
    body = build_exec_payload(template, path="/tmp/scene with space.mrb")
    _assert_parses(body.decode())
