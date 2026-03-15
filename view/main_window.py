"""メインウィンドウ: 全コンポーネントの組み立てと Presenter 接続 (PySide6)。

View 層の最上位モジュール。``UiState`` データクラスと ``MainWindow`` を提供する。
未実装コンポーネントは no-op スタブで吸収し、Presenter は常に動作可能な状態を保つ。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QFileDialog, QMessageBox, QFrame,
)
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtCore import QTimer
from PIL import Image

from view.components.preview import PreviewPanel
from view.components.controls import NavigationBar, SplitActionBar, RightPanel
from view.components.split_bar import SplitBar


# ======================================================================
# ViewModel
# ======================================================================

@dataclass
class UiState:
    """Presenter → View への一括 UI 更新用データ転送オブジェクト。"""

    # ページ情報
    page_info_text: str = "0 / 0"
    zoom_info_text: str = "倍率: 100%"

    # スプリットバー
    total_pages: int = 0
    current_page: int = 0
    split_points: list[int] = field(default_factory=list)
    active_section_index: int = -1

    # セクション情報
    section_info_text: str = "- / -"
    section_range_text: str = "ページ範囲: -"
    section_color: str = "gray"
    section_filename: str = ""

    # ボタン / コントロール状態 (True = 有効)
    can_prev: bool = False
    can_next: bool = False
    can_add_split: bool = False
    can_remove_split: bool = False
    can_clear_split: bool = False
    can_split_every: bool = False
    can_execute: bool = False
    can_open: bool = True
    can_prev_section: bool = False
    can_next_section: bool = False
    can_remove_active_split: bool = False
    can_edit_filename: bool = False


# ======================================================================
# メインウィンドウ
# ======================================================================

class MainWindow(QMainWindow):
    """PySide6 ベースのトップレベルウィンドウ。

    コンポーネントを組み立て、Presenter にイベント接続のインターフェースを提供する。
    ドメインロジックや状態は一切持たない。
    """

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("PDF 分割アプリケーション")
        self.resize(1000, 700)

        self._presenter: Any = None
        self._timers: dict[str, QTimer] = {}
        self._next_timer_id: int = 0

        self._build_ui()

    # ------------------------------------------------------------------
    # レイアウト構築
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """中央ウィジェットとレイアウトを構築する。"""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # 左ペイン
        left_pane = QVBoxLayout()
        self.preview = PreviewPanel()
        self.split_bar = SplitBar()
        self.split_action_bar = SplitActionBar()
        self.nav_bar = NavigationBar()
        left_pane.addWidget(self.preview, stretch=1)
        left_pane.addWidget(self.split_bar)
        left_pane.addWidget(self.split_action_bar)
        left_pane.addWidget(self.nav_bar)

        main_layout.addLayout(left_pane, stretch=7)

        self.pane_divider = QFrame()
        self.pane_divider.setFrameShape(QFrame.Shape.VLine)
        self.pane_divider.setFrameShadow(QFrame.Shadow.Sunken)
        self.pane_divider.setStyleSheet("color: #cbd5e1;")
        main_layout.addWidget(self.pane_divider)

        # 右ペイン
        self.right_panel = RightPanel()
        main_layout.addWidget(self.right_panel, stretch=3)

    # ------------------------------------------------------------------
    # Presenter 接続
    # ------------------------------------------------------------------

    def set_presenter(self, presenter: Any) -> None:
        """全コンポーネントのイベントを Presenter に接続する。"""
        self._presenter = presenter
        self.preview.set_presenter(presenter)
        self.nav_bar.set_presenter(presenter)
        self.split_action_bar.set_presenter(presenter)
        self.split_bar.set_on_page_click(presenter.go_to_page)
        self.right_panel.set_presenter(presenter)
        self._setup_shortcuts(presenter)

    def _setup_shortcuts(self, presenter: Any) -> None:
        """ウィンドウ全体のキーボードショートカットを設定する。"""
        shortcuts = [
            ("PgUp", presenter.prev_page),
            ("PgDown", presenter.next_page),
            ("Ctrl+PgUp", presenter.prev_10_pages),
            ("Ctrl+PgDown", presenter.next_10_pages),
            ("Home", presenter.go_to_first_page),
            ("End", presenter.go_to_last_page),
            ("Shift+Return", presenter.execute_split),
            ("Ctrl+Up", presenter.prev_section),
            ("Ctrl+Down", presenter.next_section),
        ]
        self._shortcuts: list[QShortcut] = []
        for key_seq, slot in shortcuts:
            sc = QShortcut(QKeySequence(key_seq), self)
            sc.activated.connect(slot)
            self._shortcuts.append(sc)

    # ------------------------------------------------------------------
    # Presenter から呼ばれる公開メソッド
    # ------------------------------------------------------------------

    def update_ui(self, state: UiState) -> None:
        """UiState に基づいて全コンポーネントの表示を一括更新する。"""
        self.nav_bar.apply_state(state.page_info_text, state.can_prev, state.can_next)
        self.split_bar.update_state(
            state.total_pages, state.current_page,
            state.split_points, state.active_section_index,
        )
        self.split_action_bar.apply_state(
            state.zoom_info_text, state.can_add_split, state.can_remove_split,
        )
        self.right_panel.apply_state(
            state.can_open, state.can_clear_split,
            state.can_split_every, state.can_execute,
        )
        self.right_panel.section.apply_state(
            state.section_info_text, state.section_range_text,
            state.section_color, state.section_filename,
            state.can_prev_section, state.can_next_section,
            state.can_remove_active_split, state.can_edit_filename,
        )

    def display_page(
        self,
        pil_image: Image.Image,
        target_width: int,
        target_height: int,
    ) -> None:
        """レンダリング済み PIL Image をプレビューに表示する。"""
        self.preview.display_image(pil_image, target_width, target_height)

    def get_preview_size(self) -> tuple[int, int]:
        """プレビュー領域の (幅, 高さ) を返す。"""
        return self.preview.size

    def get_section_filename(self) -> str:
        """セクションファイル名入力欄の現在のテキストを返す。"""
        return self.right_panel.section.get_filename()

    def set_section_filename(self, text: str) -> None:
        """セクションファイル名入力欄のテキストを設定する。"""
        self.right_panel.section.set_filename(text)

    def schedule_focus_filename_entry(self) -> None:
        """短い遅延の後、ファイル名入力欄にフォーカスし全選択する。"""
        QTimer.singleShot(10, self.right_panel.section.focus_and_select)

    # ------------------------------------------------------------------
    # ダイアログ
    # ------------------------------------------------------------------

    def show_info(self, title: str, message: str) -> None:
        """情報ダイアログを表示する。"""
        QMessageBox.information(self, title, message)

    def show_error(self, title: str, message: str) -> None:
        """エラーダイアログを表示する。"""
        QMessageBox.critical(self, title, message)

    def ask_yes_no(self, title: str, message: str) -> bool:
        """はい/いいえ確認ダイアログを表示する。"""
        result = QMessageBox.question(
            self, title, message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        return result == QMessageBox.StandardButton.Yes

    def ask_ok_cancel(self, title: str, message: str) -> bool:
        """OK/キャンセル確認ダイアログを表示する。"""
        result = QMessageBox.question(
            self, title, message,
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
        )
        return result == QMessageBox.StandardButton.Ok

    def ask_open_file(self) -> str | None:
        """ファイル選択ダイアログを表示する。"""
        path, _ = QFileDialog.getOpenFileName(
            self, "PDFファイルを選択", "", "PDF Files (*.pdf)",
        )
        return path or None

    def ask_directory(self) -> str | None:
        """ディレクトリ選択ダイアログを表示する。"""
        path = QFileDialog.getExistingDirectory(self, "保存先フォルダを選択")
        return path or None

    # ------------------------------------------------------------------
    # スケジューリング (no-op スタブ — Step 1.8 で実装)
    # ------------------------------------------------------------------

    def schedule(self, ms: int, callback: Callable) -> str:
        """指定ミリ秒後にコールバックを実行するタイマーを設定する。ジョブIDを返す。"""
        self._next_timer_id += 1
        job_id = f"timer_{self._next_timer_id}"

        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: self._on_timer_fired(job_id, callback))
        self._timers[job_id] = timer
        timer.start(ms)
        return job_id

    def cancel_schedule(self, job_id: str) -> None:
        """タイマーをキャンセルする。"""
        timer = self._timers.pop(job_id, None)
        if timer is not None:
            timer.stop()

    def _on_timer_fired(self, job_id: str, callback: Callable) -> None:
        """タイマー発火時にコールバックを呼び、タイマーを辞書から除去する。"""
        self._timers.pop(job_id, None)
        callback()

    def destroy_window(self) -> None:
        """ウィンドウを破棄する。"""
        self.close()

    # ------------------------------------------------------------------
    # closeEvent オーバーライド
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:
        """ウィンドウ閉じ操作を Presenter に委譲する。"""
        if self._presenter:
            event.ignore()
            self._presenter.on_closing()
        else:
            super().closeEvent(event)
