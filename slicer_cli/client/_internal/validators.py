"""Binary-content validators shared by render endpoints + doctor probes.

These guard against the "Slicer returned 200 but the body is garbage" failure
mode (e.g., headless Linux without Mesa returns an empty PNG, or a
misconfigured viewer returns a 0x0 PNG). Validation lives at the client
layer so every consumer (CLI, future MCP server, doctor probes) is
defended; the public Render methods raise `SlicerBadResponseError` rather
than handing back broken bytes.
"""

from __future__ import annotations

from slicer_cli.client.errors import SlicerBadResponseError

_PNG_MAGIC: bytes = b"\x89PNG\r\n\x1a\n"
_MIN_PNG_BYTES: int = 256
_MESA_HINT: str = (
    "On headless Linux without GPU, set GALLIUM_DRIVER=llvmpipe before "
    "launching Slicer for software OpenGL."
)


def validate_png(content: bytes, *, endpoint: str) -> bytes:
    """Verify `content` looks like a non-empty, non-degenerate PNG.

    Three checks:
    1. PNG magic header (`\\x89PNG\\r\\n\\x1a\\n`).
    2. Total length >= 256 bytes (a 1x1 transparent PNG is ~70 bytes — anything
       smaller than 256 is essentially a header with no image data).
    3. IHDR width/height (bytes 16-24, big-endian) are both non-zero.

    Raises `SlicerBadResponseError` (→ E_BAD_RESPONSE) on any failure with a
    hint that literally contains `GALLIUM_DRIVER=llvmpipe` so agents can
    copy-paste the fix.
    """
    if not content.startswith(_PNG_MAGIC):
        raise SlicerBadResponseError(
            f"Expected a PNG response, got {len(content)} bytes that are not a PNG.",
            endpoint=endpoint,
        )
    if len(content) < _MIN_PNG_BYTES:
        raise SlicerBadResponseError(
            f"PNG too small ({len(content)} bytes) — likely an empty viewport.",
            endpoint=endpoint,
            hint=_MESA_HINT,
        )
    width = int.from_bytes(content[16:20], "big")
    height = int.from_bytes(content[20:24], "big")
    if width == 0 or height == 0:
        raise SlicerBadResponseError(
            f"PNG has zero dimensions ({width}x{height}).",
            endpoint=endpoint,
            hint="Check that the Slicer viewer is initialized; try `slicer-cli doctor`.",
        )
    return content


def validate_binary(content: bytes, *, endpoint: str, min_bytes: int) -> bytes:
    """Generic non-empty-bytes guard for endpoints without a known magic header.

    Used for glTF (Slicer can return either binary `.glb` or JSON `.gltf`, so
    we don't check magic bytes — only that the response is a sensible size).
    """
    if len(content) < min_bytes:
        raise SlicerBadResponseError(
            f"Response too small ({len(content)} bytes < {min_bytes}).",
            endpoint=endpoint,
            hint="Likely an empty render — check viewer state and `doctor` probes.",
        )
    return content
