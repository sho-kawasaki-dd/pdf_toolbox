from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from presenter.pdf_to_jpeg_presenter import PdfToJpegPresenter


def _make_mock_view() -> MagicMock:
    view = MagicMock()
    view.ask_open_file.return_value = None
    view.ask_directory.return_value = None
    view.ask_yes_no.return_value = True
    view.ask_ok_cancel.return_value = False
    view.schedule.return_value = "timer_1"
    view.get_pdf_to_jpeg_preview_size.return_value = (320, 420)
    return view


class TestPdfToJpegPresenter:

    def test_defaults_disable_execution(self) -> None:
        view = _make_mock_view()
        PdfToJpegPresenter(view)

        state = view.update_pdf_to_jpeg_ui.call_args[0][0]
        assert state.can_execute is False
        assert state.has_preview is False
        assert "白背景" in state.note_text

    def test_choose_pdf_file_loads_preview(self, sample_pdf: Path) -> None:
        view = _make_mock_view()
        view.ask_open_file.return_value = str(sample_pdf)
        presenter = PdfToJpegPresenter(view)
        view.reset_mock()

        presenter.choose_pdf_file()

        state = view.update_pdf_to_jpeg_ui.call_args[0][0]
        assert state.has_input_pdf is True
        assert state.has_preview is True
        assert sample_pdf.name in state.selected_pdf_text

    def test_execute_conversion_validates_required_input_and_output(self, sample_pdf: Path, tmp_path: Path) -> None:
        view = _make_mock_view()
        presenter = PdfToJpegPresenter(view)

        presenter.execute_conversion()
        view.show_error.assert_called_once()
        assert "変換対象のPDF" in view.show_error.call_args[0][1]

        view.reset_mock()
        presenter._session.set_input_pdf(str(sample_pdf))
        presenter._preview_document.open(str(sample_pdf))

        presenter.execute_conversion()
        view.show_error.assert_called_once()
        assert "保存先フォルダ" in view.show_error.call_args[0][1]

        presenter._preview_document.close()

    def test_execute_conversion_confirms_overwrite_before_start(self, sample_pdf: Path, tmp_path: Path) -> None:
        view = _make_mock_view()
        view.ask_yes_no.return_value = False
        presenter = PdfToJpegPresenter(view)
        presenter._session.set_input_pdf(str(sample_pdf))
        presenter._session.set_output_dir(str(tmp_path / "output"))
        presenter._preview_document.open(str(sample_pdf))
        output_dir = tmp_path / "output" / sample_pdf.stem
        output_dir.mkdir(parents=True)
        (output_dir / f"{sample_pdf.stem}_001.jpg").write_bytes(b"occupied")
        presenter._processor.start_conversion = MagicMock()
        view.reset_mock()

        presenter.execute_conversion()

        view.ask_yes_no.assert_called_once()
        presenter._processor.start_conversion.assert_not_called()
        presenter._preview_document.close()

    def test_execute_conversion_starts_after_overwrite_approval(self, sample_pdf: Path, tmp_path: Path) -> None:
        view = _make_mock_view()
        presenter = PdfToJpegPresenter(view)
        presenter._session.set_input_pdf(str(sample_pdf))
        presenter._session.set_output_dir(str(tmp_path / "output"))
        presenter._preview_document.open(str(sample_pdf))
        output_dir = tmp_path / "output" / sample_pdf.stem
        output_dir.mkdir(parents=True)
        (output_dir / f"{sample_pdf.stem}_001.jpg").write_bytes(b"occupied")

        def fake_start(_session, overwrite=False) -> None:
            presenter._processor.is_converting = True
            presenter._session.begin_batch(1)
            presenter._session.mark_page_started(1)

        presenter._processor.start_conversion = MagicMock(side_effect=fake_start)
        view.reset_mock()

        presenter.execute_conversion()

        presenter._processor.start_conversion.assert_called_once_with(presenter._session, overwrite=True)
        view.schedule.assert_called_once()
        state = view.update_pdf_to_jpeg_ui.call_args[0][0]
        assert state.is_running is True
        assert "変換中" in state.progress_text
        presenter._preview_document.close()

    def test_poll_results_shows_completion_message(self, tmp_path: Path) -> None:
        view = _make_mock_view()
        presenter = PdfToJpegPresenter(view)
        presenter._session.set_input_pdf("C:/sample.pdf")
        presenter._session.set_output_dir(str(tmp_path / "output"))
        presenter._session.begin_batch(2)
        presenter._session.mark_page_started(2)
        presenter._session.record_success()
        presenter._session.record_success()
        presenter._processor.is_converting = False
        presenter._processor.poll_results = MagicMock(return_value=[
            {"type": "finished", "success_count": 2, "failure_count": 0, "output_dir": str(tmp_path / "output" / "sample")},
        ])

        presenter._poll_results()

        view.show_info.assert_called_once()
        assert "成功: 2ページ" in view.show_info.call_args[0][1]
        assert "出力先:" in view.show_info.call_args[0][1]

    def test_poll_results_reschedules_while_running(self) -> None:
        view = _make_mock_view()
        presenter = PdfToJpegPresenter(view)
        presenter._processor.is_converting = True
        presenter._processor.poll_results = MagicMock(return_value=[
            {"type": "progress", "processed_pages": 1, "total_pages": 3, "current_page_number": 2},
        ])
        presenter._session.begin_batch(3)
        presenter._session.mark_page_started(2)
        presenter._session.record_success()
        view.reset_mock()

        presenter._poll_results()

        view.schedule.assert_called_once()
        view.show_info.assert_not_called()

    def test_on_closing_requires_confirmation_while_busy(self) -> None:
        view = _make_mock_view()
        view.ask_ok_cancel.return_value = False
        presenter = PdfToJpegPresenter(view)
        presenter._processor.is_converting = True

        presenter.on_closing()

        view.ask_ok_cancel.assert_called_once()
        view.destroy_window.assert_not_called()