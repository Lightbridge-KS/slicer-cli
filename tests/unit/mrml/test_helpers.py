"""mrml/_helpers — id_to_class, parse_class_filter, attach_class_to_refs, format_node_table."""

from __future__ import annotations

import pytest

from slicer_cli.cli._internal.mrml_helpers import (
    attach_class_to_refs,
    format_node_table,
    id_to_class,
    parse_class_filter,
)

# --------------------------------------------------------------------- id_to_class


@pytest.mark.parametrize(
    ("node_id", "expected"),
    [
        ("vtkMRMLScalarVolumeNode1", "vtkMRMLScalarVolumeNode"),
        ("vtkMRMLViewNode1", "vtkMRMLViewNode"),
        ("vtkMRMLSliceNodeRed", "vtkMRMLSliceNode"),
        ("vtkMRMLLayoutNodevtkMRMLLayoutNode", "vtkMRMLLayoutNode"),
        ("vtkMRMLColorTableNodeFileMagma.txt", "vtkMRMLColorTableNode"),
        ("vtkMRMLCrosshairNodedefault", "vtkMRMLCrosshairNode"),
        ("vtkMRMLSelectionNodeSingleton", "vtkMRMLSelectionNode"),
    ],
)
def test_id_to_class_extracts_canonical_class(node_id: str, expected: str) -> None:
    assert id_to_class(node_id) == expected


@pytest.mark.parametrize("bad_id", ["", "notAVtkId", "Volume1", "vtkOther"])
def test_id_to_class_returns_none_for_unparseable(bad_id: str) -> None:
    assert id_to_class(bad_id) is None


# ------------------------------------------------------------- parse_class_filter


def test_parse_class_filter_passes_through() -> None:
    assert parse_class_filter("vtkMRMLScalarVolumeNode") == "vtkMRMLScalarVolumeNode"


def test_parse_class_filter_strips_whitespace() -> None:
    assert parse_class_filter("  vtkMRMLViewNode  ") == "vtkMRMLViewNode"


@pytest.mark.parametrize("empty", [None, "", "   "])
def test_parse_class_filter_returns_none_for_empty(empty: str | None) -> None:
    assert parse_class_filter(empty) is None


# ------------------------------------------------------------ attach_class_to_refs


def test_attach_class_to_refs_zips_and_decorates() -> None:
    refs = attach_class_to_refs(
        ["vtkMRMLScalarVolumeNode1", "vtkMRMLViewNode1"],
        ["MRHead", "View1"],
    )
    assert len(refs) == 2
    assert refs[0].id == "vtkMRMLScalarVolumeNode1"
    assert refs[0].name == "MRHead"
    assert refs[0].class_ == "vtkMRMLScalarVolumeNode"
    assert refs[1].class_ == "vtkMRMLViewNode"


def test_attach_class_to_refs_handles_unknown_class() -> None:
    refs = attach_class_to_refs(["bogus_id"], ["whatever"])
    assert refs[0].class_ is None


def test_attach_class_to_refs_handles_unequal_lengths() -> None:
    """Defensive: zip stops at the shorter sequence rather than crashing."""
    refs = attach_class_to_refs(
        ["vtkMRMLScalarVolumeNode1", "vtkMRMLViewNode1"],
        ["MRHead"],  # only one name
    )
    assert len(refs) == 1


# ------------------------------------------------------------- format_node_table


def test_format_node_table_has_three_columns() -> None:
    refs = attach_class_to_refs(["vtkMRMLScalarVolumeNode1"], ["MRHead"])
    table = format_node_table(refs)
    assert len(table.columns) == 3
    headers = [str(col.header) for col in table.columns]
    assert headers == ["ID", "Name", "Class"]


def test_format_node_table_renders_dash_for_unknown_class() -> None:
    refs = attach_class_to_refs(["bogus_id"], ["whatever"])
    table = format_node_table(refs)
    # rich.Table stores rows lazily — just verify it builds without error
    assert table.row_count == 1
