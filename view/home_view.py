"""PDF ツールの機能カードを並べるホーム画面。"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QGridLayout, QLabel, QSizePolicy, QToolButton, QVBoxLayout, QWidget

from view.font_config import make_app_font


FEATURE_CARD_ICON_SIZE = 156
FEATURE_CARD_MIN_WIDTH = 250

FEATURES: tuple[tuple[str, str, str, bool], ...] = (
    ("split", "pdf_splitter_icon.png", "PDF 分割", True),
    ("merge", "pdf_merger_icon.png", "PDF 結合", False),
    ("reorder", "pdf_page_reorder_icon.png", "PDF 並び替え", False),
    ("compress", "pdf_compressor_icon.png", "PDF 圧縮", True),
    ("pdf-to-jpeg", "pdf2jpeg_icon.png", "PDF → JPEG", False),
)


def _resource_path(relative_path: str) -> Path:
    """開発実行と PyInstaller 実行の両方で使えるリソースパスを返す。"""
    base_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base_dir / relative_path


class FeatureCardButton(QToolButton):
    """縦長カード比率を保つホーム画面用ボタン。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.setIconSize(QSize(FEATURE_CARD_ICON_SIZE, FEATURE_CARD_ICON_SIZE))
        self.setMinimumWidth(FEATURE_CARD_MIN_WIDTH)
        self.setMinimumHeight(self.heightForWidth(FEATURE_CARD_MIN_WIDTH))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setFont(make_app_font(18, bold=True))

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return max(280, int(width * 1.12))

    def sizeHint(self):
        width = max(FEATURE_CARD_MIN_WIDTH, super().sizeHint().width())
        return QSize(width, self.heightForWidth(width))


class HomeView(QWidget):
    """利用可能な機能カードを並べて選択イベントを出す画面。"""

    feature_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.feature_buttons: dict[str, QPushButton] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        """ホーム画面のタイトルと機能カード一覧を構築する。"""
        outer = QVBoxLayout(self)
        outer.setContentsMargins(32, 32, 32, 32)
        outer.setSpacing(20)

        title = QLabel("PDF ツールボックス")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(make_app_font(28, bold=True))
        outer.addWidget(title)

        subtitle = QLabel("使いたい機能を選択してください")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setFont(make_app_font(14))
        subtitle.setStyleSheet("color: #475569;")
        outer.addWidget(subtitle)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(16)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 1)
        outer.addLayout(grid)
        outer.addStretch(1)

        # 機能定義テーブルからカードを生成し、表示順と有効/無効を一元管理する。
        for index, (feature, icon_name, title, enabled) in enumerate(FEATURES):
            row, column = divmod(index, 3)
            self._add_card(grid, row, column, feature, icon_name, title, enabled)

    def _add_card(
        self,
        grid: QGridLayout,
        row: int,
        column: int,
        feature: str,
        icon_name: str,
        title: str,
        enabled: bool,
    ) -> None:
        """1 枚ぶんの機能カードを生成してグリッドへ配置する。"""
        button = FeatureCardButton()
        button.setObjectName(f"{feature}_card")
        button.setText(title if enabled else f"{title}\n準備中")
        button.setIcon(self._load_feature_icon(icon_name))
        button.setEnabled(enabled)
        button.setCursor(
            Qt.CursorShape.PointingHandCursor if enabled else Qt.CursorShape.ArrowCursor,
        )
        button.setStyleSheet(
            "QToolButton {"
            " background-color: #f8fafc;"
            " border: 1px solid #cbd5e1;"
            " border-radius: 14px;"
            " padding: 18px 14px 20px 14px;"
            " color: #0f172a;"
            " qproperty-toolButtonStyle: ToolButtonTextUnderIcon;"
            "}"
            "QToolButton:hover:enabled { background-color: #e2e8f0; border-color: #94a3b8; }"
            "QToolButton:pressed:enabled { background-color: #dbeafe; }"
            "QToolButton:disabled { color: #94a3b8; background-color: #f1f5f9; }"
        )
        if enabled:
            # どのカードが押されたかだけを外へ出し、画面遷移判断は Coordinator に任せる。
            button.clicked.connect(lambda checked=False, name=feature: self.feature_selected.emit(name))
        self.feature_buttons[feature] = button
        grid.addWidget(button, row, column)

    def _load_feature_icon(self, icon_name: str) -> QIcon:
        icon_path = _resource_path(f"assets/images/{icon_name}")
        return QIcon(str(icon_path)) if icon_path.exists() else QIcon()
