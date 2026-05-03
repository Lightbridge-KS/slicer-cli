"""Safety guard helpers — `require_confirm`, `require_nonempty_id`."""

from __future__ import annotations

import pytest

from slicer_cli.cli._internal.safety import require_confirm, require_nonempty_id
from slicer_cli.client.errors import (
    ErrorCode,
    SlicerDestructiveError,
    SlicerEmptySelectorError,
)

# ---------------------------------------------------------------- require_confirm


def test_require_confirm_passes_when_true() -> None:
    require_confirm(True, "scene clear")  # no exception


def test_require_confirm_raises_when_false() -> None:
    with pytest.raises(SlicerDestructiveError) as info:
        require_confirm(False, "scene clear")
    assert info.value.code == ErrorCode.E_DESTRUCTIVE
    assert "scene clear" in info.value.message
    assert info.value.hint is not None
    assert "--confirm" in info.value.hint


def test_require_confirm_custom_flag_in_hint() -> None:
    with pytest.raises(SlicerDestructiveError) as info:
        require_confirm(False, "system shutdown", flag="--yes")
    assert info.value.hint is not None
    assert "--yes" in info.value.hint


# ---------------------------------------------------------- require_nonempty_id


def test_require_nonempty_id_returns_clean() -> None:
    assert require_nonempty_id("vtkMRMLScalarVolumeNode1") == "vtkMRMLScalarVolumeNode1"


def test_require_nonempty_id_strips_whitespace() -> None:
    assert require_nonempty_id("  vtkMRMLScalarVolumeNode1  ") == "vtkMRMLScalarVolumeNode1"


@pytest.mark.parametrize("bad_id", [None, "", "   ", "\t\n"])
def test_require_nonempty_id_rejects(bad_id: str | None) -> None:
    with pytest.raises(SlicerEmptySelectorError) as info:
        require_nonempty_id(bad_id)
    assert info.value.code == ErrorCode.E_EMPTY_SELECTOR
    assert info.value.hint is not None
    assert "DELETE /slicer/mrml" in info.value.hint
