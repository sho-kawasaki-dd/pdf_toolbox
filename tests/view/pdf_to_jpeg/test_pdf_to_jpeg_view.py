from __future__ import annotations

import fitz
from pathlib import Path

from view.pdf_to_jpeg.pdf_to_jpeg_view import PdfToJpegUiState, PdfToJpegView


class TestPdfToJpegView:

    def test_can_instantiate(self, qtbot) -> None:
        view = PdfToJpegView()
        qtbot.addWidget(view)

        assert view is not None

    def test_set_presenter_wires_main_actions(self, qtbot) -> None:
        class PresenterStub:
            def __init__(self) -> None:
                self.choose_pdf_file_called = 0
                self.choose_output_directory_called = 0
                self.execute_conversion_called = 0
                self.quality_values: list[int] = []

            def choose_pdf_file(self) -> None:
                self.choose_pdf_file_called += 1

            def choose_output_directory(self) -> None:
                self.choose_output_directory_called += 1

            def execute_conversion(self) -> None:
                self.execute_conversion_called += 1

            def set_jpeg_quality(self, value: int) -> None:
                self.quality_values.append(value)

            def handle_dropped_paths(self, _paths: list[str]) -> None:
                return None

        view = PdfToJpegView()
        qtbot.addWidget(view)
        presenter = PresenterStub()

        view.set_presenter(presenter)
        view.btn_choose_pdf.click()
        view.btn_choose_output.click()
        view.btn_execute.click()
        view.sld_jpeg_quality.setValue(82)

        assert presenter.choose_pdf_file_called == 1
        assert presenter.choose_output_directory_called == 1
        assert presenter.execute_conversion_called == 1
        assert presenter.quality_values[-1] == 82

    def test_update_ui_shows_preview_and_progress(self, qtbot, sample_pdf: Path) -> None:
        view = PdfToJpegView()
        qtbot.addWidget(view)

        with fitz.open(str(sample_pdf)) as document:
            pixmap = document.load_page(0).get_pixmap(matrix=fitz.Matrix(0.15, 0.15), alpha=False)
        png_bytes = pixmap.tobytes("png")

        state = PdfToJpegUiState(
            selected_pdf_text=str(sample_pdf),
            output_dir_text="C:/out",
            output_detail_text="出力先サブフォルダ: C:/out/sample",
            progress_text="変換中: 1 / 10 ページ (現在: 2ページ目)",
            summary_text="成功: 1ページ / 失敗: 0ページ",
            progress_value=10,
            preview_png_bytes=png_bytes,
            preview_text="",
            has_input_pdf=True,
            has_output_dir=True,
            has_preview=True,
            can_execute=True,
        )

        view.update_ui(state)

        assert view.txt_selected_pdf.text() == str(sample_pdf)
        assert view.txt_output_dir.text() == "C:/out"
        assert view.lbl_output_detail.text() == "出力先サブフォルダ: C:/out/sample"
        assert view.progress_bar.value() == 10
        assert view.btn_execute.isEnabled() is True
        assert view.preview_label.pixmap() is not None
        assert not view.preview_label.pixmap().isNull()

    def test_update_ui_disables_buttons_while_running(self, qtbot) -> None:
        view = PdfToJpegView()
        qtbot.addWidget(view)

        state = PdfToJpegUiState(
            can_choose_pdf=False,
            can_choose_output=False,
            can_execute=False,
            can_edit_quality=False,
            can_back_home=False,
            is_running=True,
            progress_text="変換中: 0 / 3 ページ (現在: 1ページ目)",
        )

        view.update_ui(state)

        assert view.btn_choose_pdf.isEnabled() is False
        assert view.btn_choose_output.isEnabled() is False
        assert view.btn_execute.isEnabled() is False
        assert view.btn_back_home.isEnabled() is False
        assert view.sld_jpeg_quality.isEnabled() is False

    def test_get_preview_size_returns_positive_dimensions(self, qtbot) -> None:
        view = PdfToJpegView()
        qtbot.addWidget(view)

        width, height = view.get_preview_size()

        assert width > 0
        assert height > 0