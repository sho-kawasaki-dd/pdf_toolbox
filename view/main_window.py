"""アプリ全体のトップレベルウィンドウ。"""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtWidgets import (
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
)
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtCore import QTimer, Qt
from PIL import Image

from view.compress.compress_view import CompressionUiState, CompressionView
from view.home_view import HomeView
from view.split.split_view import SplitView, UiState


class MainWindow(QMainWindow):
    """PySide6 ベースのトップレベルウィンドウ。

    コンポーネントを組み立て、Presenter にイベント接続のインターフェースを提供する。
    ドメインロジックや状態は一切持たない。
    """

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("PDF ツールボックス")
        self.resize(1000, 700)

        # MainWindow は状態主体ではなく、Presenter から見た UI ハブとして振る舞う。
        self._presenter: Any = None
        self._compress_presenter: Any = None
        self._close_handler: Callable[[], None] | None = None
        self._timers: dict[str, QTimer] = {}
        self._next_timer_id: int = 0
        self._shortcuts: list[QShortcut] = []

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.home_view = HomeView()
        self.split_view = SplitView()
        self.compress_view = CompressionView()
        # 画面切り替えは stacked widget へ寄せ、MainWindow 自体は
        # 「どの画面を見せるか」だけを知る構成にする。
        self.stack.addWidget(self.home_view)
        self.stack.addWidget(self.split_view)
        self.stack.addWidget(self.compress_view)
        self.stack.setCurrentWidget(self.home_view)

        self._sync_split_view_aliases()

        self._update_shortcuts_for_screen("home")

    def _sync_split_view_aliases(self) -> None:
        """既存 API 互換のため SplitView の主要コンポーネントを公開する。"""
        self.preview = self.split_view.preview
        self.split_bar = self.split_view.split_bar
        self.split_action_bar = self.split_view.split_action_bar
        self.nav_bar = self.split_view.nav_bar
        self.right_panel = self.split_view.right_panel
        self.pane_divider = self.split_view.pane_divider

    def set_presenter(self, presenter: Any) -> None:
        """分割画面のイベントを Presenter に接続する。"""
        self._presenter = presenter
        self.split_view.set_presenter(presenter)
        self._setup_shortcuts(presenter)

    def set_compress_presenter(self, presenter: Any) -> None:
        """圧縮画面のイベントを Presenter に接続する。"""
        self._compress_presenter = presenter
        self.compress_view.set_presenter(presenter)

    def set_close_handler(self, handler: Callable[[], None]) -> None:
        """ウィンドウ closeEvent の委譲先を設定する。"""
        self._close_handler = handler

    def _setup_shortcuts(self, presenter: Any) -> None:
        """分割画面表示時のみ有効なキーボードショートカットを設定する。"""
        for shortcut in self._shortcuts:
            shortcut.setParent(None)
            shortcut.deleteLater()
        self._shortcuts.clear()

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
        for key_seq, slot in shortcuts:
            sc = QShortcut(QKeySequence(key_seq), self.split_view)
            sc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            sc.activated.connect(slot)
            self._shortcuts.append(sc)

        self._update_shortcuts_for_screen("split" if self.stack.currentWidget() is self.split_view else "home")

    def _update_shortcuts_for_screen(self, screen: str) -> None:
        enabled = screen == "split"
        for shortcut in self._shortcuts:
            shortcut.setEnabled(enabled)

    def show_home(self) -> None:
        """ホーム画面へ切り替える。"""
        self.stack.setCurrentWidget(self.home_view)
        self._update_shortcuts_for_screen("home")

    def show_split(self) -> None:
        """分割画面へ切り替える。"""
        self.stack.setCurrentWidget(self.split_view)
        self._update_shortcuts_for_screen("split")

    def show_compress(self) -> None:
        """圧縮画面を表示する。"""
        self.stack.setCurrentWidget(self.compress_view)
        # 圧縮画面では分割専用ショートカットを無効にする。
        self._update_shortcuts_for_screen("home")

    def update_ui(self, state: UiState) -> None:
        self.split_view.update_ui(state)

    def display_page(
        self,
        pil_image: Image.Image,
        target_width: int,
        target_height: int,
    ) -> None:
        self.split_view.display_page(pil_image, target_width, target_height)

    def get_preview_size(self) -> tuple[int, int]:
        return self.split_view.get_preview_size()

    def get_section_filename(self) -> str:
        return self.split_view.get_section_filename()

    def set_section_filename(self, text: str) -> None:
        self.split_view.set_section_filename(text)

    def schedule_focus_filename_entry(self) -> None:
        self.split_view.schedule_focus_filename_entry()

    def update_compression_ui(self, state: CompressionUiState) -> None:
        """圧縮画面の状態を更新する。"""
        self.compress_view.update_ui(state)

    def get_selected_compression_inputs(self) -> list[str]:
        """圧縮画面で選択中の入力パス一覧を返す。"""
        return self.compress_view.get_selected_input_paths()

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

    def ask_open_files(self, title: str, file_filter: str) -> list[str]:
        """複数ファイル選択ダイアログを表示する。"""
        # 圧縮画面では PDF と ZIP の両方で複数選択が必要なため、
        # 単一ファイル用 API と分けて公開している。
        paths, _ = QFileDialog.getOpenFileNames(self, title, "", file_filter)
        return paths

    def ask_directory(self, title: str = "保存先フォルダを選択") -> str | None:
        """ディレクトリ選択ダイアログを表示する。"""
        path = QFileDialog.getExistingDirectory(self, title)
        return path or None

    # ------------------------------------------------------------------
    # スケジューリング (no-op スタブ — Step 1.8 で実装)
    # ------------------------------------------------------------------

    def schedule(self, ms: int, callback: Callable) -> str:
        """指定ミリ秒後にコールバックを実行するタイマーを設定する。ジョブIDを返す。"""
        self._next_timer_id += 1
        job_id = f"timer_{self._next_timer_id}"

        # Presenter ごとに独立したポーリングや遅延処理を持てるよう、
        # タイマーはジョブ ID で管理する。
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
        # 実際の終了口を 1 箇所にしておくと、Presenter 側は
        # 終了確認後にこのメソッドを呼ぶだけでよい。
        self.close()

    # ------------------------------------------------------------------
    # closeEvent オーバーライド
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:
        """ウィンドウ閉じ操作を Presenter に委譲する。"""
        if self._close_handler is not None:
            # 機能ごとに終了確認条件が異なるため、MainWindow 側では閉じずに委譲する。
            event.ignore()
            self._close_handler()
        elif self._presenter:
            event.ignore()
            self._presenter.on_closing()
        else:
            super().closeEvent(event)
