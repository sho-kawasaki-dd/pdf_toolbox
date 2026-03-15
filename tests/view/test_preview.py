"""PreviewPanel のテスト (Step 1.3)。

インスタンス化・画像表示・プレースホルダー・サイズを検証する。
"""

from __future__ import annotations

import pytest
from PIL import Image
from PySide6.QtGui import QColor

from view.components.preview import PreviewPanel
from view.components.preview import _pil_to_qpixmap


class TestPreviewPanel:

    def test_can_instantiate(self, qtbot):
        panel = PreviewPanel()
        qtbot.addWidget(panel)

    def test_display_image_rgb(self, qtbot):
        panel = PreviewPanel()
        qtbot.addWidget(panel)
        img = Image.new("RGB", (200, 300), "red")
        panel.display_image(img, 200, 300)

    def test_display_image_rgba(self, qtbot):
        panel = PreviewPanel()
        qtbot.addWidget(panel)
        img = Image.new("RGBA", (200, 300), (255, 0, 0, 128))
        panel.display_image(img, 200, 300)

    def test_pil_to_qpixmap_preserves_dimensions(self):
        img = Image.new("RGB", (137, 211), "red")
        pixmap = _pil_to_qpixmap(img)
        assert pixmap.width() == 137
        assert pixmap.height() == 211

    def test_pil_to_qpixmap_preserves_pixel_layout(self):
        img = Image.new("RGB", (3, 2), "black")
        img.putpixel((0, 0), (255, 0, 0))
        img.putpixel((1, 0), (0, 255, 0))
        img.putpixel((2, 0), (0, 0, 255))
        pixmap = _pil_to_qpixmap(img)
        qimage = pixmap.toImage()
        assert qimage.pixelColor(0, 0) == QColor(255, 0, 0)
        assert qimage.pixelColor(1, 0) == QColor(0, 255, 0)
        assert qimage.pixelColor(2, 0) == QColor(0, 0, 255)

    def test_size_returns_tuple(self, qtbot):
        panel = PreviewPanel()
        qtbot.addWidget(panel)
        size = panel.size
        assert isinstance(size, tuple)
        assert len(size) == 2
        assert isinstance(size[0], int)
        assert isinstance(size[1], int)

    def test_show_placeholder(self, qtbot):
        panel = PreviewPanel()
        qtbot.addWidget(panel)
        panel.show_placeholder("テスト")

    def test_show_placeholder_default(self, qtbot):
        panel = PreviewPanel()
        qtbot.addWidget(panel)
        panel.show_placeholder()

    def test_focus(self, qtbot):
        panel = PreviewPanel()
        qtbot.addWidget(panel)
        panel.focus()
