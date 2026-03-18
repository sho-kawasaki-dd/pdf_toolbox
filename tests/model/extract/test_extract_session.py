from __future__ import annotations

from pathlib import Path

import pytest

from model.extract.extract_session import (
    ExtractSession,
    SourcePageRef,
    ZOOM_DEFAULT,
    ZOOM_MAX,
    ZOOM_MIN,
    ZOOM_STEP,
)


# ── Source 追加・削除 ────────────────────────────────────


def test_add_source_returns_document(tmp_path: Path) -> None:
    session = ExtractSession()
    doc = session.add_source(str(tmp_path / "a.pdf"), 5)
    assert doc is not None
    assert doc.page_count == 5
    assert len(session.source_documents) == 1


def test_add_source_deduplicates_case_insensitive(tmp_path: Path) -> None:
    session = ExtractSession()
    first = session.add_source(str(tmp_path / "A.pdf"), 3)
    second = session.add_source(str(tmp_path / "a.pdf"), 3)
    assert first is not None
    assert second is None
    assert len(session.source_documents) == 1


def test_add_multiple_sources(tmp_path: Path) -> None:
    session = ExtractSession()
    doc_a = session.add_source(str(tmp_path / "a.pdf"), 3)
    doc_b = session.add_source(str(tmp_path / "b.pdf"), 5)
    assert doc_a is not None
    assert doc_b is not None
    assert len(session.source_documents) == 2


def test_remove_source_deletes_document(tmp_path: Path) -> None:
    session = ExtractSession()
    doc = session.add_source(str(tmp_path / "a.pdf"), 3)
    assert doc is not None
    assert session.remove_source(doc.id)
    assert len(session.source_documents) == 0


def test_remove_source_removes_target_entries(tmp_path: Path) -> None:
    session = ExtractSession()
    doc = session.add_source(str(tmp_path / "a.pdf"), 3)
    assert doc is not None
    ref = SourcePageRef(doc_id=doc.id, page_index=0)
    session.add_to_target([ref])
    assert len(session.target_entries) == 1

    session.remove_source(doc.id)
    assert len(session.target_entries) == 0


def test_remove_source_clears_selected_source_pages(tmp_path: Path) -> None:
    session = ExtractSession()
    doc = session.add_source(str(tmp_path / "a.pdf"), 3)
    assert doc is not None
    ref = SourcePageRef(doc_id=doc.id, page_index=1)
    session.set_selected_source_pages([ref])
    assert len(session.selected_source_pages) == 1

    session.remove_source(doc.id)
    assert len(session.selected_source_pages) == 0


def test_remove_nonexistent_source_returns_false() -> None:
    session = ExtractSession()
    assert session.remove_source("no-such-id") is False


def test_get_source_document(tmp_path: Path) -> None:
    session = ExtractSession()
    doc = session.add_source(str(tmp_path / "a.pdf"), 3)
    assert doc is not None
    assert session.get_source_document(doc.id) is doc
    assert session.get_source_document("missing") is None


# ── Source 選択 ──────────────────────────────────────────


def test_set_selected_source_pages_filters_invalid(tmp_path: Path) -> None:
    session = ExtractSession()
    doc = session.add_source(str(tmp_path / "a.pdf"), 3)
    assert doc is not None

    good = SourcePageRef(doc_id=doc.id, page_index=2)
    out_of_range = SourcePageRef(doc_id=doc.id, page_index=5)
    bad_doc = SourcePageRef(doc_id="nope", page_index=0)

    session.set_selected_source_pages([good, out_of_range, bad_doc])
    assert session.selected_source_pages == [good]


# ── Target 操作 ──────────────────────────────────────────


def test_add_to_target(tmp_path: Path) -> None:
    session = ExtractSession()
    doc = session.add_source(str(tmp_path / "a.pdf"), 3)
    assert doc is not None
    refs = [
        SourcePageRef(doc_id=doc.id, page_index=0),
        SourcePageRef(doc_id=doc.id, page_index=1),
    ]
    added = session.add_to_target(refs)
    assert len(added) == 2
    assert len(session.target_entries) == 2


def test_add_to_target_allows_duplicates(tmp_path: Path) -> None:
    session = ExtractSession()
    doc = session.add_source(str(tmp_path / "a.pdf"), 3)
    assert doc is not None
    ref = SourcePageRef(doc_id=doc.id, page_index=0)
    session.add_to_target([ref])
    session.add_to_target([ref])
    assert len(session.target_entries) == 2


def test_add_to_target_rejects_invalid_refs(tmp_path: Path) -> None:
    session = ExtractSession()
    doc = session.add_source(str(tmp_path / "a.pdf"), 3)
    assert doc is not None
    bad_doc = SourcePageRef(doc_id="no-id", page_index=0)
    bad_page = SourcePageRef(doc_id=doc.id, page_index=99)
    added = session.add_to_target([bad_doc, bad_page])
    assert added == []


def test_remove_selected_targets(tmp_path: Path) -> None:
    session = ExtractSession()
    doc = session.add_source(str(tmp_path / "a.pdf"), 3)
    assert doc is not None
    refs = [SourcePageRef(doc_id=doc.id, page_index=i) for i in range(3)]
    entries = session.add_to_target(refs)
    session.set_selected_target_ids([entries[1].id])

    removed = session.remove_selected_targets()
    assert removed == [entries[1].id]
    assert len(session.target_entries) == 2
    assert session.selected_target_ids == []


def test_clear_target(tmp_path: Path) -> None:
    session = ExtractSession()
    doc = session.add_source(str(tmp_path / "a.pdf"), 3)
    assert doc is not None
    refs = [SourcePageRef(doc_id=doc.id, page_index=i) for i in range(3)]
    session.add_to_target(refs)
    session.set_selected_target_ids([session.target_entries[0].id])

    count = session.clear_target()
    assert count == 3
    assert session.target_entries == []
    assert session.selected_target_ids == []


def test_move_selected_target_up(tmp_path: Path) -> None:
    session = ExtractSession()
    doc = session.add_source(str(tmp_path / "a.pdf"), 4)
    assert doc is not None
    entries = session.add_to_target(
        [SourcePageRef(doc_id=doc.id, page_index=i) for i in range(4)]
    )
    session.set_selected_target_ids([entries[2].id, entries[3].id])

    assert session.move_selected_target_up()
    ids = [e.id for e in session.target_entries]
    assert ids == [entries[0].id, entries[2].id, entries[3].id, entries[1].id]


def test_move_selected_target_down(tmp_path: Path) -> None:
    session = ExtractSession()
    doc = session.add_source(str(tmp_path / "a.pdf"), 4)
    assert doc is not None
    entries = session.add_to_target(
        [SourcePageRef(doc_id=doc.id, page_index=i) for i in range(4)]
    )
    session.set_selected_target_ids([entries[0].id, entries[1].id])

    assert session.move_selected_target_down()
    ids = [e.id for e in session.target_entries]
    assert ids == [entries[2].id, entries[0].id, entries[1].id, entries[3].id]


def test_move_target_up_at_top_noop(tmp_path: Path) -> None:
    session = ExtractSession()
    doc = session.add_source(str(tmp_path / "a.pdf"), 2)
    assert doc is not None
    entries = session.add_to_target(
        [SourcePageRef(doc_id=doc.id, page_index=i) for i in range(2)]
    )
    session.set_selected_target_ids([entries[0].id])
    assert not session.move_selected_target_up()


def test_move_target_down_at_bottom_noop(tmp_path: Path) -> None:
    session = ExtractSession()
    doc = session.add_source(str(tmp_path / "a.pdf"), 2)
    assert doc is not None
    entries = session.add_to_target(
        [SourcePageRef(doc_id=doc.id, page_index=i) for i in range(2)]
    )
    session.set_selected_target_ids([entries[1].id])
    assert not session.move_selected_target_down()


def test_reorder_target(tmp_path: Path) -> None:
    session = ExtractSession()
    doc = session.add_source(str(tmp_path / "a.pdf"), 3)
    assert doc is not None
    entries = session.add_to_target(
        [SourcePageRef(doc_id=doc.id, page_index=i) for i in range(3)]
    )
    new_order = [entries[2].id, entries[0].id, entries[1].id]
    assert session.reorder_target(new_order)
    assert [e.id for e in session.target_entries] == new_order


def test_reorder_target_rejects_mismatched_ids(tmp_path: Path) -> None:
    session = ExtractSession()
    doc = session.add_source(str(tmp_path / "a.pdf"), 2)
    assert doc is not None
    session.add_to_target(
        [SourcePageRef(doc_id=doc.id, page_index=i) for i in range(2)]
    )
    assert not session.reorder_target(["only-one"])
    assert not session.reorder_target(["fake-id-1", "fake-id-2"])


# ── ズーム ───────────────────────────────────────────────


def test_source_zoom_cycle() -> None:
    session = ExtractSession()
    assert session.source_zoom_percent == ZOOM_DEFAULT

    session.zoom_in_source()
    assert session.source_zoom_percent == ZOOM_DEFAULT + ZOOM_STEP

    session.zoom_out_source()
    assert session.source_zoom_percent == ZOOM_DEFAULT

    session.reset_source_zoom()
    assert session.source_zoom_percent == ZOOM_DEFAULT


def test_source_zoom_clamps_at_bounds() -> None:
    session = ExtractSession()
    session.source_zoom_percent = ZOOM_MAX
    session.zoom_in_source()
    assert session.source_zoom_percent == ZOOM_MAX

    session.source_zoom_percent = ZOOM_MIN
    session.zoom_out_source()
    assert session.source_zoom_percent == ZOOM_MIN


def test_target_zoom_cycle() -> None:
    session = ExtractSession()
    assert session.target_zoom_percent == ZOOM_DEFAULT

    session.zoom_in_target()
    assert session.target_zoom_percent == ZOOM_DEFAULT + ZOOM_STEP

    session.zoom_out_target()
    assert session.target_zoom_percent == ZOOM_DEFAULT

    session.reset_target_zoom()
    assert session.target_zoom_percent == ZOOM_DEFAULT


def test_target_zoom_clamps_at_bounds() -> None:
    session = ExtractSession()
    session.target_zoom_percent = ZOOM_MAX
    session.zoom_in_target()
    assert session.target_zoom_percent == ZOOM_MAX

    session.target_zoom_percent = ZOOM_MIN
    session.zoom_out_target()
    assert session.target_zoom_percent == ZOOM_MIN


def test_source_and_target_zoom_independent() -> None:
    session = ExtractSession()
    session.zoom_in_source()
    session.zoom_in_source()
    assert session.source_zoom_percent == ZOOM_DEFAULT + 2 * ZOOM_STEP
    assert session.target_zoom_percent == ZOOM_DEFAULT


# ── 出力・実行制御 ──────────────────────────────────────


def test_set_output_path(tmp_path: Path) -> None:
    session = ExtractSession()
    session.set_output_path(str(tmp_path / "out.pdf"))
    assert session.output_path is not None
    session.set_output_path(None)
    assert session.output_path is None


def test_has_active_session(tmp_path: Path) -> None:
    session = ExtractSession()
    assert not session.has_active_session()

    session.add_source(str(tmp_path / "a.pdf"), 1)
    assert session.has_active_session()


def test_has_active_session_with_output_only(tmp_path: Path) -> None:
    session = ExtractSession()
    session.set_output_path(str(tmp_path / "out.pdf"))
    assert session.has_active_session()


def test_can_execute(tmp_path: Path) -> None:
    session = ExtractSession()
    assert not session.can_execute()

    doc = session.add_source(str(tmp_path / "a.pdf"), 1)
    assert doc is not None
    session.add_to_target([SourcePageRef(doc_id=doc.id, page_index=0)])
    assert not session.can_execute()  # no output_path

    session.set_output_path(str(tmp_path / "out.pdf"))
    assert session.can_execute()

    session.begin_execution()
    assert not session.can_execute()

    session.finish_execution()
    assert session.can_execute()


def test_execution_lifecycle() -> None:
    session = ExtractSession()
    assert not session.is_running
    assert not session.cancel_requested

    session.begin_execution()
    assert session.is_running
    assert not session.cancel_requested

    session.request_cancel()
    assert session.cancel_requested

    session.finish_execution()
    assert not session.is_running
