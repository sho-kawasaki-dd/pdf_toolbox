"""SplitBar のテスト (Step 1.5)。"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QMouseEvent

from view.split.components.split_bar import SplitBar


class TestSplitBar:
    """SplitBar の状態更新・描画・クリックイベントを検証する。"""

    def test_can_instantiate(self, qtbot):
        bar = SplitBar()
        qtbot.addWidget(bar)
        assert bar is not None

    def test_initial_state(self, qtbot):
        bar = SplitBar()
        qtbot.addWidget(bar)
        assert bar.total_pages == 0
        assert bar.current_page == 0
        assert bar.split_points == []
        assert bar.active_section_index == -1

    def test_update_state(self, qtbot):
        bar = SplitBar()
        qtbot.addWidget(bar)
        bar.update_state(total=10, current=3, splits=[5], active_section_index=0)
        assert bar.total_pages == 10
        assert bar.current_page == 3
        assert bar.split_points == [5]
        assert bar.active_section_index == 0

    def test_update_state_sorts_splits(self, qtbot):
        bar = SplitBar()
        qtbot.addWidget(bar)
        bar.update_state(total=10, current=0, splits=[7, 3, 5])
        assert bar.split_points == [3, 5, 7]

    def test_paint_no_crash_zero_pages(self, qtbot):
        """total_pages=0 で描画してもクラッシュしない。"""
        bar = SplitBar()
        qtbot.addWidget(bar)
        bar.show()
        bar.update_state(total=0, current=0, splits=[])
        bar.repaint()

    def test_paint_no_crash_with_data(self, qtbot):
        """データがある状態で描画してもクラッシュしない。"""
        bar = SplitBar()
        qtbot.addWidget(bar)
        bar.show()
        bar.resize(300, 30)
        bar.update_state(total=10, current=3, splits=[5], active_section_index=0)
        bar.repaint()

    def test_click_fires_callback(self, qtbot):
        """クリックイベントで正しいページ番号のコールバックが発火する。"""
        bar = SplitBar()
        qtbot.addWidget(bar)
        bar.resize(200, 30)
        bar.show()
        bar.update_state(total=10, current=0, splits=[])

        callback = MagicMock()
        bar.set_on_page_click(callback)

        # バーの中央をクリック → ページ 5 付近
        qtbot.mouseClick(bar, Qt.MouseButton.LeftButton, pos=bar.rect().center())
        assert callback.called
        page = callback.call_args[0][0]
        assert 0 <= page < 10

    def test_click_no_callback_no_crash(self, qtbot):
        """コールバック未設定でクリックしてもクラッシュしない。"""
        bar = SplitBar()
        qtbot.addWidget(bar)
        bar.resize(200, 30)
        bar.show()
        bar.update_state(total=10, current=0, splits=[])
        qtbot.mouseClick(bar, Qt.MouseButton.LeftButton, pos=bar.rect().center())

    def test_fixed_height(self, qtbot):
        bar = SplitBar()
        qtbot.addWidget(bar)
        assert bar.height() == 30
