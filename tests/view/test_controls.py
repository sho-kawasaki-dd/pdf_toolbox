"""NavigationBar / SplitActionBar / SectionPanel / RightPanel のテスト。"""

from __future__ import annotations

import pytest

from view.components.controls import (
    NavigationBar, SplitActionBar, SectionPanel, RightPanel,
    LEFT_PANEL_BUTTON_HEIGHT, LEFT_PANEL_BUTTON_POINT_SIZE, LEFT_PANEL_LABEL_POINT_SIZE,
    RIGHT_PANEL_BUTTON_HEIGHT, RIGHT_PANEL_INPUT_HEIGHT,
    RIGHT_PANEL_LABEL_POINT_SIZE, RIGHT_PANEL_PRIMARY_BUTTON_HEIGHT,
)


class TestNavigationBar:
    """NavigationBar のインスタンス化・ボタン構成・状態更新を検証する。"""

    def test_can_instantiate(self, qtbot):
        bar = NavigationBar()
        qtbot.addWidget(bar)
        assert bar is not None

    def test_has_five_buttons_and_label(self, qtbot):
        bar = NavigationBar()
        qtbot.addWidget(bar)
        assert bar.btn_prev_10 is not None
        assert bar.btn_prev is not None
        assert bar.lbl_page_info is not None
        assert bar.btn_next is not None
        assert bar.btn_next_10 is not None

    def test_buttons_initially_disabled(self, qtbot):
        bar = NavigationBar()
        qtbot.addWidget(bar)
        assert not bar.btn_prev.isEnabled()
        assert not bar.btn_prev_10.isEnabled()
        assert not bar.btn_next.isEnabled()
        assert not bar.btn_next_10.isEnabled()

    def test_initial_label_text(self, qtbot):
        bar = NavigationBar()
        qtbot.addWidget(bar)
        assert bar.lbl_page_info.text() == "0 / 0"

    def test_update_enables_buttons(self, qtbot):
        bar = NavigationBar()
        qtbot.addWidget(bar)
        bar.apply_state("3 / 10", can_prev=True, can_next=True)
        assert bar.lbl_page_info.text() == "3 / 10"
        assert bar.btn_prev.isEnabled()
        assert bar.btn_prev_10.isEnabled()
        assert bar.btn_next.isEnabled()
        assert bar.btn_next_10.isEnabled()

    def test_update_disables_prev(self, qtbot):
        bar = NavigationBar()
        qtbot.addWidget(bar)
        bar.apply_state("1 / 10", can_prev=False, can_next=True)
        assert not bar.btn_prev.isEnabled()
        assert not bar.btn_prev_10.isEnabled()
        assert bar.btn_next.isEnabled()
        assert bar.btn_next_10.isEnabled()

    def test_update_disables_next(self, qtbot):
        bar = NavigationBar()
        qtbot.addWidget(bar)
        bar.apply_state("10 / 10", can_prev=True, can_next=False)
        assert bar.btn_prev.isEnabled()
        assert bar.btn_prev_10.isEnabled()
        assert not bar.btn_next.isEnabled()
        assert not bar.btn_next_10.isEnabled()

    def test_update_all_disabled(self, qtbot):
        bar = NavigationBar()
        qtbot.addWidget(bar)
        # First enable, then disable to verify state transitions
        bar.apply_state("5 / 10", can_prev=True, can_next=True)
        bar.apply_state("0 / 0", can_prev=False, can_next=False)
        assert not bar.btn_prev.isEnabled()
        assert not bar.btn_next.isEnabled()
        assert bar.lbl_page_info.text() == "0 / 0"

    def test_uses_larger_left_panel_button_and_label_sizes(self, qtbot):
        bar = NavigationBar()
        qtbot.addWidget(bar)
        assert bar.btn_prev.minimumHeight() == LEFT_PANEL_BUTTON_HEIGHT
        assert bar.btn_next.minimumHeight() == LEFT_PANEL_BUTTON_HEIGHT
        assert bar.btn_prev.font().pointSize() >= LEFT_PANEL_BUTTON_POINT_SIZE
        assert bar.lbl_page_info.font().pointSize() >= LEFT_PANEL_LABEL_POINT_SIZE


class TestSplitActionBar:
    """SplitActionBar のインスタンス化・ボタン構成・状態更新を検証する。"""

    def test_can_instantiate(self, qtbot):
        bar = SplitActionBar()
        qtbot.addWidget(bar)
        assert bar is not None

    def test_has_buttons_and_label(self, qtbot):
        bar = SplitActionBar()
        qtbot.addWidget(bar)
        assert bar.lbl_zoom_info is not None
        assert bar.btn_add_split is not None
        assert bar.btn_remove_split is not None

    def test_buttons_initially_disabled(self, qtbot):
        bar = SplitActionBar()
        qtbot.addWidget(bar)
        assert not bar.btn_add_split.isEnabled()
        assert not bar.btn_remove_split.isEnabled()

    def test_initial_zoom_label(self, qtbot):
        bar = SplitActionBar()
        qtbot.addWidget(bar)
        assert bar.lbl_zoom_info.text() == "倍率: 100%"

    def test_update_enables_add(self, qtbot):
        bar = SplitActionBar()
        qtbot.addWidget(bar)
        bar.apply_state("倍率: 150%", can_add=True, can_remove=False)
        assert bar.lbl_zoom_info.text() == "倍率: 150%"
        assert bar.btn_add_split.isEnabled()
        assert not bar.btn_remove_split.isEnabled()

    def test_update_enables_remove(self, qtbot):
        bar = SplitActionBar()
        qtbot.addWidget(bar)
        bar.apply_state("倍率: 100%", can_add=False, can_remove=True)
        assert not bar.btn_add_split.isEnabled()
        assert bar.btn_remove_split.isEnabled()

    def test_update_disables_both(self, qtbot):
        bar = SplitActionBar()
        qtbot.addWidget(bar)
        bar.apply_state("倍率: 100%", can_add=True, can_remove=True)
        bar.apply_state("倍率: 100%", can_add=False, can_remove=False)
        assert not bar.btn_add_split.isEnabled()
        assert not bar.btn_remove_split.isEnabled()

    def test_uses_larger_left_panel_controls(self, qtbot):
        bar = SplitActionBar()
        qtbot.addWidget(bar)
        assert bar.lbl_zoom_info.minimumWidth() >= 110
        assert bar.lbl_zoom_info.font().pointSize() >= LEFT_PANEL_LABEL_POINT_SIZE
        assert bar.btn_add_split.minimumHeight() == LEFT_PANEL_BUTTON_HEIGHT
        assert bar.btn_remove_split.minimumHeight() == LEFT_PANEL_BUTTON_HEIGHT
        assert bar.btn_add_split.font().pointSize() >= LEFT_PANEL_BUTTON_POINT_SIZE


class TestSectionPanel:
    """SectionPanel のインスタンス化・状態更新・ファイル名操作を検証する。"""

    def test_can_instantiate(self, qtbot):
        panel = SectionPanel()
        qtbot.addWidget(panel)
        assert panel is not None

    def test_get_filename_empty(self, qtbot):
        panel = SectionPanel()
        qtbot.addWidget(panel)
        assert panel.get_filename() == ""

    def test_set_filename(self, qtbot):
        panel = SectionPanel()
        qtbot.addWidget(panel)
        panel.txt_filename.setEnabled(True)
        panel.set_filename("test.pdf")
        assert panel.get_filename() == "test.pdf"

    def test_set_filename_no_change_if_same(self, qtbot):
        """同じテキストなら setText は呼ばれない。"""
        panel = SectionPanel()
        qtbot.addWidget(panel)
        panel.txt_filename.setEnabled(True)
        panel.set_filename("test.pdf")
        panel.set_filename("test.pdf")
        assert panel.get_filename() == "test.pdf"

    def test_update_labels_and_buttons(self, qtbot):
        panel = SectionPanel()
        qtbot.addWidget(panel)
        panel.apply_state(
            section_info_text="セクション 2 / 3",
            section_range_text="ページ範囲: P.4 - P.6",
            section_color="#e74c3c",
            section_filename="part2.pdf",
            can_prev_section=True,
            can_next_section=True,
            can_remove_active_split=True,
            can_edit_filename=True,
        )
        assert panel.lbl_section_info.text() == "セクション 2 / 3"
        assert panel.lbl_section_range.text() == "ページ範囲: P.4 - P.6"
        assert panel.get_filename() == "part2.pdf"
        assert panel.lbl_section_title.text() == "現在のセクション:"
        assert panel.btn_prev_section.isEnabled()
        assert panel.btn_next_section.isEnabled()
        assert panel.btn_remove_active_split.isEnabled()
        assert panel.txt_filename.isEnabled()

    def test_update_disables_buttons(self, qtbot):
        panel = SectionPanel()
        qtbot.addWidget(panel)
        panel.apply_state(
            section_info_text="- / -",
            section_range_text="ページ範囲: -",
            section_color="gray",
            section_filename="",
            can_prev_section=False,
            can_next_section=False,
            can_remove_active_split=False,
            can_edit_filename=False,
        )
        assert not panel.btn_prev_section.isEnabled()
        assert not panel.btn_next_section.isEnabled()
        assert not panel.btn_remove_active_split.isEnabled()
        assert not panel.txt_filename.isEnabled()

    def test_uses_larger_font_and_input_height(self, qtbot):
        panel = SectionPanel()
        qtbot.addWidget(panel)
        assert panel.txt_filename.minimumHeight() == RIGHT_PANEL_INPUT_HEIGHT
        assert panel.txt_filename.font().pointSize() >= RIGHT_PANEL_LABEL_POINT_SIZE
        assert panel.btn_prev_section.minimumHeight() == RIGHT_PANEL_BUTTON_HEIGHT
        assert panel.btn_next_section.minimumHeight() == RIGHT_PANEL_BUTTON_HEIGHT


class TestRightPanel:
    """RightPanel のボタン有効/無効切り替えを検証する。"""

    def test_can_instantiate(self, qtbot):
        panel = RightPanel()
        qtbot.addWidget(panel)
        assert panel is not None

    def test_buttons_initially_disabled(self, qtbot):
        panel = RightPanel()
        qtbot.addWidget(panel)
        assert not panel.btn_clear_split.isEnabled()
        assert not panel.btn_split_every.isEnabled()
        assert not panel.btn_execute.isEnabled()
        assert panel.btn_open.isEnabled()

    def test_update_enables_buttons(self, qtbot):
        panel = RightPanel()
        qtbot.addWidget(panel)
        panel.apply_state(
            can_open=True, can_clear_split=True,
            can_split_every=True, can_execute=True,
        )
        assert panel.btn_open.isEnabled()
        assert panel.btn_clear_split.isEnabled()
        assert panel.btn_split_every.isEnabled()
        assert panel.btn_execute.isEnabled()

    def test_update_disables_open(self, qtbot):
        panel = RightPanel()
        qtbot.addWidget(panel)
        panel.apply_state(
            can_open=False, can_clear_split=False,
            can_split_every=False, can_execute=False,
        )
        assert not panel.btn_open.isEnabled()

    def test_has_section_panel(self, qtbot):
        panel = RightPanel()
        qtbot.addWidget(panel)
        assert isinstance(panel.section, SectionPanel)

    def test_uses_taller_buttons(self, qtbot):
        panel = RightPanel()
        qtbot.addWidget(panel)
        assert panel.btn_open.minimumHeight() == RIGHT_PANEL_PRIMARY_BUTTON_HEIGHT
        assert panel.btn_execute.minimumHeight() == RIGHT_PANEL_PRIMARY_BUTTON_HEIGHT
        assert panel.btn_clear_split.minimumHeight() == RIGHT_PANEL_BUTTON_HEIGHT
        assert panel.btn_split_every.minimumHeight() == RIGHT_PANEL_BUTTON_HEIGHT
        assert panel.btn_open.font().pointSize() >= RIGHT_PANEL_LABEL_POINT_SIZE
        assert "#bfdbfe" in panel.btn_open.styleSheet().lower()
