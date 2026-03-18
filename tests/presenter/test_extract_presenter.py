from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, PropertyMock

import pytest

from model.extract.extract_session import SourcePageRef
from presenter.extract_presenter import ExtractPresenter


def _make_mock_view() -> MagicMock:
    """ExtractPresenter が必要とする MainWindow モックを返す。"""
    view = MagicMock()
    view.ask_open_files.return_value = []
    view.ask_save_file.return_value = None
    view.ask_ok_cancel.return_value = False
    view.ask_yes_no.return_value = True
    view.schedule.return_value = "timer_1"
    # extract_view のシグナルを MagicMock で表現
    ev = MagicMock()
    ev.target_list = MagicMock()
    view.extract_view = ev
    return view


def _stub_thumbnail_loader(**overrides) -> SimpleNamespace:
    defaults = dict(
        request_thumbnails=MagicMock(return_value=[]),
        poll_results=MagicMock(return_value=[]),
        get_cached=MagicMock(return_value=None),
        is_pending=MagicMock(return_value=False),
        is_loading=False,
        invalidate=MagicMock(),
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


# ── 初期状態 ──────────────────────────────────────────


class TestExtractPresenterDefaults:

    def test_defaults_disable_execution(self) -> None:
        view = _make_mock_view()
        ExtractPresenter(view)

        state = view.update_extract_ui.call_args[0][0]
        assert state.can_execute is False
        assert state.output_path_text == "抽出後PDFの保存先を選択してください"
        assert state.progress_text == "待機中"

    def test_has_active_session_false_initially(self) -> None:
        view = _make_mock_view()
        p = ExtractPresenter(view)
        assert p.has_active_session() is False

    def test_is_busy_false_initially(self) -> None:
        view = _make_mock_view()
        p = ExtractPresenter(view)
        assert p.is_busy() is False


# ── Source PDF 追加 ───────────────────────────────────


class TestAddSourcePdf:

    def test_add_pdf_files_updates_source_sections(self, sample_pdf: Path) -> None:
        view = _make_mock_view()
        view.ask_open_files.return_value = [str(sample_pdf)]
        p = ExtractPresenter(view)
        p._thumbnail_loader = _stub_thumbnail_loader(is_loading=True)
        view.reset_mock()

        p.add_pdf_files()

        state = view.update_extract_ui.call_args[0][0]
        assert len(state.source_sections) == 1
        assert state.source_sections[0].page_count == 10
        assert state.source_sections[0].filename == sample_pdf.name
        view.schedule.assert_called_once()

    def test_handle_dropped_paths_ignores_non_pdf(self, sample_pdf: Path, tmp_path: Path) -> None:
        view = _make_mock_view()
        p = ExtractPresenter(view)
        p._thumbnail_loader = _stub_thumbnail_loader(is_loading=False)
        txt_file = tmp_path / "notes.txt"
        txt_file.write_text("hello", encoding="utf-8")
        view.reset_mock()

        p.handle_dropped_paths([str(sample_pdf), str(txt_file)])

        state = view.update_extract_ui.call_args[0][0]
        assert len(state.source_sections) == 1
        view.show_info.assert_called_once()
        assert "PDF以外" in view.show_info.call_args[0][1]

    def test_duplicate_source_ignored(self, sample_pdf: Path) -> None:
        view = _make_mock_view()
        p = ExtractPresenter(view)
        p._thumbnail_loader = _stub_thumbnail_loader(is_loading=False)
        view.reset_mock()

        p.handle_dropped_paths([str(sample_pdf)])
        p.handle_dropped_paths([str(sample_pdf)])

        state = view.update_extract_ui.call_args[0][0]
        assert len(state.source_sections) == 1

    def test_add_blocked_while_running(self, sample_pdf: Path) -> None:
        view = _make_mock_view()
        p = ExtractPresenter(view)
        p._processor = SimpleNamespace(is_running=True, poll_results=MagicMock(return_value=[]))
        view.reset_mock()

        p.handle_dropped_paths([str(sample_pdf)])

        view.show_info.assert_called_once()
        assert "実行中" in view.show_info.call_args[0][0]


# ── Source 削除 ───────────────────────────────────────


class TestRemoveSource:

    def test_remove_selected_source_removes_document_and_target(self, sample_pdf: Path) -> None:
        view = _make_mock_view()
        p = ExtractPresenter(view)
        p._thumbnail_loader = _stub_thumbnail_loader(is_loading=False)
        p.handle_dropped_paths([str(sample_pdf)])

        doc = p._session.source_documents[0]
        ref = SourcePageRef(doc_id=doc.id, page_index=0)
        p._session.set_selected_source_pages([ref])
        p._session.add_to_target([ref])
        view.reset_mock()

        p.remove_selected_source()

        state = view.update_extract_ui.call_args[0][0]
        assert len(state.source_sections) == 0
        assert len(state.target_items) == 0

    def test_remove_no_selection_is_noop(self) -> None:
        view = _make_mock_view()
        p = ExtractPresenter(view)
        view.reset_mock()

        p.remove_selected_source()

        view.update_extract_ui.assert_not_called()


# ── Source 選択 ───────────────────────────────────────


class TestSourceSelection:

    def test_click_selects_single_page(self, sample_pdf: Path) -> None:
        view = _make_mock_view()
        p = ExtractPresenter(view)
        p._thumbnail_loader = _stub_thumbnail_loader(is_loading=False)
        p.handle_dropped_paths([str(sample_pdf)])
        doc = p._session.source_documents[0]
        view.reset_mock()

        event = SimpleNamespace(modifiers=MagicMock(return_value=MagicMock(__and__=lambda s, o: False)))
        # 修飾キーなしのクリック
        from PySide6.QtCore import Qt
        mock_event = MagicMock()
        mock_event.modifiers.return_value = Qt.KeyboardModifier.NoModifier
        p._on_source_page_clicked(doc.id, 3, mock_event)

        state = view.update_extract_ui.call_args[0][0]
        selected = [pg for sec in state.source_sections for pg in sec.pages if pg.is_selected]
        assert len(selected) == 1
        assert selected[0].page_index == 3

    def test_ctrl_click_toggles(self, sample_pdf: Path) -> None:
        view = _make_mock_view()
        p = ExtractPresenter(view)
        p._thumbnail_loader = _stub_thumbnail_loader(is_loading=False)
        p.handle_dropped_paths([str(sample_pdf)])
        doc = p._session.source_documents[0]

        from PySide6.QtCore import Qt
        ctrl_event = MagicMock()
        ctrl_event.modifiers.return_value = Qt.KeyboardModifier.ControlModifier

        p._on_source_page_clicked(doc.id, 0, ctrl_event)
        p._on_source_page_clicked(doc.id, 2, ctrl_event)
        assert len(p._session.selected_source_pages) == 2

        # Ctrl+Click same page → deselect
        p._on_source_page_clicked(doc.id, 0, ctrl_event)
        assert len(p._session.selected_source_pages) == 1
        assert p._session.selected_source_pages[0].page_index == 2

    def test_double_click_adds_to_target(self, sample_pdf: Path) -> None:
        view = _make_mock_view()
        p = ExtractPresenter(view)
        p._thumbnail_loader = _stub_thumbnail_loader(is_loading=False)
        p.handle_dropped_paths([str(sample_pdf)])
        doc = p._session.source_documents[0]
        view.reset_mock()

        p._on_source_page_double_clicked(doc.id, 5)

        state = view.update_extract_ui.call_args[0][0]
        assert len(state.target_items) == 1
        assert state.target_items[0].page_index == 5


# ── Target 操作 ───────────────────────────────────────


class TestTargetOperations:

    def _setup_with_target(self, sample_pdf: Path):
        """Source 追加 → 2 ページを Target に追加した状態を返す。"""
        view = _make_mock_view()
        p = ExtractPresenter(view)
        p._thumbnail_loader = _stub_thumbnail_loader(is_loading=False)
        p.handle_dropped_paths([str(sample_pdf)])
        doc = p._session.source_documents[0]
        refs = [
            SourcePageRef(doc_id=doc.id, page_index=0),
            SourcePageRef(doc_id=doc.id, page_index=1),
            SourcePageRef(doc_id=doc.id, page_index=2),
        ]
        p._session.add_to_target(refs)
        return view, p, doc

    def test_extract_selected_to_target(self, sample_pdf: Path) -> None:
        view = _make_mock_view()
        p = ExtractPresenter(view)
        p._thumbnail_loader = _stub_thumbnail_loader(is_loading=False)
        p.handle_dropped_paths([str(sample_pdf)])
        doc = p._session.source_documents[0]
        ref = SourcePageRef(doc_id=doc.id, page_index=4)
        p._session.set_selected_source_pages([ref])
        view.reset_mock()

        p.extract_selected_to_target()

        state = view.update_extract_ui.call_args[0][0]
        assert len(state.target_items) == 1
        assert state.target_items[0].page_index == 4

    def test_remove_selected_targets(self, sample_pdf: Path) -> None:
        view, p, doc = self._setup_with_target(sample_pdf)
        entry_id = p._session.target_entries[1].id
        p._session.set_selected_target_ids([entry_id])
        view.reset_mock()

        p.remove_selected_targets()

        state = view.update_extract_ui.call_args[0][0]
        assert len(state.target_items) == 2

    def test_clear_target(self, sample_pdf: Path) -> None:
        view, p, _ = self._setup_with_target(sample_pdf)
        view.reset_mock()

        p.clear_target()

        state = view.update_extract_ui.call_args[0][0]
        assert len(state.target_items) == 0

    def test_move_target_up(self, sample_pdf: Path) -> None:
        view, p, _ = self._setup_with_target(sample_pdf)
        last_id = p._session.target_entries[2].id
        p._session.set_selected_target_ids([last_id])
        view.reset_mock()

        p.move_target_up()

        state = view.update_extract_ui.call_args[0][0]
        assert state.target_items[1].entry_id == last_id

    def test_move_target_down(self, sample_pdf: Path) -> None:
        view, p, _ = self._setup_with_target(sample_pdf)
        first_id = p._session.target_entries[0].id
        p._session.set_selected_target_ids([first_id])
        view.reset_mock()

        p.move_target_down()

        state = view.update_extract_ui.call_args[0][0]
        assert state.target_items[1].entry_id == first_id

    def test_pages_dropped_from_source(self, sample_pdf: Path) -> None:
        view = _make_mock_view()
        p = ExtractPresenter(view)
        p._thumbnail_loader = _stub_thumbnail_loader(is_loading=False)
        p.handle_dropped_paths([str(sample_pdf)])
        doc = p._session.source_documents[0]
        view.reset_mock()

        p._on_pages_dropped_from_source([
            {"doc_id": doc.id, "page_index": 0},
            {"doc_id": doc.id, "page_index": 3},
        ])

        state = view.update_extract_ui.call_args[0][0]
        assert len(state.target_items) == 2

    def test_target_order_changed(self, sample_pdf: Path) -> None:
        view, p, _ = self._setup_with_target(sample_pdf)
        ids = [e.id for e in p._session.target_entries]
        reversed_ids = list(reversed(ids))
        view.reset_mock()

        p._on_target_order_changed(reversed_ids)

        state = view.update_extract_ui.call_args[0][0]
        assert [t.entry_id for t in state.target_items] == reversed_ids

    def test_target_blocked_while_running(self, sample_pdf: Path) -> None:
        view, p, _ = self._setup_with_target(sample_pdf)
        p._processor = SimpleNamespace(is_running=True, poll_results=MagicMock(return_value=[]))
        entry_id = p._session.target_entries[0].id
        p._session.set_selected_target_ids([entry_id])
        view.reset_mock()

        p.remove_selected_targets()
        view.show_info.assert_called_once()

        view.reset_mock()
        p.clear_target()
        view.show_info.assert_called_once()


# ── ズーム ────────────────────────────────────────────


class TestZoom:

    def test_source_zoom_in(self) -> None:
        view = _make_mock_view()
        p = ExtractPresenter(view)
        view.reset_mock()

        p.zoom_in_source()

        state = view.update_extract_ui.call_args[0][0]
        assert state.source_zoom_percent == 125

    def test_source_zoom_out(self) -> None:
        view = _make_mock_view()
        p = ExtractPresenter(view)
        view.reset_mock()

        p.zoom_out_source()

        state = view.update_extract_ui.call_args[0][0]
        assert state.source_zoom_percent == 75

    def test_source_zoom_reset(self) -> None:
        view = _make_mock_view()
        p = ExtractPresenter(view)
        p.zoom_in_source()
        p.zoom_in_source()
        view.reset_mock()

        p.reset_source_zoom()

        state = view.update_extract_ui.call_args[0][0]
        assert state.source_zoom_percent == 100

    def test_target_zoom_independent(self) -> None:
        view = _make_mock_view()
        p = ExtractPresenter(view)
        p.zoom_in_source()
        p.zoom_out_target()
        view.reset_mock()

        p._refresh_ui()

        state = view.update_extract_ui.call_args[0][0]
        assert state.source_zoom_percent == 125
        assert state.target_zoom_percent == 75


# ── 出力 / 実行 ──────────────────────────────────────


class TestExecution:

    def test_choose_output_enables_execution(self, sample_pdf: Path, tmp_path: Path) -> None:
        view = _make_mock_view()
        view.ask_save_file.return_value = str(tmp_path / "out.pdf")
        p = ExtractPresenter(view)
        p._thumbnail_loader = _stub_thumbnail_loader(is_loading=False)
        p.handle_dropped_paths([str(sample_pdf)])
        doc = p._session.source_documents[0]
        ref = SourcePageRef(doc_id=doc.id, page_index=0)
        p._session.add_to_target([ref])
        view.reset_mock()

        p.choose_output_file()

        state = view.update_extract_ui.call_args[0][0]
        assert state.output_path_text.endswith("out.pdf")
        assert state.can_execute is True

    def test_execute_validates_empty_target(self) -> None:
        view = _make_mock_view()
        p = ExtractPresenter(view)
        view.reset_mock()

        p.execute_extract()

        view.show_error.assert_called_once()
        assert "抽出対象" in view.show_error.call_args[0][1]

    def test_execute_validates_no_output_path(self, sample_pdf: Path) -> None:
        view = _make_mock_view()
        p = ExtractPresenter(view)
        p._thumbnail_loader = _stub_thumbnail_loader(is_loading=False)
        p.handle_dropped_paths([str(sample_pdf)])
        doc = p._session.source_documents[0]
        p._session.add_to_target([SourcePageRef(doc_id=doc.id, page_index=0)])
        view.reset_mock()

        p.execute_extract()

        view.show_error.assert_called_once()
        assert "保存先" in view.show_error.call_args[0][1]

    def test_execute_confirms_overwrite(self, sample_pdf: Path, tmp_path: Path) -> None:
        view = _make_mock_view()
        view.ask_yes_no.return_value = False
        p = ExtractPresenter(view)
        p._thumbnail_loader = _stub_thumbnail_loader(is_loading=False)
        p.handle_dropped_paths([str(sample_pdf)])
        doc = p._session.source_documents[0]
        p._session.add_to_target([SourcePageRef(doc_id=doc.id, page_index=0)])
        out = tmp_path / "exists.pdf"
        out.write_bytes(b"occupied")
        p._session.set_output_path(str(out))
        view.reset_mock()

        p.execute_extract()

        view.ask_yes_no.assert_called_once()
        view.schedule.assert_not_called()

    def test_execute_starts_processor_and_polling(self, sample_pdf: Path, tmp_path: Path) -> None:
        view = _make_mock_view()
        p = ExtractPresenter(view)
        p._thumbnail_loader = _stub_thumbnail_loader(is_loading=False)
        p.handle_dropped_paths([str(sample_pdf)])
        doc = p._session.source_documents[0]
        p._session.add_to_target([SourcePageRef(doc_id=doc.id, page_index=0)])
        p._session.set_output_path(str(tmp_path / "out.pdf"))
        fake_proc = SimpleNamespace(
            is_running=False,
            poll_results=MagicMock(return_value=[]),
            request_cancel=MagicMock(),
        )
        fake_proc.start_extract = MagicMock(
            side_effect=lambda *_args: setattr(fake_proc, "is_running", True),
        )
        p._processor = fake_proc
        view.reset_mock()

        p.execute_extract()

        fake_proc.start_extract.assert_called_once()
        view.schedule.assert_called_once()
        state = view.update_extract_ui.call_args[0][0]
        assert state.can_add_pdf is False
        assert "抽出中" in state.progress_text
        assert state.can_back_home is False


# ── ポーリング結果 ────────────────────────────────────


class TestPolling:

    def test_poll_extract_finished(self, sample_pdf: Path, tmp_path: Path) -> None:
        view = _make_mock_view()
        p = ExtractPresenter(view)
        p._session.begin_execution()
        p._processor = SimpleNamespace(
            is_running=False,
            poll_results=MagicMock(return_value=[
                {"type": "progress", "processed": 3, "total": 3},
                {"type": "finished", "processed": 3, "total": 3, "output_path": str(tmp_path / "out.pdf")},
            ]),
        )
        view.reset_mock()

        p._poll_extract_results()

        view.show_info.assert_called_once()
        assert "抽出完了" in view.show_info.call_args[0][0]
        assert "保存先:" in view.show_info.call_args[0][1]

    def test_poll_extract_failure(self) -> None:
        view = _make_mock_view()
        p = ExtractPresenter(view)
        p._session.begin_execution()
        p._processor = SimpleNamespace(
            is_running=False,
            poll_results=MagicMock(return_value=[
                {"type": "failure", "processed": 0, "total": 3, "message": "broken"},
            ]),
        )
        view.reset_mock()

        p._poll_extract_results()

        view.show_error.assert_called_once_with("抽出エラー", "broken")

    def test_poll_extract_cancelled(self) -> None:
        view = _make_mock_view()
        p = ExtractPresenter(view)
        p._session.begin_execution()
        p._processor = SimpleNamespace(
            is_running=False,
            poll_results=MagicMock(return_value=[
                {"type": "cancelled", "processed": 1, "total": 3, "message": "キャンセル"},
            ]),
        )
        view.reset_mock()

        p._poll_extract_results()

        view.show_info.assert_called_once()
        assert "キャンセル" in view.show_info.call_args[0][0]

    def test_poll_cancelled_closes_after_shutdown(self) -> None:
        view = _make_mock_view()
        p = ExtractPresenter(view)
        p._session.begin_execution()
        p._close_after_cancel = True
        p._processor = SimpleNamespace(
            is_running=False,
            poll_results=MagicMock(return_value=[
                {"type": "cancelled", "processed": 1, "total": 2, "message": "PDF抽出をキャンセルしました。"},
            ]),
        )
        view.reset_mock()

        p._poll_extract_results()

        view.destroy_window.assert_called_once()

    def test_poll_thumbnail_refreshes_ui(self, sample_pdf: Path) -> None:
        view = _make_mock_view()
        p = ExtractPresenter(view)
        p._thumbnail_loader = _stub_thumbnail_loader(
            poll_results=MagicMock(return_value=[
                SimpleNamespace(path=str(sample_pdf), page_index=0, status="ready", image_bytes=b"png"),
            ]),
            is_loading=False,
        )
        view.reset_mock()

        p._poll_thumbnail_results()

        view.update_extract_ui.assert_called()
        assert p._thumbnail_poll_job_id is None

    def test_thumbnail_poll_continues_while_loading(self) -> None:
        view = _make_mock_view()
        p = ExtractPresenter(view)
        p._thumbnail_loader = _stub_thumbnail_loader(
            poll_results=MagicMock(return_value=[]),
            is_loading=True,
        )
        view.reset_mock()

        p._poll_thumbnail_results()

        view.schedule.assert_called_once()

    def test_poll_progress_reschedules_if_running(self) -> None:
        view = _make_mock_view()
        p = ExtractPresenter(view)
        p._session.begin_execution()
        p._last_status = "running"
        p._processor = SimpleNamespace(
            is_running=True,
            poll_results=MagicMock(return_value=[
                {"type": "progress", "processed": 1, "total": 3},
            ]),
        )
        view.reset_mock()

        p._poll_extract_results()

        view.schedule.assert_called_once()
        state = view.update_extract_ui.call_args[0][0]
        assert "抽出中" in state.progress_text


# ── 終了制御 ──────────────────────────────────────────


class TestClosing:

    def test_on_closing_destroys_when_idle(self) -> None:
        view = _make_mock_view()
        p = ExtractPresenter(view)

        p.on_closing()

        view.destroy_window.assert_called_once()

    def test_on_closing_requests_cancel_while_busy(self) -> None:
        view = _make_mock_view()
        view.ask_ok_cancel.return_value = True
        p = ExtractPresenter(view)
        p._session.begin_execution()
        p._processor = SimpleNamespace(
            is_running=True,
            request_cancel=MagicMock(),
            poll_results=MagicMock(return_value=[]),
        )
        view.reset_mock()

        p.on_closing()

        p._processor.request_cancel.assert_called_once()
        view.destroy_window.assert_not_called()
        view.schedule.assert_called()

    def test_on_closing_aborted_if_user_declines(self) -> None:
        view = _make_mock_view()
        view.ask_ok_cancel.return_value = False
        p = ExtractPresenter(view)
        p._session.begin_execution()
        p._processor = SimpleNamespace(
            is_running=True,
            request_cancel=MagicMock(),
            poll_results=MagicMock(return_value=[]),
        )
        view.reset_mock()

        p.on_closing()

        p._processor.request_cancel.assert_not_called()
        view.destroy_window.assert_not_called()


# ── UI 状態の一貫性 ──────────────────────────────────


class TestUiStateConsistency:

    def test_runtime_feedback_reset_on_input_change(self, sample_pdf: Path) -> None:
        view = _make_mock_view()
        p = ExtractPresenter(view)
        p._last_status = "finished"
        p._last_progress_total = 5
        p._thumbnail_loader = _stub_thumbnail_loader(is_loading=False)
        view.reset_mock()

        p.handle_dropped_paths([str(sample_pdf)])

        state = view.update_extract_ui.call_args[0][0]
        assert state.progress_text == "待機中"

    def test_has_active_session_true_after_source_added(self, sample_pdf: Path) -> None:
        view = _make_mock_view()
        p = ExtractPresenter(view)
        p._thumbnail_loader = _stub_thumbnail_loader(is_loading=False)
        p.handle_dropped_paths([str(sample_pdf)])

        assert p.has_active_session() is True

    def test_move_buttons_state(self, sample_pdf: Path) -> None:
        view = _make_mock_view()
        p = ExtractPresenter(view)
        p._thumbnail_loader = _stub_thumbnail_loader(is_loading=False)
        p.handle_dropped_paths([str(sample_pdf)])
        doc = p._session.source_documents[0]
        refs = [SourcePageRef(doc_id=doc.id, page_index=i) for i in range(3)]
        p._session.add_to_target(refs)

        # 先頭選択 → up 不可, down 可
        p._session.set_selected_target_ids([p._session.target_entries[0].id])
        view.reset_mock()
        p._refresh_ui()
        state = view.update_extract_ui.call_args[0][0]
        assert state.can_move_up is False
        assert state.can_move_down is True

        # 末尾選択 → up 可, down 不可
        p._session.set_selected_target_ids([p._session.target_entries[2].id])
        view.reset_mock()
        p._refresh_ui()
        state = view.update_extract_ui.call_args[0][0]
        assert state.can_move_up is True
        assert state.can_move_down is False

    def test_thumbnail_status_in_ui_state(self, sample_pdf: Path) -> None:
        view = _make_mock_view()
        p = ExtractPresenter(view)
        p._thumbnail_loader = _stub_thumbnail_loader(
            get_cached=MagicMock(return_value=SimpleNamespace(
                status="ready", image_bytes=b"thumb",
            )),
            is_loading=False,
        )
        p.handle_dropped_paths([str(sample_pdf)])
        view.reset_mock()
        p._refresh_ui()

        state = view.update_extract_ui.call_args[0][0]
        page = state.source_sections[0].pages[0]
        assert page.thumbnail_status == "ready"
        assert page.thumbnail_png_bytes == b"thumb"
