"""`slicer-cli render slice / threed / screenshot / gltf` — unit tests."""

from __future__ import annotations

import json
import struct
from pathlib import Path

import respx
from httpx import Response
from typer.testing import CliRunner

from slicer_cli.cli.app import app


def _make_png(width: int = 64, height: int = 64, *, body_size: int = 1024) -> bytes:
    """Synthesize a byte-correct PNG header + IHDR + padding to `body_size`.

    We don't need a decodable image — `validate_png` only inspects the magic
    bytes and IHDR width/height, so a minimal-but-honest header passes.
    """
    magic = b"\x89PNG\r\n\x1a\n"
    ihdr_length = b"\x00\x00\x00\x0d"  # 13 bytes of IHDR data
    ihdr_type = b"IHDR"
    ihdr_data = struct.pack(">II", width, height) + b"\x08\x02\x00\x00\x00"
    ihdr_crc = b"\x00\x00\x00\x00"  # CRC not validated by us
    header = magic + ihdr_length + ihdr_type + ihdr_data + ihdr_crc
    pad = b"\x00" * max(body_size - len(header), 0)
    return header + pad


# --------------------------------------------------------------- render slice


def test_render_slice_writes_png_file(runner: CliRunner, tmp_path: Path) -> None:
    out_path = tmp_path / "slice.png"
    fake_png = _make_png(width=256, height=256, body_size=2048)
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        route = mock.get("/slicer/slice", params={"view": "red"}).mock(
            return_value=Response(200, content=fake_png, headers={"content-type": "image/png"})
        )
        result = runner.invoke(app, ["--json", "render", "slice", "--out", str(out_path)])

    assert result.exit_code == 0, result.stderr
    assert route.called
    body = json.loads(result.stdout)
    assert body["bytes"] == len(fake_png)
    assert body["format"] == "png"
    assert out_path.read_bytes() == fake_png


def test_render_slice_passes_view_offset_size(runner: CliRunner, tmp_path: Path) -> None:
    out_path = tmp_path / "slice.png"
    fake_png = _make_png(body_size=512)
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        route = mock.get(
            "/slicer/slice",
            params={"view": "yellow", "offset": "12.5", "size": "256"},
        ).mock(return_value=Response(200, content=fake_png, headers={"content-type": "image/png"}))
        result = runner.invoke(
            app,
            [
                "--json",
                "render",
                "slice",
                "--out",
                str(out_path),
                "--view",
                "yellow",
                "--offset",
                "12.5",
                "--size",
                "256",
            ],
        )

    assert result.exit_code == 0, result.stderr
    assert route.called


def test_render_slice_invalid_view_returns_e_bad_input(runner: CliRunner, tmp_path: Path) -> None:
    with respx.mock(base_url="http://127.0.0.1:2016", assert_all_called=False):
        result = runner.invoke(
            app,
            ["--json", "render", "slice", "--out", str(tmp_path / "x.png"), "--view", "bogus"],
        )
    assert result.exit_code == 1
    assert json.loads(result.stdout)["error"]["code"] == "E_BAD_INPUT"


def test_render_slice_empty_png_blocked(runner: CliRunner, tmp_path: Path) -> None:
    """A 64-byte 'PNG' (just header) is below the 256-byte threshold → E_BAD_RESPONSE."""
    tiny = b"\x89PNG\r\n\x1a\n" + b"\x00" * 50
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        mock.get("/slicer/slice").mock(
            return_value=Response(200, content=tiny, headers={"content-type": "image/png"})
        )
        result = runner.invoke(
            app, ["--json", "render", "slice", "--out", str(tmp_path / "empty.png")]
        )

    assert result.exit_code == 2
    body = json.loads(result.stdout)
    assert body["error"]["code"] == "E_BAD_RESPONSE"
    # Mesa hint must include the literal env var verbatim so agents can copy-paste.
    assert "GALLIUM_DRIVER=llvmpipe" in body["error"]["hint"]


def test_render_slice_zero_dim_png_blocked(runner: CliRunner, tmp_path: Path) -> None:
    """Valid magic + size, but IHDR says 0x0 → E_BAD_RESPONSE."""
    bad = _make_png(width=0, height=0, body_size=1024)
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        mock.get("/slicer/slice").mock(
            return_value=Response(200, content=bad, headers={"content-type": "image/png"})
        )
        result = runner.invoke(
            app, ["--json", "render", "slice", "--out", str(tmp_path / "zero.png")]
        )
    assert result.exit_code == 2
    assert json.loads(result.stdout)["error"]["code"] == "E_BAD_RESPONSE"


def test_render_slice_5xx(runner: CliRunner, tmp_path: Path) -> None:
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        mock.get("/slicer/slice").mock(return_value=Response(500, json={"message": "boom"}))
        result = runner.invoke(app, ["--json", "render", "slice", "--out", str(tmp_path / "x.png")])
    assert result.exit_code == 2
    assert json.loads(result.stdout)["error"]["code"] == "E_HTTP_5XX"


def test_render_slice_to_stdout_routes_envelope_to_stderr(
    runner: CliRunner, tmp_path: Path
) -> None:
    """`--out -` writes binary to stdout; the JSON envelope must go to stderr."""
    fake_png = _make_png(body_size=512)
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        mock.get("/slicer/slice").mock(
            return_value=Response(200, content=fake_png, headers={"content-type": "image/png"})
        )
        result = runner.invoke(
            app, ["--json", "render", "slice", "--out", "-"], catch_exceptions=False
        )

    assert result.exit_code == 0, result.stderr
    # stdout must be the raw PNG; stderr must hold the JSON envelope.
    assert result.stdout_bytes == fake_png
    body = json.loads(result.stderr)
    assert body["ok"] is True
    assert body["bytes"] == len(fake_png)


# --------------------------------------------------------------- render threed


def test_render_threed_happy_path(runner: CliRunner, tmp_path: Path) -> None:
    out_path = tmp_path / "3d.png"
    fake_png = _make_png(body_size=2048)
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        route = mock.get("/slicer/threeD", params={"lookFromAxis": "A"}).mock(
            return_value=Response(200, content=fake_png, headers={"content-type": "image/png"})
        )
        result = runner.invoke(
            app, ["--json", "render", "threed", "--out", str(out_path), "--look", "A"]
        )

    assert result.exit_code == 0, result.stderr
    assert route.called
    assert out_path.read_bytes() == fake_png


def test_render_threed_invalid_look_blocked(runner: CliRunner, tmp_path: Path) -> None:
    with respx.mock(base_url="http://127.0.0.1:2016", assert_all_called=False):
        result = runner.invoke(
            app,
            [
                "--json",
                "render",
                "threed",
                "--out",
                str(tmp_path / "x.png"),
                "--look",
                "Z",
            ],
        )
    assert result.exit_code == 1
    assert json.loads(result.stdout)["error"]["code"] == "E_BAD_INPUT"


# --------------------------------------------------------------- render screenshot


def test_render_screenshot_happy_path(runner: CliRunner, tmp_path: Path) -> None:
    out_path = tmp_path / "ss.png"
    fake_png = _make_png(body_size=4096)
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        route = mock.get("/slicer/screenshot").mock(
            return_value=Response(200, content=fake_png, headers={"content-type": "image/png"})
        )
        result = runner.invoke(app, ["--json", "render", "screenshot", "--out", str(out_path)])

    assert result.exit_code == 0, result.stderr
    assert route.called
    assert out_path.read_bytes() == fake_png


def test_render_screenshot_when_main_window_absent(runner: CliRunner, tmp_path: Path) -> None:
    """Slicer typically returns 5xx with a python traceback when main window is absent."""
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        mock.get("/slicer/screenshot").mock(
            return_value=Response(500, json={"message": "no main window"})
        )
        result = runner.invoke(
            app, ["--json", "render", "screenshot", "--out", str(tmp_path / "x.png")]
        )
    assert result.exit_code == 2
    assert json.loads(result.stdout)["error"]["code"] == "E_HTTP_5XX"


# --------------------------------------------------------------- render gltf


def test_render_gltf_happy_path(runner: CliRunner, tmp_path: Path) -> None:
    """Slicer returns JSON glTF in this build (~10 KB); validate_binary accepts it."""
    out_path = tmp_path / "scene.gltf"
    fake_gltf = b'{"asset":{"version":"2.0"}}' + b" " * 2000
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        route = mock.get(
            "/slicer/threeDGraphics", params={"widgetIndex": "0", "boxVisible": "false"}
        ).mock(
            return_value=Response(
                200, content=fake_gltf, headers={"content-type": "application/json"}
            )
        )
        result = runner.invoke(app, ["--json", "render", "gltf", "--out", str(out_path)])

    assert result.exit_code == 0, result.stderr
    assert route.called
    assert out_path.read_bytes() == fake_gltf


def test_render_gltf_too_small_blocked(runner: CliRunner, tmp_path: Path) -> None:
    """< 1024 byte glTF response → E_BAD_RESPONSE."""
    with respx.mock(base_url="http://127.0.0.1:2016") as mock:
        mock.get("/slicer/threeDGraphics").mock(
            return_value=Response(200, content=b"{}", headers={"content-type": "application/json"})
        )
        result = runner.invoke(app, ["--json", "render", "gltf", "--out", str(tmp_path / "x.gltf")])
    assert result.exit_code == 2
    assert json.loads(result.stdout)["error"]["code"] == "E_BAD_RESPONSE"


# --------------------------------------------------------------- --out required


def test_render_slice_requires_out(runner: CliRunner) -> None:
    """Locked Q-D — consistent with `volume export`."""
    result = runner.invoke(app, ["--json", "render", "slice"])
    # Typer exits 2 for missing required option.
    assert result.exit_code == 2
