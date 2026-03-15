"""SplitView tests."""

from __future__ import annotations

from unittest.mock import MagicMock

from view.split.split_view import SplitView, UiState


class TestSplitView:

    def test_can_instantiate(self, qtbot):
        view = SplitView()
        qtbot.addWidget(view)
        assert view is not None

    def test_update_ui_delegates_to_child_widgets(self, qtbot):
        view = SplitView()
        qtbot.addWidget(view)
        view.nav_bar.apply_state = MagicMock()
        view.split_bar.update_state = MagicMock()
        view.split_action_bar.apply_state = MagicMock()
        view.right_panel.apply_state = MagicMock()
        view.right_panel.section.apply_state = MagicMock()

        state = UiState(
            page_info_text="2 / 8",
            zoom_info_text="倍率: 120%",
            total_pages=8,
            current_page=1,
            split_points=[3],
            active_section_index=0,
            section_info_text="セクション 1 / 2",
            section_range_text="ページ範囲: P.1 - P.3",
            section_color="#3498db",
            section_filename="part1.pdf",
            can_prev=True,
            can_next=True,
            can_add_split=True,
            can_remove_split=False,
            can_clear_split=True,
            can_split_every=True,
            can_execute=True,
            can_open=True,
            can_prev_section=False,
            can_next_section=True,
            can_remove_active_split=False,
            can_edit_filename=True,
        )

        view.update_ui(state)

        view.nav_bar.apply_state.assert_called_once_with("2 / 8", True, True)
        view.split_bar.update_state.assert_called_once_with(8, 1, [3], 0)
        view.split_action_bar.apply_state.assert_called_once_with("倍率: 120%", True, False)
        view.right_panel.apply_state.assert_called_once_with(True, True, True, True)
        view.right_panel.section.apply_state.assert_called_once_with(
            "セクション 1 / 2",
            "ページ範囲: P.1 - P.3",
            "#3498db",
            "part1.pdf",
            False,
            True,
            False,
            True,
        )

    def test_back_button_emits_signal(self, qtbot):
        view = SplitView()
        qtbot.addWidget(view)
        received = []
        view.back_to_home_requested.connect(lambda: received.append(True))

        view.btn_back_home.click()

        assert received == [True]
