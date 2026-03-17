"""AppCoordinator tests."""

from __future__ import annotations

from unittest.mock import MagicMock

from presenter.app_coordinator import AppCoordinator
from view.main_window import MainWindow


class TestAppCoordinator:

    def test_split_card_shows_split_screen(self, qtbot):
        window = MainWindow()
        qtbot.addWidget(window)
        coordinator = AppCoordinator(window)

        coordinator._on_feature_selected("split")

        assert window.stack.currentWidget() is window.split_view

    def test_compress_card_shows_compress_screen(self, qtbot):
        window = MainWindow()
        qtbot.addWidget(window)
        coordinator = AppCoordinator(window)

        coordinator._on_feature_selected("compress")

        assert window.stack.currentWidget() is window.compress_view

    def test_merge_card_shows_merge_screen(self, qtbot):
        window = MainWindow()
        qtbot.addWidget(window)
        coordinator = AppCoordinator(window)

        coordinator._on_feature_selected("merge")

        assert window.stack.currentWidget() is window.merge_view

    def test_back_to_home_confirms_active_session(self, qtbot):
        window = MainWindow()
        qtbot.addWidget(window)
        coordinator = AppCoordinator(window)
        window.show_split()
        window.ask_yes_no = MagicMock(return_value=True)
        coordinator.split_presenter.has_active_session = MagicMock(return_value=True)
        coordinator.split_presenter.is_busy = MagicMock(return_value=False)

        coordinator.on_back_to_home()

        window.ask_yes_no.assert_called_once()
        assert window.stack.currentWidget() is window.home_view

    def test_back_to_home_blocked_while_busy(self, qtbot):
        window = MainWindow()
        qtbot.addWidget(window)
        coordinator = AppCoordinator(window)
        window.show_split()
        window.show_info = MagicMock()
        coordinator.split_presenter.is_busy = MagicMock(return_value=True)

        coordinator.on_back_to_home()

        window.show_info.assert_called_once()

    def test_back_to_home_blocked_while_compressing(self, qtbot):
        window = MainWindow()
        qtbot.addWidget(window)
        coordinator = AppCoordinator(window)
        window.show_compress()
        window.show_info = MagicMock()
        coordinator.compress_presenter.is_busy = MagicMock(return_value=True)

        coordinator.on_back_to_home()

        window.show_info.assert_called_once()

    def test_back_to_home_confirms_active_merge_session(self, qtbot):
        window = MainWindow()
        qtbot.addWidget(window)
        coordinator = AppCoordinator(window)
        window.show_merge()
        window.ask_yes_no = MagicMock(return_value=True)
        coordinator.merge_presenter.has_active_session = MagicMock(return_value=True)
        coordinator.merge_presenter.is_busy = MagicMock(return_value=False)

        coordinator.on_back_to_home()

        window.ask_yes_no.assert_called_once()
        assert window.stack.currentWidget() is window.home_view

    def test_back_to_home_blocked_while_merging(self, qtbot):
        window = MainWindow()
        qtbot.addWidget(window)
        coordinator = AppCoordinator(window)
        window.show_merge()
        window.show_info = MagicMock()
        coordinator.merge_presenter.is_busy = MagicMock(return_value=True)

        coordinator.on_back_to_home()

        window.show_info.assert_called_once()
