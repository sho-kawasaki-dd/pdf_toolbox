from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from presenter.compress_presenter import CompressionPresenter


def _make_mock_view() -> MagicMock:
    view = MagicMock()
    view.ask_open_files.return_value = []
    view.ask_directory.return_value = None
    view.get_selected_compression_inputs.return_value = []
    view.ask_ok_cancel.return_value = False
    view.schedule.return_value = "timer_1"
    return view


class TestCompressionPresenter:

    def test_defaults_match_phase_requirements(self) -> None:
        view = _make_mock_view()
        CompressionPresenter(view)

        state = view.update_compression_ui.call_args[0][0]
        assert state.jpeg_quality == 75
        assert state.png_quality == 75
        assert state.clean_metadata is False
        assert state.can_execute is False

    def test_add_pdf_files_updates_input_list(self, sample_pdf: Path) -> None:
        view = _make_mock_view()
        view.ask_open_files.return_value = [str(sample_pdf)]
        presenter = CompressionPresenter(view)
        view.reset_mock()

        presenter.add_pdf_files()

        state = view.update_compression_ui.call_args[0][0]
        assert len(state.input_items) == 1
        assert "sample.pdf" in state.input_items[0].label
        assert state.can_clear_inputs is True

    def test_execute_compression_starts_processor_and_polling(self, sample_pdf: Path, tmp_path: Path) -> None:
        view = _make_mock_view()
        presenter = CompressionPresenter(view)
        presenter._session.add_input(str(sample_pdf))
        presenter._session.set_output_dir(str(tmp_path / "out"))

        def fake_start(session) -> None:
            presenter._processor.is_compressing = True
            session.begin_batch(1)

        presenter._processor.start_compression = MagicMock(side_effect=fake_start)
        view.reset_mock()

        presenter.execute_compression()

        presenter._processor.start_compression.assert_called_once()
        view.schedule.assert_called_once()
        state = view.update_compression_ui.call_args[0][0]
        assert state.can_execute is False
        assert presenter.is_busy() is True

    def test_poll_results_shows_completion_summary(self) -> None:
        view = _make_mock_view()
        presenter = CompressionPresenter(view)
        presenter._session.begin_batch(2)
        presenter._session.record_success()
        presenter._session.record_skip()
        presenter._processor.is_compressing = False
        presenter._processor.poll_results = MagicMock(return_value=[
            {
                "type": "success",
                "item": "ok.pdf",
                "output_path": "out/ok.pdf",
                "message": "ok",
                "input_bytes": 1_000,
                "lossy_output_bytes": 700,
                "final_output_bytes": 650,
            },
            {"type": "skipped", "item": "skip.pdf", "reason": "invalid pdf"},
            {"type": "finished", "success_count": 1, "failure_count": 0, "skip_count": 1},
        ])

        presenter._poll_compression_results()

        view.show_info.assert_called_once()
        assert "成功: 1件" in view.show_info.call_args[0][1]
        assert "スキップ: 1件" in view.show_info.call_args[0][1]
        assert "元PDF総容量: 1000.0 B" in view.show_info.call_args[0][1]
        assert "圧縮後総容量: 650.0 B" in view.show_info.call_args[0][1]
        assert "全体圧縮率: 35.0%" in view.show_info.call_args[0][1]
        assert "非可逆圧縮率: 30.0%" in view.show_info.call_args[0][1]
        assert "可逆圧縮率: 5.0%" in view.show_info.call_args[0][1]

    def test_on_closing_requires_confirmation_while_busy(self) -> None:
        view = _make_mock_view()
        view.ask_ok_cancel.return_value = False
        presenter = CompressionPresenter(view)
        presenter._processor.is_compressing = True

        presenter.on_closing()

        view.ask_ok_cancel.assert_called_once()
        view.destroy_window.assert_not_called()

    def test_handle_dropped_paths_ignores_unsupported_inputs(self, sample_pdf: Path, tmp_path: Path) -> None:
        view = _make_mock_view()
        unsupported = tmp_path / "notes.txt"
        unsupported.write_text("ignore", encoding="utf-8")
        presenter = CompressionPresenter(view)
        view.reset_mock()

        presenter.handle_dropped_paths([str(sample_pdf), str(unsupported)])

        state = view.update_compression_ui.call_args[0][0]
        assert len(state.input_items) == 1
        assert sample_pdf.name in state.input_items[0].label
        view.show_info.assert_called_once()
        assert "PDF / フォルダ / ZIP 以外" in view.show_info.call_args[0][1]

    def test_choose_output_directory_updates_ui_state(self, tmp_path: Path) -> None:
        view = _make_mock_view()
        view.ask_directory.return_value = str(tmp_path / "exports")
        presenter = CompressionPresenter(view)
        view.reset_mock()

        presenter.choose_output_directory()

        state = view.update_compression_ui.call_args[0][0]
        assert state.output_dir_text.endswith("exports")

    def test_poll_results_reschedules_while_worker_is_still_running(self) -> None:
        view = _make_mock_view()
        presenter = CompressionPresenter(view)
        presenter._processor.is_compressing = True
        presenter._processor.poll_results = MagicMock(return_value=[
            {"type": "failure", "item": "bad.pdf", "message": "broken"},
        ])
        view.reset_mock()

        presenter._poll_compression_results()

        view.schedule.assert_called_once()
        view.show_error.assert_not_called()
        assert presenter._recent_failures[0]["message"] == "broken"

    def test_on_closing_destroys_window_after_confirmation(self) -> None:
        view = _make_mock_view()
        view.ask_ok_cancel.return_value = True
        presenter = CompressionPresenter(view)
        presenter._processor.is_compressing = True
        presenter._poll_job_id = "timer_1"

        presenter.on_closing()

        view.cancel_schedule.assert_called_once_with("timer_1")
        view.destroy_window.assert_called_once()
