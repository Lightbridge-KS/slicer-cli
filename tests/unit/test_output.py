"""Output envelope shapes (PRD §6.2/§6.3)."""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout

from slicer_cli.client.errors import (
    ErrorCode,
    SlicerEmptySelectorError,
    SlicerError,
)
from slicer_cli.output import render_error, render_success


def test_render_success_json_envelope() -> None:
    buf = io.StringIO()
    with redirect_stdout(buf):
        render_success({"foo": 1, "bar": "x"}, mode="json")

    payload = json.loads(buf.getvalue())
    assert payload == {"ok": True, "foo": 1, "bar": "x"}


def test_render_error_json_envelope() -> None:
    err = SlicerEmptySelectorError()
    buf = io.StringIO()
    with redirect_stdout(buf):
        render_error(err, mode="json")

    payload = json.loads(buf.getvalue())
    assert payload["ok"] is False
    assert payload["error"]["code"] == ErrorCode.E_EMPTY_SELECTOR.value
    assert "selectors" in payload["error"]["message"]
    assert payload["error"]["hint"]
    assert payload["error"]["http_status"] is None


def test_error_to_dict_has_stable_shape() -> None:
    err = SlicerError(
        ErrorCode.E_BAD_INPUT,
        "missing arg",
        hint="pass --x",
        endpoint="/slicer/foo",
        http_status=None,
    )
    assert err.to_dict() == {
        "code": "E_BAD_INPUT",
        "message": "missing arg",
        "hint": "pass --x",
        "endpoint": "/slicer/foo",
        "http_status": None,
    }


def test_render_success_pretty_writes_to_stdout() -> None:
    buf = io.StringIO()
    with redirect_stdout(buf):
        render_success({"a": "b"}, mode="pretty")
    assert "a" in buf.getvalue()
    assert "b" in buf.getvalue()
