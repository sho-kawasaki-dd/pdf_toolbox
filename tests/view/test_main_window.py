"""MainWindow の基本テスト (Step 1.2)。

インスタンス化・UiState デフォルト値・no-op スタブメソッドの呼び出しを検証する。
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock
from PIL import Image
from PySide6.QtWidgets import QFileDialog, QMessageBox, QFrame

from view.compress.compress_view import CompressionInputItem, CompressionUiState
from view.flatten.flatten_view import FlattenInputItem, FlattenUiState
from view.merge.merge_view import MergeInputItem, MergeUiState
from view.pdf_to_jpeg.pdf_to_jpeg_view import PdfToJpegUiState
from view.main_window import MainWindow, UiState


class TestUiStateDefaults:

    def test_default_page_info(self):
        state = UiState()
        assert state.page_info_text == "0 / 0"
        assert state.zoom_info_text == "倍率: 100%"

    def test_default_split_bar(self):
        state = UiState()
        assert state.total_pages == 0
        assert state.current_page == 0
        assert state.split_points == []
        assert state.active_section_index == -1

    def test_default_section_info(self):
        state = UiState()
        assert state.section_info_text == "- / -"
        assert state.section_range_text == "ページ範囲: -"
        assert state.section_color == "gray"
        assert state.section_filename == ""

    def test_default_button_states(self):
        state = UiState()
        assert state.can_open is True
        assert state.can_prev is False
        assert state.can_next is False
        assert state.can_execute is False


class TestMainWindowInstantiation:

    def test_can_instantiate(self, qtbot):
        win = MainWindow()
        qtbot.addWidget(win)
        assert win.windowTitle() == "PDF ツールボックス"

    def test_starts_on_home_screen(self, qtbot):
        win = MainWindow()
        qtbot.addWidget(win)
        assert win.stack.currentWidget() is win.home_view

    def test_can_show_compress_screen(self, qtbot):
        win = MainWindow()
        qtbot.addWidget(win)

        win.show_compress()

        assert win.stack.currentWidget() is win.compress_view

    def test_can_show_merge_screen(self, qtbot):
        win = MainWindow()
        qtbot.addWidget(win)

        win.show_merge()

        assert win.stack.currentWidget() is win.merge_view

    def test_can_show_pdf_to_jpeg_screen(self, qtbot):
        win = MainWindow()
        qtbot.addWidget(win)

        win.show_pdf_to_jpeg()

        assert win.stack.currentWidget() is win.pdf_to_jpeg_view

    def test_can_show_flatten_screen(self, qtbot):
        win = MainWindow()
        qtbot.addWidget(win)

        win.show_flatten()

        assert win.stack.currentWidget() is win.flatten_view

    def test_initial_size(self, qtbot):
        win = MainWindow()
        qtbot.addWidget(win)
        assert win.width() >= 500
        assert win.height() >= 400

    def test_has_left_right_divider(self, qtbot):
        win = MainWindow()
        qtbot.addWidget(win)
        assert win.pane_divider.frameShape() == QFrame.Shape.VLine


class TestMainWindowStubs:
    """no-op スタブがエラーなく呼べることを検証する。"""

    def test_set_presenter(self, qtbot):
        win = MainWindow()
        qtbot.addWidget(win)
        mock_presenter = MagicMock()
        win.set_presenter(mock_presenter)

    def test_update_ui(self, qtbot):
        win = MainWindow()
        qtbot.addWidget(win)
        win.update_ui(UiState())

    def test_update_ui_sets_nav_bar(self, qtbot):
        """update_ui が NavigationBar にページ情報を反映する。"""
        win = MainWindow()
        qtbot.addWidget(win)
        state = UiState(page_info_text="3 / 10", can_prev=True, can_next=True)
        win.update_ui(state)
        assert win.nav_bar.lbl_page_info.text() == "3 / 10"
        assert win.nav_bar.btn_prev.isEnabled()
        assert win.nav_bar.btn_next.isEnabled()

    def test_display_page(self, qtbot):
        win = MainWindow()
        qtbot.addWidget(win)
        img = Image.new("RGB", (100, 100), "white")
        win.display_page(img, 100, 100)

    def test_get_preview_size(self, qtbot):
        win = MainWindow()
        qtbot.addWidget(win)
        size = win.get_preview_size()
        assert isinstance(size, tuple)
        assert len(size) == 2

    def test_get_section_filename(self, qtbot):
        win = MainWindow()
        qtbot.addWidget(win)
        assert isinstance(win.get_section_filename(), str)

    def test_set_section_filename(self, qtbot):
        win = MainWindow()
        qtbot.addWidget(win)
        win.set_section_filename("test.pdf")

    def test_schedule_focus_filename_entry(self, qtbot):
        win = MainWindow()
        qtbot.addWidget(win)
        win.schedule_focus_filename_entry()

    def test_update_compression_ui(self, qtbot):
        win = MainWindow()
        qtbot.addWidget(win)

        win.update_compression_ui(
            CompressionUiState(
                input_items=[CompressionInputItem(path="C:/work/sample.pdf", label="[PDF] C:/work/sample.pdf")],
                output_dir_text="C:/out",
                progress_value=25,
                can_execute=True,
            ),
        )

        assert win.compress_view.input_list.count() == 1
        assert win.compress_view.txt_output_dir.text() == "C:/out"
        assert win.compress_view.btn_execute.isEnabled()

    def test_update_merge_ui(self, qtbot):
        win = MainWindow()
        qtbot.addWidget(win)

        win.update_merge_ui(
            MergeUiState(
                input_items=[MergeInputItem(path="C:/work/sample.pdf", title="sample.pdf", detail="C:/work/sample.pdf")],
                output_path_text="C:/out/merged.pdf",
                can_execute=True,
            ),
        )

        assert win.merge_view.input_list.count() == 1
        assert win.merge_view.txt_output_path.text() == "C:/out/merged.pdf"
        assert win.merge_view.btn_execute.isEnabled()

    def test_set_pdf_to_jpeg_presenter(self, qtbot):
        win = MainWindow()
        qtbot.addWidget(win)
        mock_presenter = MagicMock()

        win.set_pdf_to_jpeg_presenter(mock_presenter)

        win.pdf_to_jpeg_view.btn_choose_pdf.click()
        mock_presenter.choose_pdf_file.assert_called_once()

    def test_set_flatten_presenter(self, qtbot):
        win = MainWindow()
        qtbot.addWidget(win)
        mock_presenter = MagicMock()

        win.set_flatten_presenter(mock_presenter)

        win.flatten_view.btn_add_pdf.click()
        mock_presenter.add_pdf_files.assert_called_once()

        win.flatten_view.btn_add_folder.click()
        mock_presenter.add_folder.assert_called_once()

        win.update_flatten_ui(FlattenUiState(can_execute=True))
        win.flatten_view.btn_execute.click()
        mock_presenter.execute_flatten.assert_called_once()

    def test_update_pdf_to_jpeg_ui(self, qtbot):
        win = MainWindow()
        qtbot.addWidget(win)

        win.update_pdf_to_jpeg_ui(
            PdfToJpegUiState(
                selected_pdf_text="C:/work/sample.pdf",
                output_dir_text="C:/out",
                output_detail_text="出力先サブフォルダ: C:/out/sample",
                progress_value=20,
                can_execute=True,
                has_input_pdf=True,
            ),
        )

        assert win.pdf_to_jpeg_view.txt_selected_pdf.text() == "C:/work/sample.pdf"
        assert win.pdf_to_jpeg_view.txt_output_dir.text() == "C:/out"
        assert win.pdf_to_jpeg_view.btn_execute.isEnabled()

    def test_update_flatten_ui(self, qtbot):
        win = MainWindow()
        qtbot.addWidget(win)

        win.update_flatten_ui(
            FlattenUiState(
                input_items=[FlattenInputItem(path="C:/work/sample.pdf", label="[PDF] C:/work/sample.pdf")],
                progress_value=25,
                can_execute=True,
            ),
        )

        assert win.flatten_view.input_list.count() == 1
        assert win.flatten_view.progress_bar.value() == 25
        assert win.flatten_view.btn_execute.isEnabled()

    def test_get_selected_flatten_inputs(self, qtbot):
        win = MainWindow()
        qtbot.addWidget(win)

        win.update_flatten_ui(
            FlattenUiState(
                input_items=[
                    FlattenInputItem(path="C:/one.pdf", label="[PDF] C:/one.pdf"),
                    FlattenInputItem(path="C:/two.pdf", label="[PDF] C:/two.pdf"),
                ],
                can_remove_selected=True,
                can_clear_inputs=True,
            ),
        )

        win.flatten_view.input_list.item(1).setSelected(True)

        assert win.get_selected_flatten_inputs() == ["C:/two.pdf"]

    def test_get_pdf_to_jpeg_preview_size(self, qtbot):
        win = MainWindow()
        qtbot.addWidget(win)

        size = win.get_pdf_to_jpeg_preview_size()

        assert isinstance(size, tuple)
        assert len(size) == 2

    def test_show_info(self, qtbot, monkeypatch):
        win = MainWindow()
        qtbot.addWidget(win)
        monkeypatch.setattr(QMessageBox, "information", lambda *a, **kw: None)
        win.show_info("title", "message")

    def test_show_error(self, qtbot, monkeypatch):
        win = MainWindow()
        qtbot.addWidget(win)
        monkeypatch.setattr(QMessageBox, "critical", lambda *a, **kw: None)
        win.show_error("title", "message")

    def test_ask_yes_no(self, qtbot, monkeypatch):
        win = MainWindow()
        qtbot.addWidget(win)
        monkeypatch.setattr(
            QMessageBox, "question",
            lambda *a, **kw: QMessageBox.StandardButton.No,
        )
        result = win.ask_yes_no("title", "message")
        assert result is False

    def test_ask_ok_cancel(self, qtbot, monkeypatch):
        win = MainWindow()
        qtbot.addWidget(win)
        monkeypatch.setattr(
            QMessageBox, "question",
            lambda *a, **kw: QMessageBox.StandardButton.Cancel,
        )
        result = win.ask_ok_cancel("title", "message")
        assert result is False

    def test_ask_open_file(self, qtbot, monkeypatch):
        win = MainWindow()
        qtbot.addWidget(win)
        monkeypatch.setattr(
            QFileDialog, "getOpenFileName", lambda *a, **kw: ("", ""),
        )
        result = win.ask_open_file()
        assert result is None

    def test_ask_directory(self, qtbot, monkeypatch):
        win = MainWindow()
        qtbot.addWidget(win)
        monkeypatch.setattr(
            QFileDialog, "getExistingDirectory", lambda *a, **kw: "",
        )
        result = win.ask_directory()
        assert result is None

    def test_ask_open_files(self, qtbot, monkeypatch):
        win = MainWindow()
        qtbot.addWidget(win)
        monkeypatch.setattr(
            QFileDialog, "getOpenFileNames", lambda *a, **kw: (["a.pdf", "b.pdf"], "PDF Files (*.pdf)"),
        )

        result = win.ask_open_files("PDFファイルを選択", "PDF Files (*.pdf)")

        assert result == ["a.pdf", "b.pdf"]

    def test_ask_save_file(self, qtbot, monkeypatch):
        win = MainWindow()
        qtbot.addWidget(win)
        monkeypatch.setattr(
            QFileDialog, "getSaveFileName", lambda *a, **kw: ("merged.pdf", "PDF Files (*.pdf)"),
        )

        result = win.ask_save_file("保存先を選択", "PDF Files (*.pdf)")

        assert result == "merged.pdf"

    def test_schedule(self, qtbot):
        win = MainWindow()
        qtbot.addWidget(win)
        job_id = win.schedule(100, lambda: None)
        assert isinstance(job_id, str)
        assert job_id.startswith("timer_")
        # Clean up
        win.cancel_schedule(job_id)

    def test_cancel_schedule(self, qtbot):
        win = MainWindow()
        qtbot.addWidget(win)
        called = []
        job_id = win.schedule(50, lambda: called.append(True))
        win.cancel_schedule(job_id)
        # タイマーはキャンセル済み — 辞書から除去されている
        assert job_id not in win._timers

    def test_schedule_fires_callback(self, qtbot):
        """QTimer が実際にコールバックを発火する。"""
        win = MainWindow()
        qtbot.addWidget(win)
        results = []
        win.schedule(10, lambda: results.append("fired"))
        qtbot.waitUntil(lambda: len(results) > 0, timeout=1000)
        assert results == ["fired"]

    def test_destroy_window(self, qtbot):
        win = MainWindow()
        qtbot.addWidget(win)
        win.destroy_window()
