"""各種ボタン・入力エリアのコントロールウィジェット群 (PySide6)。

NavigationBar     … ページ移動ボタン + ページ番号ラベル
SplitActionBar    … ズーム表示 + 分割点追加/消去ボタン
SectionPanel      … セクション情報・ファイル名入力・セクション間ナビゲーション
RightPanel        … PDF を開く・リセット・1 ページ分割・セクション・実行ボタン

Step 1.4〜1.7 で段階的に実装する。
"""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel,
    QLineEdit, QFrame, QSizePolicy,
)
from PySide6.QtGui import QColor, QPainter, QBrush, QFont
from PySide6.QtCore import Qt, QEvent

from view.font_config import make_app_font


RIGHT_PANEL_BUTTON_HEIGHT = 46
RIGHT_PANEL_PRIMARY_BUTTON_HEIGHT = 52
RIGHT_PANEL_INPUT_HEIGHT = 42
RIGHT_PANEL_LABEL_POINT_SIZE = 12
RIGHT_PANEL_TITLE_POINT_SIZE = 13
LEFT_PANEL_BUTTON_HEIGHT = 40
LEFT_PANEL_LABEL_POINT_SIZE = 12
LEFT_PANEL_BUTTON_POINT_SIZE = 11


# ======================================================================
# ナビゲーションバー（Step 1.4）
# ======================================================================

class NavigationBar(QWidget):
    """ページ移動ボタンとページ番号ラベル。

    ``set_presenter`` で Presenter を接続し、ボタン押下を委譲する。
    ``apply_state`` で UiState に基づきボタン有効/無効・ラベルテキストを更新する。
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.btn_prev_10 = QPushButton("<< -10")
        _prepare_left_button(self.btn_prev_10, min_width=92)
        self.btn_prev_10.setEnabled(False)

        self.btn_prev = QPushButton("< 前のページ")
        _prepare_left_button(self.btn_prev)
        self.btn_prev.setEnabled(False)

        self.lbl_page_info = QLabel("0 / 0")
        self.lbl_page_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        _prepare_left_label(self.lbl_page_info, bold=True)

        self.btn_next = QPushButton("次のページ >")
        _prepare_left_button(self.btn_next)
        self.btn_next.setEnabled(False)

        self.btn_next_10 = QPushButton("+10 >>")
        _prepare_left_button(self.btn_next_10, min_width=92)
        self.btn_next_10.setEnabled(False)

        for widget in (
            self.btn_prev_10, self.btn_prev,
            self.lbl_page_info,
            self.btn_next, self.btn_next_10,
        ):
            layout.addWidget(widget)

    def set_presenter(self, presenter: Any) -> None:
        """Presenter メソッドをボタンに接続する。"""
        self.btn_prev_10.clicked.connect(presenter.prev_10_pages)
        self.btn_prev.clicked.connect(presenter.prev_page)
        self.btn_next.clicked.connect(presenter.next_page)
        self.btn_next_10.clicked.connect(presenter.next_10_pages)

    def apply_state(self, page_info_text: str, can_prev: bool, can_next: bool) -> None:
        """UiState の値に基づいてラベルとボタン状態を更新する。"""
        self.lbl_page_info.setText(page_info_text)
        self.btn_prev.setEnabled(can_prev)
        self.btn_prev_10.setEnabled(can_prev)
        self.btn_next.setEnabled(can_next)
        self.btn_next_10.setEnabled(can_next)


# ======================================================================
# 分割操作バー（Step 1.6）
# ======================================================================

class SplitActionBar(QWidget):
    """ズーム倍率ラベルと分割点追加/削除ボタン。

    ``set_presenter`` で Presenter を接続し、ボタン押下を委譲する。
    ``apply_state`` でズームテキスト・ボタン有効/無効を更新する。
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.lbl_zoom_info = QLabel("倍率: 100%")
        self.lbl_zoom_info.setMinimumWidth(110)
        _prepare_left_label(self.lbl_zoom_info, bold=True)

        self.btn_add_split = QPushButton("現在のページに分割点を設定する")
        _prepare_left_button(self.btn_add_split)
        self.btn_add_split.setEnabled(False)
        self.btn_add_split.setStyleSheet(
            "QPushButton { background-color: #f39c12; color: #111; }"
            "QPushButton:disabled { background-color: #ccc; color: #666; }"
        )

        self.btn_remove_split = QPushButton("現在のページの分割点を削除")
        _prepare_left_button(self.btn_remove_split)
        self.btn_remove_split.setEnabled(False)

        layout.addWidget(self.lbl_zoom_info)
        layout.addWidget(self.btn_add_split, stretch=1)
        layout.addWidget(self.btn_remove_split, stretch=1)

    def set_presenter(self, presenter: Any) -> None:
        """Presenter メソッドをボタンに接続する。"""
        self.btn_add_split.clicked.connect(presenter.add_split_point)
        self.btn_remove_split.clicked.connect(presenter.remove_split_point)

    def apply_state(self, zoom_text: str, can_add: bool, can_remove: bool) -> None:
        """ズームラベルとボタン状態を更新する。"""
        self.lbl_zoom_info.setText(zoom_text)
        self.btn_add_split.setEnabled(can_add)
        self.btn_remove_split.setEnabled(can_remove)


# ======================================================================
# カラーマーカー（SectionPanel 内部用）
# ======================================================================

class _ColorMarker(QWidget):
    """セクション色を表示する 20x20 の小さな四角。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(20, 20)
        self._color = QColor("gray")

    def set_color(self, color_str: str) -> None:
        """表示色を変更して再描画する。"""
        self._color = QColor(color_str)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setBrush(QBrush(self._color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(self.rect())
        painter.end()


def _make_font(point_size: int, *, bold: bool = False) -> QFont:
    """右パネル用の読みやすいフォントを生成する。"""
    return make_app_font(point_size, bold=bold)


def _prepare_button(button: QPushButton, min_height: int, point_size: int) -> None:
    """ボタンの最小高さとフォントサイズを揃える。"""
    button.setMinimumHeight(min_height)
    button.setFont(_make_font(point_size, bold=True))


def _prepare_label(label: QLabel, point_size: int, *, bold: bool = False) -> None:
    """ラベルのフォントサイズを揃える。"""
    label.setFont(_make_font(point_size, bold=bold))


def _prepare_left_button(button: QPushButton, *, min_width: int | None = None) -> None:
    """左ペインのボタンサイズとフォントを揃える。"""
    button.setMinimumHeight(LEFT_PANEL_BUTTON_HEIGHT)
    button.setFont(_make_font(LEFT_PANEL_BUTTON_POINT_SIZE, bold=True))
    if min_width is not None:
        button.setMinimumWidth(min_width)


def _prepare_left_label(label: QLabel, *, bold: bool = False) -> None:
    """左ペインのラベルフォントを揃える。"""
    label.setFont(_make_font(LEFT_PANEL_LABEL_POINT_SIZE, bold=bold))


# ======================================================================
# セクションパネル（Step 1.7）
# ======================================================================

class SectionPanel(QWidget):
    """アクティブセクション情報の表示・ファイル名入力・セクション間ナビゲーション。

    ファイル名 ``QLineEdit`` には ``eventFilter`` でキーバインドを設定する:
    - Tab → 次セクション  - Enter → 保存+次  - Shift+Enter → 実行
    - Delete → 分割点削除  - FocusOut → 保存
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._presenter: Any = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # タイトル + セクション番号 + 色マーカー
        header_row = QHBoxLayout()
        header_row.setSpacing(10)
        self.lbl_section_title = QLabel("現在のセクション:")
        _prepare_label(self.lbl_section_title, RIGHT_PANEL_TITLE_POINT_SIZE, bold=True)
        self.color_marker = _ColorMarker()
        self.lbl_section_info = QLabel("- / -")
        _prepare_label(self.lbl_section_info, RIGHT_PANEL_TITLE_POINT_SIZE, bold=True)
        header_row.addWidget(self.lbl_section_title)
        header_row.addWidget(self.color_marker)
        header_row.addWidget(self.lbl_section_info, stretch=1)
        layout.addLayout(header_row)

        # ページ範囲
        self.lbl_section_range = QLabel("ページ範囲: -")
        _prepare_label(self.lbl_section_range, RIGHT_PANEL_LABEL_POINT_SIZE)
        layout.addWidget(self.lbl_section_range)

        # ファイル名入力
        filename_label = QLabel("出力ファイル名:")
        _prepare_label(filename_label, RIGHT_PANEL_LABEL_POINT_SIZE, bold=True)
        layout.addWidget(filename_label)
        self.txt_filename = QLineEdit()
        self.txt_filename.setPlaceholderText("ファイル名を入力")
        self.txt_filename.setEnabled(False)
        self.txt_filename.setMinimumHeight(RIGHT_PANEL_INPUT_HEIGHT)
        self.txt_filename.setFont(_make_font(RIGHT_PANEL_LABEL_POINT_SIZE))
        layout.addWidget(self.txt_filename)

        # セクション間ナビゲーション
        nav_row = QHBoxLayout()
        nav_row.setSpacing(8)
        self.btn_prev_section = QPushButton("< 前のセクション")
        self.btn_prev_section.setEnabled(False)
        _prepare_button(
            self.btn_prev_section,
            RIGHT_PANEL_BUTTON_HEIGHT,
            RIGHT_PANEL_LABEL_POINT_SIZE,
        )
        self.btn_next_section = QPushButton("次のセクション >")
        self.btn_next_section.setEnabled(False)
        _prepare_button(
            self.btn_next_section,
            RIGHT_PANEL_BUTTON_HEIGHT,
            RIGHT_PANEL_LABEL_POINT_SIZE,
        )
        nav_row.addWidget(self.btn_prev_section)
        nav_row.addWidget(self.btn_next_section)
        layout.addLayout(nav_row)

        # アクティブセクション分割点の削除
        self.btn_remove_active_split = QPushButton("このセクションの開始分割点を削除")
        self.btn_remove_active_split.setEnabled(False)
        _prepare_button(
            self.btn_remove_active_split,
            RIGHT_PANEL_BUTTON_HEIGHT,
            RIGHT_PANEL_LABEL_POINT_SIZE,
        )
        layout.addWidget(self.btn_remove_active_split)

        # eventFilter をファイル名入力にインストール
        self.txt_filename.installEventFilter(self)

    # ------------------------------------------------------------------
    # Presenter 接続
    # ------------------------------------------------------------------

    def set_presenter(self, presenter: Any) -> None:
        """Presenter を保持し、ボタンを接続する。"""
        self._presenter = presenter
        self.btn_prev_section.clicked.connect(presenter.prev_section)
        self.btn_next_section.clicked.connect(presenter.next_section)
        self.btn_remove_active_split.clicked.connect(
            presenter.remove_active_section_split_point,
        )

    # ------------------------------------------------------------------
    # eventFilter: ファイル名入力欄のキーバインド
    # ------------------------------------------------------------------

    def eventFilter(self, obj, event) -> bool:
        """QLineEdit のキーイベントを Presenter メソッドに委譲する。"""
        if obj is self.txt_filename and event.type() == QEvent.Type.KeyPress:
            key = event.key()
            shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)

            if key == Qt.Key.Key_Tab:
                if self._presenter:
                    self._presenter.save_and_advance_section()
                return True
            elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if self._presenter:
                    if shift:
                        self._presenter.execute_split()
                    else:
                        self._presenter.save_and_advance_section()
                return True
            elif key == Qt.Key.Key_Delete:
                if self._presenter:
                    self._presenter.remove_active_section_split_point()
                return True

        if obj is self.txt_filename and event.type() == QEvent.Type.FocusOut:
            if self._presenter:
                self._presenter.save_section_filename()

        return super().eventFilter(obj, event)

    # ------------------------------------------------------------------
    # 公開メソッド
    # ------------------------------------------------------------------

    def get_filename(self) -> str:
        """ファイル名入力欄の現在のテキストを返す。"""
        return self.txt_filename.text()

    def set_filename(self, text: str) -> None:
        """ファイル名入力欄のテキストを設定する。"""
        if self.txt_filename.text() != text:
            self.txt_filename.setText(text)

    def focus_and_select(self) -> None:
        """ファイル名入力欄にフォーカスし全選択する。"""
        self.txt_filename.setFocus(Qt.FocusReason.OtherFocusReason)
        self.txt_filename.selectAll()

    def apply_state(
        self,
        section_info_text: str,
        section_range_text: str,
        section_color: str,
        section_filename: str,
        can_prev_section: bool,
        can_next_section: bool,
        can_remove_active_split: bool,
        can_edit_filename: bool,
    ) -> None:
        """UiState の値に基づいてラベル・ボタン・入力欄を更新する。"""
        self.lbl_section_info.setText(section_info_text)
        self.lbl_section_range.setText(section_range_text)
        self.color_marker.set_color(section_color)
        self.set_filename(section_filename)
        self.btn_prev_section.setEnabled(can_prev_section)
        self.btn_next_section.setEnabled(can_next_section)
        self.btn_remove_active_split.setEnabled(can_remove_active_split)
        self.txt_filename.setEnabled(can_edit_filename)


# ======================================================================
# 右パネル（Step 1.7）
# ======================================================================

class RightPanel(QWidget):
    """右側パネル全体: PDF を開く・リセット・1 ページ分割・セクション・実行ボタン。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        self.btn_open = QPushButton("PDFを開く")
        _prepare_button(
            self.btn_open,
            RIGHT_PANEL_PRIMARY_BUTTON_HEIGHT,
            RIGHT_PANEL_TITLE_POINT_SIZE,
        )
        self.btn_open.setStyleSheet(
            "QPushButton { background-color: #bfdbfe; color: #111827; border: 1px solid #60a5fa; border-radius: 6px; }"
            "QPushButton:hover { background-color: #93c5fd; }"
            "QPushButton:pressed { background-color: #60a5fa; }"
            "QPushButton:disabled { background-color: #e5e7eb; color: #94a3b8; border: 1px solid #cbd5e1; }"
        )
        layout.addWidget(self.btn_open)

        self.btn_clear_split = QPushButton("すべての分割点をリセット")
        self.btn_clear_split.setEnabled(False)
        _prepare_button(
            self.btn_clear_split,
            RIGHT_PANEL_BUTTON_HEIGHT,
            RIGHT_PANEL_LABEL_POINT_SIZE,
        )
        layout.addWidget(self.btn_clear_split)

        self.btn_split_every = QPushButton("全体を1ページずつ分割する")
        self.btn_split_every.setEnabled(False)
        _prepare_button(
            self.btn_split_every,
            RIGHT_PANEL_BUTTON_HEIGHT,
            RIGHT_PANEL_LABEL_POINT_SIZE,
        )
        self.btn_split_every.setStyleSheet(
            "QPushButton { background-color: #b04a4a; color: white; }"
            "QPushButton:disabled { background-color: #ccc; color: #666; }"
        )
        layout.addWidget(self.btn_split_every)

        # セクションパネル
        self.section = SectionPanel()
        layout.addWidget(self.section, stretch=1)

        self.btn_execute = QPushButton("分割を実行")
        self.btn_execute.setEnabled(False)
        _prepare_button(
            self.btn_execute,
            RIGHT_PANEL_PRIMARY_BUTTON_HEIGHT,
            RIGHT_PANEL_TITLE_POINT_SIZE,
        )
        self.btn_execute.setStyleSheet(
            "QPushButton { background-color: #2ecc71; color: white; }"
            "QPushButton:disabled { background-color: #ccc; color: #666; }"
        )
        layout.addWidget(self.btn_execute)

    def set_presenter(self, presenter: Any) -> None:
        """Presenter メソッドをボタンに接続する。"""
        self.btn_open.clicked.connect(presenter.open_pdf)
        self.btn_clear_split.clicked.connect(presenter.clear_split_points)
        self.btn_split_every.clicked.connect(presenter.split_every_page)
        self.btn_execute.clicked.connect(presenter.execute_split)
        self.section.set_presenter(presenter)

    def apply_state(
        self,
        can_open: bool,
        can_clear_split: bool,
        can_split_every: bool,
        can_execute: bool,
    ) -> None:
        """ボタンの有効/無効を切り替える。"""
        self.btn_open.setEnabled(can_open)
        self.btn_clear_split.setEnabled(can_clear_split)
        self.btn_split_every.setEnabled(can_split_every)
        self.btn_execute.setEnabled(can_execute)
