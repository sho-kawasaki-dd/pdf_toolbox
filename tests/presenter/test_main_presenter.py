"""MainPresenter のテスト (Step 1.3〜 段階的に拡充)。

View をモックして Presenter ロジックを単体テストする。
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from model.pdf_document import PdfDocument
from model.split_session import SplitSession
from presenter.main_presenter import MainPresenter
from view.main_window import UiState


def _make_mock_view() -> MagicMock:
    """Presenter が要求する公開メソッドを持つ Mock View を生成する。"""
    view = MagicMock()
    view.get_preview_size.return_value = (500, 600)
    view.get_section_filename.return_value = ""
    view.ask_open_file.return_value = None
    view.ask_directory.return_value = None
    view.ask_yes_no.return_value = False
    view.ask_ok_cancel.return_value = False
    view.schedule.return_value = "timer_1"
    return view


class TestOpenPdf:
    """open_pdf() のテスト。"""

    def test_open_pdf_calls_display_page(self, sample_pdf: Path):
        view = _make_mock_view()
        view.ask_open_file.return_value = str(sample_pdf)
        presenter = MainPresenter(view)

        presenter.open_pdf()

        view.display_page.assert_called_once()
        args = view.display_page.call_args
        # PIL Image, width, height
        assert args[0][1] > 0
        assert args[0][2] > 0

    def test_open_pdf_calls_update_ui(self, sample_pdf: Path):
        view = _make_mock_view()
        view.ask_open_file.return_value = str(sample_pdf)
        presenter = MainPresenter(view)

        presenter.open_pdf()

        view.update_ui.assert_called()
        state = view.update_ui.call_args[0][0]
        assert isinstance(state, UiState)
        assert state.total_pages == 10

    def test_open_pdf_cancel(self):
        view = _make_mock_view()
        view.ask_open_file.return_value = None
        presenter = MainPresenter(view)

        presenter.open_pdf()

        view.display_page.assert_not_called()


class TestPageNavigation:
    """ページナビゲーションのテスト。"""

    def test_next_page(self, sample_pdf: Path):
        view = _make_mock_view()
        view.ask_open_file.return_value = str(sample_pdf)
        presenter = MainPresenter(view)
        presenter.open_pdf()
        view.reset_mock()

        presenter.next_page()

        view.display_page.assert_called_once()
        view.update_ui.assert_called_once()

    def test_prev_page_at_first(self, sample_pdf: Path):
        view = _make_mock_view()
        view.ask_open_file.return_value = str(sample_pdf)
        presenter = MainPresenter(view)
        presenter.open_pdf()
        view.reset_mock()

        presenter.prev_page()

        # 先頭ページなので何も起きない
        view.display_page.assert_not_called()

    def test_prev_page_after_next(self, sample_pdf: Path):
        view = _make_mock_view()
        view.ask_open_file.return_value = str(sample_pdf)
        presenter = MainPresenter(view)
        presenter.open_pdf()
        presenter.next_page()
        view.reset_mock()

        presenter.prev_page()

        view.display_page.assert_called_once()


class TestZoom:
    """ズーム操作のテスト (Step 1.6)。"""

    def test_zoom_in(self, sample_pdf: Path):
        view = _make_mock_view()
        view.ask_open_file.return_value = str(sample_pdf)
        presenter = MainPresenter(view)
        presenter.open_pdf()
        view.reset_mock()

        presenter.zoom_in()

        view.display_page.assert_called_once()
        state = view.update_ui.call_args[0][0]
        assert "110" in state.zoom_info_text

    def test_zoom_out(self, sample_pdf: Path):
        view = _make_mock_view()
        view.ask_open_file.return_value = str(sample_pdf)
        presenter = MainPresenter(view)
        presenter.open_pdf()
        presenter.zoom_in()
        view.reset_mock()

        presenter.zoom_out()

        view.display_page.assert_called_once()
        state = view.update_ui.call_args[0][0]
        assert "100" in state.zoom_info_text

    def test_reset_zoom(self, sample_pdf: Path):
        view = _make_mock_view()
        view.ask_open_file.return_value = str(sample_pdf)
        presenter = MainPresenter(view)
        presenter.open_pdf()
        presenter.zoom_in()
        view.reset_mock()

        presenter.reset_zoom()

        view.display_page.assert_called_once()
        state = view.update_ui.call_args[0][0]
        assert "100" in state.zoom_info_text


class TestSplitPoint:
    """分割点操作のテスト (Step 1.6)。"""

    def test_add_split_point(self, sample_pdf: Path):
        view = _make_mock_view()
        view.ask_open_file.return_value = str(sample_pdf)
        presenter = MainPresenter(view)
        presenter.open_pdf()
        presenter.next_page()  # ページ 1 に移動（ページ 0 には分割点を置けない）
        view.reset_mock()

        presenter.add_split_point()

        view.update_ui.assert_called_once()
        state = view.update_ui.call_args[0][0]
        assert 1 in state.split_points

    def test_remove_split_point(self, sample_pdf: Path):
        view = _make_mock_view()
        view.ask_open_file.return_value = str(sample_pdf)
        presenter = MainPresenter(view)
        presenter.open_pdf()
        presenter.next_page()
        presenter.add_split_point()
        view.reset_mock()

        presenter.remove_split_point()

        view.update_ui.assert_called_once()
        state = view.update_ui.call_args[0][0]
        assert 1 not in state.split_points


class TestSaveAndAdvanceSection:
    """save_and_advance_section() のテスト (Step 1.7)。"""

    def test_saves_filename_and_advances(self, sample_pdf: Path):
        view = _make_mock_view()
        view.ask_open_file.return_value = str(sample_pdf)
        view.get_section_filename.return_value = "custom_name.pdf"
        presenter = MainPresenter(view)
        presenter.open_pdf()
        # 分割点を追加してセクションを作る
        presenter.next_page()
        presenter.add_split_point()
        # ページ 0 (セクション 0) に戻る — ここから advance するとセクション 1 に移動
        presenter.prev_page()
        view.reset_mock()

        presenter.save_and_advance_section()

        # schedule_focus_filename_entry が呼ばれる
        view.schedule_focus_filename_entry.assert_called_once()


class TestClearSplitPoints:
    """clear_split_points() のテスト (Step 1.7)。"""

    def test_clear_with_confirm(self, sample_pdf: Path):
        view = _make_mock_view()
        view.ask_open_file.return_value = str(sample_pdf)
        view.ask_yes_no.return_value = True
        presenter = MainPresenter(view)
        presenter.open_pdf()
        presenter.next_page()
        presenter.add_split_point()
        view.reset_mock()
        view.ask_yes_no.return_value = True

        presenter.clear_split_points()

        view.update_ui.assert_called()
        state = view.update_ui.call_args[0][0]
        assert state.split_points == []

    def test_clear_cancelled(self, sample_pdf: Path):
        view = _make_mock_view()
        view.ask_open_file.return_value = str(sample_pdf)
        presenter = MainPresenter(view)
        presenter.open_pdf()
        presenter.next_page()
        presenter.add_split_point()
        view.reset_mock()
        view.ask_yes_no.return_value = False

        presenter.clear_split_points()

        # update_ui は呼ばれない（キャンセルされた）
        view.update_ui.assert_not_called()


class TestExecuteSplit:
    """execute_split() のテスト (Step 1.8)。"""

    def test_execute_starts_processor(self, sample_pdf: Path, tmp_path: Path):
        view = _make_mock_view()
        view.ask_open_file.return_value = str(sample_pdf)
        view.ask_directory.return_value = str(tmp_path)
        presenter = MainPresenter(view)
        presenter.open_pdf()
        view.reset_mock()

        presenter.execute_split()

        # schedule() が呼ばれてポーリングが開始される
        view.schedule.assert_called()
        view.update_ui.assert_called()

    def test_open_pdf_blocked_during_split(self, sample_pdf: Path, tmp_path: Path):
        view = _make_mock_view()
        view.ask_open_file.return_value = str(sample_pdf)
        view.ask_directory.return_value = str(tmp_path)
        presenter = MainPresenter(view)
        presenter.open_pdf()

        presenter.execute_split()
        view.reset_mock()

        # 分割中に open_pdf を呼ぶと info ダイアログでブロック
        presenter.open_pdf()
        view.show_info.assert_called_once()

    def test_on_closing_during_split(self, sample_pdf: Path, tmp_path: Path):
        view = _make_mock_view()
        view.ask_open_file.return_value = str(sample_pdf)
        view.ask_directory.return_value = str(tmp_path)
        view.ask_ok_cancel.return_value = False
        presenter = MainPresenter(view)
        presenter.open_pdf()

        presenter.execute_split()
        view.reset_mock()

        # 閉じようとすると確認ダイアログ → キャンセル
        presenter.on_closing()
        view.ask_ok_cancel.assert_called_once()
        view.destroy_window.assert_not_called()
