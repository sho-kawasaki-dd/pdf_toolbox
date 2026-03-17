from __future__ import annotations

from pathlib import Path

from model.merge.merge_session import MergeSession


def test_add_inputs_deduplicates_case_insensitive(tmp_path: Path) -> None:
    session = MergeSession()
    first = tmp_path / "sample.pdf"
    second = tmp_path / "other.pdf"

    accepted = session.add_inputs([str(first), str(first).upper(), str(second)])

    assert accepted == [str(first), str(second)]
    assert session.input_paths == [str(first), str(second)]


def test_set_selected_paths_ignores_unknown_inputs(tmp_path: Path) -> None:
    session = MergeSession()
    first = tmp_path / "first.pdf"
    second = tmp_path / "second.pdf"
    session.add_inputs([str(first), str(second)])

    session.set_selected_paths([str(second), str(tmp_path / "missing.pdf")])

    assert session.selected_paths == [str(second)]


def test_remove_selected_inputs_updates_list_and_selection(tmp_path: Path) -> None:
    session = MergeSession()
    first = tmp_path / "first.pdf"
    second = tmp_path / "second.pdf"
    third = tmp_path / "third.pdf"
    session.add_inputs([str(first), str(second), str(third)])
    session.set_selected_paths([str(second), str(third)])

    removed = session.remove_selected_inputs()

    assert removed == [str(second), str(third)]
    assert session.input_paths == [str(first)]
    assert session.selected_paths == []


def test_move_selected_up_preserves_relative_order(tmp_path: Path) -> None:
    session = MergeSession()
    paths = [tmp_path / f"file{i}.pdf" for i in range(4)]
    session.add_inputs([str(path) for path in paths])
    session.set_selected_paths([str(paths[2]), str(paths[3])])

    moved = session.move_selected_up()

    assert moved is True
    assert session.input_paths == [str(paths[0]), str(paths[2]), str(paths[3]), str(paths[1])]
    assert session.selected_paths == [str(paths[2]), str(paths[3])]


def test_move_selected_down_preserves_relative_order(tmp_path: Path) -> None:
    session = MergeSession()
    paths = [tmp_path / f"file{i}.pdf" for i in range(4)]
    session.add_inputs([str(path) for path in paths])
    session.set_selected_paths([str(paths[0]), str(paths[1])])

    moved = session.move_selected_down()

    assert moved is True
    assert session.input_paths == [str(paths[2]), str(paths[0]), str(paths[1]), str(paths[3])]


def test_reorder_inputs_requires_same_members(tmp_path: Path) -> None:
    session = MergeSession()
    first = tmp_path / "first.pdf"
    second = tmp_path / "second.pdf"
    session.add_inputs([str(first), str(second)])

    assert session.reorder_inputs([str(first)]) is False
    assert session.input_paths == [str(first), str(second)]


def test_set_output_path_and_active_session_flags(tmp_path: Path) -> None:
    session = MergeSession()
    output_path = tmp_path / "merged.pdf"

    assert session.has_active_session() is False

    session.set_output_path(str(output_path))

    assert session.output_path == str(output_path)
    assert session.has_active_session() is True