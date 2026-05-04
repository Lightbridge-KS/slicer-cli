"""Tests for `scripts/extract_changelog.py`."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest


def _load_extract_changelog() -> ModuleType:
    """Import scripts/extract_changelog.py by file path (it lives outside the package)."""
    repo_root = Path(__file__).resolve().parents[2]
    module_path = repo_root / "scripts" / "extract_changelog.py"
    spec = importlib.util.spec_from_file_location("extract_changelog", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["extract_changelog"] = module
    spec.loader.exec_module(module)
    return module


extract_changelog = _load_extract_changelog()
extract_section = extract_changelog.extract_section
main = extract_changelog.main


SAMPLE = """\
# Changelog

## [Unreleased]

## [0.2.0] - 2026-06-01

### Added

- Feature B.

## [0.1.0] - 2026-05-04

### Added

- Feature A.

### Safety

- Empty selectors refused.

[Unreleased]: https://example.com/compare/v0.2.0...HEAD
[0.2.0]: https://example.com/releases/tag/v0.2.0
[0.1.0]: https://example.com/releases/tag/v0.1.0
"""


def test_extract_section_returns_body_for_middle_version() -> None:
    body = extract_section(SAMPLE, "0.2.0")
    assert body.startswith("### Added")
    assert "Feature B." in body
    # must not bleed into the next section
    assert "Feature A." not in body
    assert "## [0.1.0]" not in body


def test_extract_section_returns_body_for_last_version_excluding_link_refs() -> None:
    body = extract_section(SAMPLE, "0.1.0")
    assert "Feature A." in body
    assert "Empty selectors refused." in body
    # link references at the bottom must NOT be included
    assert "https://example.com" not in body
    assert "[Unreleased]:" not in body


def test_extract_section_handles_empty_unreleased() -> None:
    body = extract_section(SAMPLE, "Unreleased")
    assert body == ""


def test_extract_section_unknown_version_raises_keyerror() -> None:
    with pytest.raises(KeyError, match=r"9\.9\.9"):
        extract_section(SAMPLE, "9.9.9")


def test_extract_section_strips_leading_and_trailing_blanks() -> None:
    body = extract_section(SAMPLE, "0.2.0")
    assert not body.startswith("\n")
    assert not body.endswith("\n")


def test_main_prints_section_to_stdout(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(SAMPLE, encoding="utf-8")
    rc = main(["0.1.0", "--file", str(changelog)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Feature A." in out


def test_main_returns_1_for_unknown_version(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(SAMPLE, encoding="utf-8")
    rc = main(["9.9.9", "--file", str(changelog)])
    err = capsys.readouterr().err
    assert rc == 1
    assert "9.9.9" in err


def test_main_returns_1_for_missing_file(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    missing = tmp_path / "does-not-exist.md"
    rc = main(["0.1.0", "--file", str(missing)])
    err = capsys.readouterr().err
    assert rc == 1
    assert "does-not-exist.md" in err


def test_real_changelog_has_a_0_1_0_section() -> None:
    """Smoke check against the live CHANGELOG.md in the repo."""
    repo_root = Path(__file__).resolve().parents[2]
    changelog = (repo_root / "CHANGELOG.md").read_text(encoding="utf-8")
    body = extract_section(changelog, "0.1.0")
    assert body.strip(), "expected the [0.1.0] section to have content"
    assert "## [" not in body, "section bled into the next one"
