"""Extract a single version's section from a Keep-a-Changelog file.

Usage
-----
    python scripts/extract_changelog.py 0.1.0
    python scripts/extract_changelog.py 0.1.0 --file CHANGELOG.md

The matched section's body (everything between the `## [VERSION]` header
and the next `## [...]` header or the link-reference block at the bottom)
is printed to stdout, stripped of leading/trailing blank lines.

Exit codes
----------
    0  section found and printed
    1  section not found, or the file is missing
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

HEADER_RE = re.compile(r"^## \[(?P<version>[^\]]+)\]")
LINK_REF_RE = re.compile(r"^\[[^\]]+\]:\s")


def extract_section(changelog: str, version: str) -> str:
    """Return the body of the section for ``version`` in ``changelog``.

    Parameters
    ----------
    changelog : str
        Full text of a Keep-a-Changelog formatted file.
    version : str
        Version to extract, without a leading ``v`` (e.g. ``"0.1.0"``).

    Returns
    -------
    str
        The section body — everything between the matching header and
        the next ``## [...]`` header (or the link-reference block at
        the bottom), with leading and trailing blank lines stripped.

    Raises
    ------
    KeyError
        If no header matches ``version``.
    """
    lines = changelog.splitlines()
    start: int | None = None
    end: int | None = None

    for i, line in enumerate(lines):
        if start is None:
            match = HEADER_RE.match(line)
            if match is not None and match.group("version") == version:
                start = i + 1
            continue
        if HEADER_RE.match(line) is not None or LINK_REF_RE.match(line) is not None:
            end = i
            break

    if start is None:
        raise KeyError(f"no section for version {version!r} in changelog")

    if end is None:
        end = len(lines)

    return "\n".join(lines[start:end]).strip("\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", help="Version to extract (e.g. 0.1.0).")
    parser.add_argument(
        "--file",
        type=Path,
        default=Path("CHANGELOG.md"),
        help="Path to the changelog file (default: ./CHANGELOG.md).",
    )
    args = parser.parse_args(argv)

    path: Path = args.file
    if not path.is_file():
        print(f"changelog not found: {path}", file=sys.stderr)
        return 1

    try:
        body = extract_section(path.read_text(encoding="utf-8"), args.version)
    except KeyError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
