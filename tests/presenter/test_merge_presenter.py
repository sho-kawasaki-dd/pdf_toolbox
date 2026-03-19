from __future__ import annotations

from types import SimpleNamespace
from pathlib import Path
from unittest.mock import MagicMock

from presenter.merge_presenter import MergePresenter


def _make_mock_view() -> MagicMock:
    view = MagicMock()
    view.ask_open_files.return_value = []
    view.ask_save_file.return_value = None
    view.ask_ok_cancel.return_value = False
    view.ask_yes_no.return_value = True
    view.schedule.return_value = "timer_1"
    return view


class TestMergePresenter:

    def test_defaults_disable_execution(self) -> None:
        view = _make_mock_view()
        MergePresenter(view)

        state = view.update_merge_ui.call_args[0][0]
        assert state.can_execute is False
        assert state.output_path_text == "結合後PDFの保存先を選択してください"

    def test_add_pdf_files_updates_input_list(self, sample_pdf: Path) -> None:
        view = _make_mock_view()
        view.ask_open_files.return_value = [str(sample_pdf)]
        presenter = MergePresenter(view)
        presenter._thumbnail_loader = SimpleNamespace(
            request_thumbnails=MagicMock(return_value=[str(sample_pdf)]),
            is_loading=True,
            get_cached_result=MagicMock(return_value=None),
            is_pending=MagicMock(return_value=True),
            poll_results=MagicMock(return_value=[]),
        )
        view.reset_mock()

        presenter.add_pdf_files()

        state = view.update_merge_ui.call_args[0][0]
        assert len(state.input_items) == 1
        assert state.input_items[0].title == sample_pdf.name
        assert state.input_items[0].thumbnail_status == "loading"
        view.schedule.assert_called_once()

    def test_handle_dropped_paths_ignores_unsupported_inputs(self, sample_pdf: Path, tmp_path: Path) -> None:
        view = _make_mock_view()
        unsupported = tmp_path / "notes.txt"
        unsupported.write_text("ignore", encoding="utf-8")
        presenter = MergePresenter(view)
        presenter._thumbnail_loader = SimpleNamespace(
            request_thumbnails=MagicMock(return_value=[str(sample_pdf)]),
            is_loading=False,
            get_cached_result=MagicMock(return_value=None),
            is_pending=MagicMock(return_value=False),
            poll_results=MagicMock(return_value=[]),
        )
        view.reset_mock()

        presenter.handle_dropped_paths([str(sample_pdf), str(unsupported)])

        state = view.update_merge_ui.call_args[0][0]
        assert len(state.input_items) == 1
        assert state.input_items[0].path == str(sample_pdf)
        view.show_info.assert_called_once()
        assert "PDF 以外" in view.show_info.call_args[0][1]

    def test_poll_thumbnail_results_refreshes_ui_after_loader_completion(self, sample_pdf: Path) -> None:
        view = _make_mock_view()
        presenter = MergePresenter(view)
        presenter._session.add_inputs([str(sample_pdf)])
        presenter._thumbnail_loader = SimpleNamespace(
            poll_results=MagicMock(return_value=[
                SimpleNamespace(path=str(sample_pdf), status="ready", image_bytes=b"png", error_message=None),
            ]),
            get_cached_result=MagicMock(
                return_value=SimpleNamespace(path=str(sample_pdf), status="ready", image_bytes=b"png", error_message=None),
            ),
            is_loading=False,
            is_pending=MagicMock(return_value=False),
            request_thumbnails=MagicMock(return_value=[]),
        )
        view.reset_mock()

        presenter._poll_thumbnail_results()

        state = view.update_merge_ui.call_args[0][0]
        assert state.input_items[0].thumbnail_status == "ready"
        assert state.input_items[0].thumbnail_png_bytes == b"png"

    def test_remove_selected_inputs_keeps_remaining_thumbnail_state(self, sample_pdf: Path, tmp_path: Path) -> None:
        second = tmp_path / "second.pdf"
        second.write_bytes(sample_pdf.read_bytes())
        view = _make_mock_view()
        presenter = MergePresenter(view)
        presenter._session.add_inputs([str(sample_pdf), str(second)])
        presenter._thumbnail_loader = SimpleNamespace(
            get_cached_result=MagicMock(
                side_effect=lambda path: SimpleNamespace(path=path, status="ready", image_bytes=path.encode("utf-8"), error_message=None),
            ),
            is_pending=MagicMock(return_value=False),
            is_loading=False,
            request_thumbnails=MagicMock(return_value=[]),
            poll_results=MagicMock(return_value=[]),
        )
        presenter.set_selected_inputs([str(sample_pdf)])
        view.reset_mock()

        presenter.remove_selected_inputs()

        state = view.update_merge_ui.call_args[0][0]
        assert [item.path for item in state.input_items] == [str(second)]
        assert state.input_items[0].thumbnail_png_bytes == str(second).encode("utf-8")

    def test_choose_output_file_enables_execution_when_inputs_exist(self, sample_pdf: Path, tmp_path: Path) -> None:
        view = _make_mock_view()
        view.ask_save_file.return_value = str(tmp_path / "merged.pdf")
        presenter = MergePresenter(view)
        presenter._session.add_inputs([str(sample_pdf)])
        view.reset_mock()

        presenter.choose_output_file()

        state = view.update_merge_ui.call_args[0][0]
        assert state.output_path_text.endswith("merged.pdf")
        assert state.can_execute is True

    def test_execute_merge_starts_processor_and_polling(self, sample_pdf: Path, tmp_path: Path) -> None:
        view = _make_mock_view()
        presenter = MergePresenter(view)
        presenter._session.add_inputs([str(sample_pdf)])
        presenter._session.set_output_path(str(tmp_path / "merged.pdf"))
        fake_processor = SimpleNamespace(
            is_merging=False,
            poll_results=MagicMock(return_value=[]),
            request_cancel=MagicMock(),
        )
        fake_processor.start_merge = MagicMock(side_effect=lambda *_args: setattr(fake_processor, "is_merging", True))
        presenter._merge_processor = fake_processor
        view.reset_mock()

        presenter.execute_merge()

        presenter._merge_processor.start_merge.assert_called_once()
        view.schedule.assert_called_once()
        state = view.update_merge_ui.call_args[0][0]
        assert state.can_add_inputs is False
        assert "準備" in state.progress_text
        assert state.progress_value == 0
        assert state.can_back_home is False

    def test_poll_merge_results_updates_progress_value(self) -> None:
        view = _make_mock_view()
        presenter = MergePresenter(view)
        presenter._session.begin_execution()
        presenter._last_status = "running"
        presenter._merge_processor = SimpleNamespace(
            is_merging=True,
            poll_results=MagicMock(return_value=[
                {"type": "progress", "processed_items": 0, "total_items": 1, "processed_pages": 1, "total_pages": 4},
            ]),
        )
        view.schedule.return_value = "timer_2"
        view.reset_mock()

        presenter._poll_merge_results()

        state = view.update_merge_ui.call_args[0][0]
        assert state.progress_text == "結合中: 1 / 4 ページ"
        assert state.progress_value == 25
        view.schedule.assert_called_once()

    def test_set_selected_inputs_updates_move_buttons(self, sample_pdf: Path, tmp_path: Path) -> None:
        second = tmp_path / "second.pdf"
        second.write_bytes(sample_pdf.read_bytes())
        view = _make_mock_view()
        presenter = MergePresenter(view)
        presenter._session.add_inputs([str(sample_pdf), str(second)])
        view.reset_mock()

        presenter.set_selected_inputs([str(second)])

        state = view.update_merge_ui.call_args[0][0]
        assert state.can_move_up is True
        assert state.can_move_down is False

    def test_execute_merge_validates_required_inputs(self, tmp_path: Path) -> None:
        view = _make_mock_view()
        presenter = MergePresenter(view)

        presenter.execute_merge()
        view.show_error.assert_called_once()
        assert "結合対象のPDF" in view.show_error.call_args[0][1]

        view.reset_mock()
        sample_path = tmp_path / "sample.pdf"
        sample_path.write_bytes(b"%PDF-1.4\n")
        presenter._session.add_inputs([str(sample_path)])

        presenter.execute_merge()
        assert "保存先" in view.show_error.call_args[0][1]

    def test_execute_merge_confirms_overwrite(self, sample_pdf: Path, tmp_path: Path) -> None:
        view = _make_mock_view()
        view.ask_yes_no.return_value = False
        presenter = MergePresenter(view)
        presenter._session.add_inputs([str(sample_pdf)])
        output_path = tmp_path / "merged.pdf"
        output_path.write_bytes(b"occupied")
        presenter._session.set_output_path(str(output_path))
        view.reset_mock()

        presenter.execute_merge()

        view.ask_yes_no.assert_called_once()
        view.schedule.assert_not_called()

    def test_poll_merge_results_shows_completion_summary(self, sample_pdf: Path, tmp_path: Path) -> None:
        view = _make_mock_view()
        view.schedule.side_effect = lambda _ms, callback: callback() or "timer_1"
        presenter = MergePresenter(view)
        presenter._session.add_inputs([str(sample_pdf)])
        presenter._session.begin_execution()
        presenter._merge_processor = SimpleNamespace(
            is_merging=False,
            poll_results=MagicMock(return_value=[
                {"type": "progress", "processed_items": 0, "total_items": 1, "processed_pages": 1, "total_pages": 10},
                {"type": "finished", "processed_items": 1, "total_items": 1, "processed_pages": 10, "total_pages": 10, "output_path": str(tmp_path / "merged.pdf")},
            ]),
        )
        view.reset_mock()

        presenter._poll_merge_results()

        view.show_info.assert_called_once()
        assert "保存先:" in view.show_info.call_args[0][1]
        state = view.update_merge_ui.call_args[0][0]
        assert state.progress_value == 100

    def test_poll_merge_results_shows_error(self) -> None:
        view = _make_mock_view()
        view.schedule.side_effect = lambda _ms, callback: callback() or "timer_1"
        presenter = MergePresenter(view)
        presenter._session.begin_execution()
        presenter._merge_processor = SimpleNamespace(
            is_merging=False,
            poll_results=MagicMock(return_value=[
                {"type": "failure", "processed_items": 0, "total_items": 1, "processed_pages": 0, "total_pages": 10, "message": "broken"},
            ]),
        )
        view.reset_mock()

        presenter._poll_merge_results()

        view.show_error.assert_called_once_with("結合エラー", "broken")

    def test_input_edit_resets_stale_completion_state(self, sample_pdf: Path, tmp_path: Path) -> None:
        view = _make_mock_view()
        presenter = MergePresenter(view)
        presenter._last_status = "finished"
        presenter._last_progress_total = 2
        presenter._last_finished_output = str(tmp_path / "merged.pdf")
        presenter._thumbnail_loader = SimpleNamespace(
            request_thumbnails=MagicMock(return_value=[str(sample_pdf)]),
            is_loading=False,
            get_cached_result=MagicMock(return_value=None),
            is_pending=MagicMock(return_value=False),
            poll_results=MagicMock(return_value=[]),
        )
        view.reset_mock()

        presenter.handle_dropped_paths([str(sample_pdf)])

        state = view.update_merge_ui.call_args[0][0]
        assert state.progress_text == "待機中"

    def test_poll_merge_results_closes_window_after_cancelled_shutdown(self) -> None:
        view = _make_mock_view()
        presenter = MergePresenter(view)
        presenter._session.begin_execution()
        presenter._close_after_cancel = True
        presenter._merge_processor = SimpleNamespace(
            is_merging=False,
            poll_results=MagicMock(return_value=[
                {"type": "cancelled", "processed_items": 1, "total_items": 2, "message": "PDF結合をキャンセルしました。"},
            ]),
        )
        view.reset_mock()

        presenter._poll_merge_results()

        view.cancel_schedule.assert_not_called()
        view.destroy_window.assert_called_once()

    def test_reorder_inputs_while_running_shows_info(self) -> None:
        view = _make_mock_view()
        presenter = MergePresenter(view)
        presenter._session.begin_execution()
        presenter._merge_processor = SimpleNamespace(is_merging=True)

        presenter.reorder_inputs(["C:/one.pdf"])

        view.show_info.assert_called_once()

    def test_on_closing_destroys_window_when_idle(self) -> None:
        view = _make_mock_view()
        presenter = MergePresenter(view)

        presenter.on_closing()

        view.destroy_window.assert_called_once()

    def test_on_closing_requests_cancel_while_busy(self) -> None:
        view = _make_mock_view()
        view.ask_ok_cancel.return_value = True
        presenter = MergePresenter(view)
        presenter._session.begin_execution()
        presenter._merge_processor = SimpleNamespace(
            is_merging=True,
            request_cancel=MagicMock(),
            poll_results=MagicMock(return_value=[]),
        )
        view.reset_mock()

        presenter.on_closing()

        presenter._merge_processor.request_cancel.assert_called_once()
        view.destroy_window.assert_not_called()
        state = view.update_merge_ui.call_args[0][0]
        assert "キャンセル中" in state.progress_text