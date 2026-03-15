"""色分けされた分割プログレスバーウィジェット (PySide6)。

セクションごとの色定数は Presenter からも参照されるため、モジュールレベルで定義する。
``SplitBar`` は QPainter で描画し、クリック/ドラッグでページ移動を行う。
"""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QColor, QPen, QPolygonF, QBrush
from PySide6.QtCore import Qt, QPointF


SECTION_COLORS: list[str] = [
    "#3498db",
    "#e74c3c",
    "#2ecc71",
    "#f39c12",
    "#9b59b6",
    "#1abc9c",
]


class SplitBar(QWidget):
    """ページ位置と分割点を視覚化するプログレスバー。

    ``update_state`` でデータを受け取り ``paintEvent`` で QPainter 描画する。
    クリック / ドラッグでページ移動コールバックを発火する。
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(30)
        self.setMouseTracking(False)

        self.total_pages: int = 0
        self.current_page: int = 0
        self.split_points: list[int] = []
        self.active_section_index: int = -1
        self._on_page_click: Callable[[int], None] | None = None

    # ------------------------------------------------------------------
    # 公開メソッド
    # ------------------------------------------------------------------

    def set_on_page_click(self, callback: Callable[[int], None]) -> None:
        """ページクリック時のコールバックを設定する。"""
        self._on_page_click = callback

    def update_state(
        self,
        total: int,
        current: int,
        splits: list[int],
        active_section_index: int = -1,
    ) -> None:
        """描画状態を更新して再描画をスケジュールする。"""
        self.total_pages = total
        self.current_page = current
        self.split_points = sorted(splits)
        self.active_section_index = active_section_index
        self.update()

    # ------------------------------------------------------------------
    # マウスイベント
    # ------------------------------------------------------------------

    def _event_to_page(self, x: int) -> int | None:
        """マウス x 座標を 0-based ページインデックスに変換する。"""
        if self.total_pages <= 0:
            return None
        w = self.width()
        if w <= 1:
            return None
        x_clamped = min(max(x, 0), w - 1)
        page = int((x_clamped / w) * self.total_pages)
        return min(max(page, 0), self.total_pages - 1)

    def mousePressEvent(self, event) -> None:
        """クリックでページ移動コールバックを発火する。"""
        page = self._event_to_page(int(event.position().x()))
        if page is not None and self._on_page_click:
            self._on_page_click(page)

    def mouseMoveEvent(self, event) -> None:
        """ドラッグでページ移動コールバックを発火する。"""
        if event.buttons() & Qt.MouseButton.LeftButton:
            page = self._event_to_page(int(event.position().x()))
            if page is not None and self._on_page_click:
                self._on_page_click(page)

    # ------------------------------------------------------------------
    # 描画
    # ------------------------------------------------------------------

    def paintEvent(self, event) -> None:
        """セクション色分け・分割線・アクティブ枠・現在位置インジケータを描画する。"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        if self.total_pages <= 0 or w <= 1:
            painter.end()
            return

        page_width = w / self.total_pages

        # 1. セクション色分け
        start_page = 0
        color_idx = 0
        boundaries = self.split_points + [self.total_pages]
        for boundary in boundaries:
            if boundary <= start_page:
                continue
            x_start = start_page * page_width
            x_end = boundary * page_width
            color = QColor(SECTION_COLORS[color_idx % len(SECTION_COLORS)])
            painter.fillRect(int(x_start), 0, int(x_end - x_start), h, color)
            start_page = boundary
            color_idx += 1

        # 2. 分割線
        pen = QPen(QColor("black"), 2)
        painter.setPen(pen)
        for point in self.split_points:
            x = int(point * page_width)
            painter.drawLine(x, 0, x, h)

        # 3. アクティブセクション枠
        if self.active_section_index >= 0:
            all_boundaries = [0] + self.split_points + [self.total_pages]
            if self.active_section_index < len(all_boundaries) - 1:
                sec_start = all_boundaries[self.active_section_index]
                sec_end = all_boundaries[self.active_section_index + 1]
                x_s = int(sec_start * page_width) + 1
                x_e = int(sec_end * page_width) - 1
                painter.setPen(QPen(QColor("white"), 2))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(x_s, 1, x_e - x_s, h - 2)

        # 4. 現在位置インジケータ（逆三角形）
        cx = (self.current_page + 0.5) * page_width
        triangle = QPolygonF([
            QPointF(cx - 6, 0),
            QPointF(cx + 6, 0),
            QPointF(cx, 10),
        ])
        painter.setPen(QPen(QColor("black"), 1))
        painter.setBrush(QBrush(QColor("white")))
        painter.drawPolygon(triangle)

        painter.end()
