"""HomeView tests."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QToolButton

from view.home_view import HomeView


class TestHomeView:

    def test_can_instantiate(self, qtbot):
        view = HomeView()
        qtbot.addWidget(view)
        assert view is not None

    def test_split_and_compress_cards_enabled(self, qtbot):
        view = HomeView()
        qtbot.addWidget(view)
        assert view.feature_buttons["split"].isEnabled()
        assert view.feature_buttons["compress"].isEnabled()
        assert not view.feature_buttons["merge"].isEnabled()
        assert not view.feature_buttons["reorder"].isEnabled()
        assert not view.feature_buttons["pdf-to-jpeg"].isEnabled()

    def test_click_split_emits_feature_selected(self, qtbot):
        view = HomeView()
        qtbot.addWidget(view)
        received = []
        view.feature_selected.connect(received.append)

        qtbot.mouseClick(view.feature_buttons["split"], Qt.MouseButton.LeftButton)

        assert received == ["split"]

    def test_click_compress_emits_feature_selected(self, qtbot):
        view = HomeView()
        qtbot.addWidget(view)
        received = []
        view.feature_selected.connect(received.append)

        qtbot.mouseClick(view.feature_buttons["compress"], Qt.MouseButton.LeftButton)

        assert received == ["compress"]

    def test_disabled_cards_show_preparing_text(self, qtbot):
        view = HomeView()
        qtbot.addWidget(view)
        assert "準備中" in view.feature_buttons["merge"].text()
        assert "準備中" in view.feature_buttons["pdf-to-jpeg"].text()
        assert "準備中" not in view.feature_buttons["compress"].text()

    def test_cards_use_icon_buttons_with_text_under_icon(self, qtbot):
        view = HomeView()
        qtbot.addWidget(view)

        split_button = view.feature_buttons["split"]
        assert isinstance(split_button, QToolButton)
        assert split_button.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonTextUnderIcon
        assert split_button.text() == "PDF 分割"

    def test_cards_load_expected_icons(self, qtbot):
        view = HomeView()
        qtbot.addWidget(view)

        assert not view.feature_buttons["split"].icon().isNull()
        assert not view.feature_buttons["merge"].icon().isNull()
        assert not view.feature_buttons["reorder"].icon().isNull()
        assert not view.feature_buttons["compress"].icon().isNull()
        assert not view.feature_buttons["pdf-to-jpeg"].icon().isNull()

    def test_pdf_to_jpeg_card_has_expected_label(self, qtbot):
        view = HomeView()
        qtbot.addWidget(view)

        assert "PDF → JPEG" in view.feature_buttons["pdf-to-jpeg"].text()

    def test_cards_keep_portrait_ratio(self, qtbot):
        view = HomeView()
        qtbot.addWidget(view)

        split_button = view.feature_buttons["split"]
        assert split_button.minimumHeight() > split_button.minimumWidth()
        assert split_button.iconSize().width() == split_button.iconSize().height()
