"""Tests for `client._internal.audit.AuditLogger`.

We assert on the canonical line shape (timestamp, rev, url, hash, preview,
op label), append-on-write semantics, mkdir-of-parents on first write, and
clean error mapping when the path is unwritable.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from slicer_cli.client._internal.audit import AuditLogger
from slicer_cli.client.errors import ErrorCode, SlicerConfigError

# A relaxed regex: the line shape is fixed, but `rev=` is environment-dependent
# (7 hex chars in a git checkout, "unknown" otherwise) and timestamp/hash vary.
_LINE_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z  "
    r"rev=(?:[0-9a-f]{7}|unknown)  "
    r"url=http://[^\s]+  "
    r"hash=sha256:[0-9a-f]{64}  "
    r'preview="[^"]*"  '
    r"op=[\w.]+$"
)


def test_log_writes_one_line_in_prd_format(tmp_path: Path) -> None:
    log_path = tmp_path / "exec.log"
    logger = AuditLogger(path=log_path)
    logger.log(b"print('hi')", url="http://127.0.0.1:2016", op_label="test.basic")

    contents = log_path.read_text()
    assert contents.endswith("\n")
    line = contents.rstrip("\n")
    assert "\n" not in line, "audit line must be exactly one line"
    assert _LINE_RE.match(line), f"line did not match expected shape: {line!r}"


def test_log_creates_parent_directories(tmp_path: Path) -> None:
    nested = tmp_path / "deeply" / "nested" / "dir" / "exec.log"
    AuditLogger(path=nested).log(b"x", url="http://x", op_label="t")
    assert nested.is_file()


def test_log_appends_on_subsequent_writes(tmp_path: Path) -> None:
    log_path = tmp_path / "exec.log"
    logger = AuditLogger(path=log_path)
    logger.log(b"first", url="http://x", op_label="t")
    logger.log(b"second", url="http://x", op_label="t")

    lines = log_path.read_text().rstrip("\n").split("\n")
    assert len(lines) == 2


def test_log_preserves_line_one_line_with_multiline_source(tmp_path: Path) -> None:
    """Multiline Python source must collapse to a single audit line."""
    log_path = tmp_path / "exec.log"
    src = b"import slicer\nprint('a')\nprint('b')\n"
    AuditLogger(path=log_path).log(src, url="http://x", op_label="t")

    contents = log_path.read_text().rstrip("\n")
    assert contents.count("\n") == 0
    # The newlines inside the source must appear escaped as the literal \n in
    # the preview field, so a downstream `awk -F"  "` keeps working.
    assert r"\n" in contents


def test_log_truncates_preview_at_200_chars(tmp_path: Path) -> None:
    log_path = tmp_path / "exec.log"
    long_src = b"x" * 1000
    AuditLogger(path=log_path).log(long_src, url="http://x", op_label="t")

    line = log_path.read_text().rstrip("\n")
    # Extract the preview field: between `preview="` and the next `"`
    match = re.search(r'preview="([^"]*)"', line)
    assert match is not None
    preview = match.group(1)
    assert len(preview) <= 200


def test_log_hash_matches_sha256_of_full_source(tmp_path: Path) -> None:
    """The hash must be over the FULL source bytes, not the truncated preview."""
    import hashlib

    log_path = tmp_path / "exec.log"
    src = b"y" * 1000
    AuditLogger(path=log_path).log(src, url="http://x", op_label="t")

    expected = hashlib.sha256(src).hexdigest()
    assert f"hash=sha256:{expected}" in log_path.read_text()


def test_log_unwritable_path_raises_slicer_config_error(tmp_path: Path) -> None:
    """ENOSPC / EACCES must surface as SlicerConfigError, not generic OSError."""
    # Make the parent dir read-only so mkdir + open both fail.
    blocker = tmp_path / "blocker"
    blocker.touch()
    # Path under a regular file is not a valid directory; mkdir(parents=True)
    # will raise NotADirectoryError, which is an OSError subclass.
    bad_path = blocker / "subdir" / "exec.log"
    logger = AuditLogger(path=bad_path)

    with pytest.raises(SlicerConfigError) as exc_info:
        logger.log(b"x", url="http://x", op_label="t")
    assert exc_info.value.code == ErrorCode.E_CONFIG


def test_log_handles_non_utf8_source_gracefully(tmp_path: Path) -> None:
    """Bytes that aren't valid UTF-8 must not crash the logger."""
    log_path = tmp_path / "exec.log"
    src = b"\xff\xfe\xfd\xfc"
    AuditLogger(path=log_path).log(src, url="http://x", op_label="t")
    # Just confirm it wrote a line; preview content is not asserted.
    assert log_path.read_text().count("\n") == 1
