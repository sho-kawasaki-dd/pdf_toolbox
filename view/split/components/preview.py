"""PDFページプレビューウィジェット (PySide6)。

QGraphicsView + QGraphicsScene ベースで PDF ページ画像を表示する。
PIL Image → QPixmap 変換、パン操作（ScrollHandDrag）、プレースホルダーテキストを提供する。
"""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QFrame
from PySide6.QtGui import QPixmap, QImage, QFont, QColor, QPen, QPainter
from PySide6.QtCore import Qt

from PIL import Image

from view.font_config import make_app_font


def _pil_to_qpixmap(pil_image: Image.Image) -> QPixmap:
    """PIL Image を QPixmap に変換する。

    RGBA/RGB のみサポート。他モードは内部で RGB に変換する。
    """
    if pil_image.mode == "RGBA":
        fmt = QImage.Format.Format_RGBA8888
    elif pil_image.mode == "RGB":
        fmt = QImage.Format.Format_RGB888
    else:
        pil_image = pil_image.convert("RGB")
        fmt = QImage.Format.Format_RGB888

    channels = 4 if fmt == QImage.Format.Format_RGBA8888 else 3
    bytes_per_line = pil_image.width * channels
    data = pil_image.tobytes()
    qimage = QImage(data, pil_image.width, pil_image.height, bytes_per_line, fmt)
    # QImage はデータの参照を保持しないためコピーが必要
    return QPixmap.fromImage(qimage.copy())


class PreviewPanel(QGraphicsView):
    """QGraphicsView ベースの PDF ページプレビュー領域。

    パン（ドラッグスクロール）とフォーカス表示は View 内部で完結する。
    キーボードイベントは ``set_presenter`` で接続された Presenter メソッドへ委譲する。
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)

        self._pixmap_item: QGraphicsPixmapItem | None = None
        self._presenter: Any = None

        # パン操作を有効化
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # プレースホルダー表示
        self.show_placeholder()

    # ------------------------------------------------------------------
    # Presenter 接続
    # ------------------------------------------------------------------

    def set_presenter(self, presenter: Any) -> None:
        """Presenter を保持する。キーボードイベント委譲は keyPressEvent で行う。"""
        self._presenter = presenter

    # ------------------------------------------------------------------
    # Presenter から呼ばれる公開メソッド
    # ------------------------------------------------------------------

    @property
    def size(self) -> tuple[int, int]:
        """ビューポートの (幅, 高さ) を返す。初期化前は (500, 600) を返す。"""
        vp = self.viewport()
        w = vp.width()
        h = vp.height()
        if w <= 1 or h <= 1:
            return (500, 600)
        return (w, h)

    def display_image(
        self,
        pil_image: Image.Image,
        target_width: int,
        target_height: int,
    ) -> None:
        """PIL Image を QPixmap に変換してシーンに表示する。"""
        pixmap = _pil_to_qpixmap(pil_image)
        if target_width > 0 and target_height > 0:
            pixmap = pixmap.scaled(
                target_width,
                target_height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

        self._scene.clear()
        self._pixmap_item = self._scene.addPixmap(pixmap)
        self._pixmap_item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)

        self._scene.setSceneRect(0, 0, pixmap.width(), pixmap.height())
        self.centerOn(self._pixmap_item)

    def show_placeholder(self, text: str = "PDFを開いてください") -> None:
        """プレースホルダーテキストを表示する。"""
        self._scene.clear()
        self._pixmap_item = None
        font = make_app_font(18)
        text_item = self._scene.addText(text, font)
        text_item.setDefaultTextColor(QColor("#808080"))
        text_item.setPos(50, 50)

    def focus(self) -> None:
        """プレビューにフォーカスを設定する。"""
        self.setFocus(Qt.FocusReason.OtherFocusReason)

    # ------------------------------------------------------------------
    # キーボードイベント
    # ------------------------------------------------------------------

    def keyPressEvent(self, event) -> None:
        """キーボードイベントを Presenter に委譲する。"""
        if not self._presenter:
            super().keyPressEvent(event)
            return

        key = event.key()
        modifiers = event.modifiers()
        ctrl = bool(modifiers & Qt.KeyboardModifier.ControlModifier)
        shift = bool(modifiers & Qt.KeyboardModifier.ShiftModifier)

        handled = True

        if key == Qt.Key.Key_PageUp:
            if ctrl:
                self._presenter.prev_10_pages()
            else:
                self._presenter.prev_page()
        elif key == Qt.Key.Key_PageDown:
            if ctrl:
                self._presenter.next_10_pages()
            else:
                self._presenter.next_page()
        elif key == Qt.Key.Key_Home:
            self._presenter.go_to_first_page()
        elif key == Qt.Key.Key_End:
            self._presenter.go_to_last_page()
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if shift:
                self._presenter.execute_split()
            else:
                self._presenter.add_split_point()
        elif key == Qt.Key.Key_Delete:
            self._presenter.remove_split_point()
        elif key == Qt.Key.Key_Z:
            if shift:
                self._presenter.zoom_out()
            else:
                self._presenter.zoom_in()
        elif key == Qt.Key.Key_D:
            self._presenter.reset_zoom()
        else:
            handled = False

        if not handled:
            super().keyPressEvent(event)

    # ------------------------------------------------------------------
    # フォーカス表示
    # ------------------------------------------------------------------

    def focusInEvent(self, event) -> None:
        """フォーカス時に青い枠を表示する。"""
        self.setStyleSheet("PreviewPanel { border: 1px solid #3b82f6; }")
        super().focusInEvent(event)

    def focusOutEvent(self, event) -> None:
        """フォーカスが外れたときに枠を消す。"""
        self.setStyleSheet("")
        super().focusOutEvent(event)
