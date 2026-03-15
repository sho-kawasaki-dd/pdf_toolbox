"""メインウィンドウ: 全コンポーネントの組み立てと Presenter 接続。

View 層の最上位モジュール。``UiState`` データクラスと ``MainWindow`` を提供する。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image

from view.components.split_bar import CustomSplitBar
from view.components.preview import PreviewPanel
from view.components.controls import NavigationBar, SplitActionBar, RightPanel

# CustomTkinter の全体設定
ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")


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

class MainWindow(ctk.CTk):
    """CustomTkinter ベースのトップレベルウィンドウ。

    コンポーネントを組み立て、Presenter にイベント接続のインターフェースを提供する。
    ドメインロジックや状態は一切持たない。
    """

    def __init__(self) -> None:
        super().__init__()
        self.title("PDF 分割アプリケーション (CustomTkinter)")
        self.geometry("1000x700")

        self._presenter = None

        self.grid_columnconfigure(0, weight=7)
        self.grid_columnconfigure(1, weight=3)
        self.grid_rowconfigure(0, weight=1)

        self._build_left_frame()
        self._build_right_frame()

    # ------------------------------------------------------------------
    # レイアウト構築
    # ------------------------------------------------------------------

    def _build_left_frame(self) -> None:
        left = ctk.CTkFrame(self)
        left.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        left.grid_rowconfigure(0, weight=1)
        left.grid_columnconfigure(0, weight=1)

        self.preview = PreviewPanel(left)
        self.preview.frame.grid(row=0, column=0, sticky="nsew", pady=(0, 10))

        self.split_bar = CustomSplitBar(left)
        self.split_bar.grid(row=1, column=0, sticky="ew", pady=(0, 10))

        self.navigation = NavigationBar(left)
        self.navigation.frame.grid(row=2, column=0, sticky="ew")

        self.split_action = SplitActionBar(left)
        self.split_action.frame.grid(row=3, column=0, sticky="ew", pady=(10, 10))

    def _build_right_frame(self) -> None:
        self.right_panel = RightPanel(self)
        self.right_panel.frame.grid(
            row=0, column=1, sticky="nsew", padx=(0, 10), pady=10,
        )

    # ------------------------------------------------------------------
    # Presenter 接続
    # ------------------------------------------------------------------

    def set_presenter(self, presenter) -> None:
        """全コンポーネントのイベントを Presenter に接続する。"""
        self._presenter = presenter
        self.protocol("WM_DELETE_WINDOW", presenter.on_closing)

        self.preview.set_presenter(presenter)
        self.split_bar.set_on_page_click(presenter.go_to_page)
        self.navigation.set_presenter(presenter)
        self.split_action.set_presenter(presenter)
        self.right_panel.set_presenter(presenter)

        # グローバルキーバインド
        self.bind_all("<Shift-Return>", self._wrap(presenter.execute_split))
        self.bind_all("<Shift-KP_Enter>", self._wrap(presenter.execute_split))
        self.bind_all("<Control-Up>", self._wrap(presenter.prev_section))
        self.bind_all("<Control-Down>", self._wrap(presenter.next_section))
        self.bind_all("<Control-KP_Up>", self._wrap(presenter.prev_section))
        self.bind_all("<Control-KP_Down>", self._wrap(presenter.next_section))

    @staticmethod
    def _wrap(callback):
        """callback を呼んで 'break' を返す Tk イベントハンドラを生成する。"""
        def handler(event):
            callback()
            return "break"
        return handler

    # ------------------------------------------------------------------
    # Presenter から呼ばれる公開メソッド
    # ------------------------------------------------------------------

    def update_ui(self, state: UiState) -> None:
        """UiState に基づいて全コンポーネントの表示を一括更新する。"""
        self.split_bar.update_state(
            state.total_pages,
            state.current_page,
            state.split_points,
            state.active_section_index,
        )
        self.navigation.update(
            state.page_info_text,
            state.can_prev,
            state.can_next,
        )
        self.split_action.update(
            state.zoom_info_text,
            state.can_add_split,
            state.can_remove_split,
        )
        self.right_panel.update(
            state.can_open,
            state.can_clear_split,
            state.can_split_every,
            state.can_execute,
        )
        self.right_panel.section.update(
            state.section_info_text,
            state.section_range_text,
            state.section_color,
            state.section_filename,
            state.can_prev_section,
            state.can_next_section,
            state.can_remove_active_split,
            state.can_edit_filename,
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
        self.after(10, self.right_panel.section.focus_and_select)

    # ------------------------------------------------------------------
    # ダイアログ
    # ------------------------------------------------------------------

    def show_info(self, title: str, message: str) -> None:
        messagebox.showinfo(title, message)

    def show_error(self, title: str, message: str) -> None:
        messagebox.showerror(title, message)

    def ask_yes_no(self, title: str, message: str) -> bool:
        return messagebox.askyesno(title, message)

    def ask_ok_cancel(self, title: str, message: str) -> bool:
        return messagebox.askokcancel(title, message)

    def ask_open_file(self) -> str | None:
        path = filedialog.askopenfilename(
            title="PDFファイルを選択",
            filetypes=[("PDF Files", "*.pdf")],
        )
        return path or None

    def ask_directory(self) -> str | None:
        path = filedialog.askdirectory(title="保存先フォルダを選択")
        return path or None

    # ------------------------------------------------------------------
    # スケジューリング
    # ------------------------------------------------------------------

    def schedule(self, ms: int, callback) -> str:
        """``self.after`` のラッパー。ジョブ ID を返す。"""
        return self.after(ms, callback)

    def cancel_schedule(self, job_id: str) -> None:
        """``self.after_cancel`` のラッパー。"""
        try:
            self.after_cancel(job_id)
        except Exception:
            pass

    def destroy_window(self) -> None:
        """ウィンドウを破棄する。"""
        self.destroy()
