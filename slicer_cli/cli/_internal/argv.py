"""argv pre-processor that lifts known global flags to the front.

Click's grammar requires global options to appear *before* the subcommand
(e.g. `slicer-cli --json status`). Agents naturally write the verb first
(`slicer-cli status --json`). Rather than duplicating `--json` / `--pretty`
on every command, we re-order argv at the entry point.

Used from `cli/app.py:main`. Independently importable for tests.
"""

from __future__ import annotations

# Flags that may appear after the subcommand and should be hoisted to the front.
GLOBAL_FLAGS_BOOL: frozenset[str] = frozenset({"--json", "--pretty", "--quiet"})
GLOBAL_FLAGS_VALUE: frozenset[str] = frozenset({"--url", "--timeout"})


def hoist_global_flags(argv: list[str]) -> list[str]:
    """Re-order argv so global flags work *after* the subcommand too.

    `slicer-cli status --json` is more natural for agents than the strict
    Click convention `slicer-cli --json status`. This function lifts known
    global flags (and their values) to the front so Typer's root callback
    still picks them up.
    """
    hoisted: list[str] = []
    rest: list[str] = []
    i = 0
    while i < len(argv):
        token = argv[i]
        if token in GLOBAL_FLAGS_BOOL:
            hoisted.append(token)
            i += 1
            continue
        if token in GLOBAL_FLAGS_VALUE:
            hoisted.append(token)
            if i + 1 < len(argv):
                hoisted.append(argv[i + 1])
                i += 2
            else:
                i += 1
            continue
        # Match `--key=value` style for value flags.
        if any(token.startswith(f"{flag}=") for flag in GLOBAL_FLAGS_VALUE):
            hoisted.append(token)
            i += 1
            continue
        rest.append(token)
        i += 1
    return hoisted + rest
