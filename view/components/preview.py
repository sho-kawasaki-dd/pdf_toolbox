"""PDFページプレビューキャンバスウィジェット（パン操作対応）。"""

from __future__ import annotations

import tkinter as tk

from typing import Any

import customtkinter as ctk
from PIL import Image, ImageTk


class PreviewPanel:
    """Canvas ベースの PDF ページプレビュー領域。

    パン（ドラッグスクロール）とフォーカス表示は View 内部で完結する。
    キーボードイベントは ``set_presenter`` で接続された Presenter メソッドへ委譲する。
    """

    def __init__(self, master: ctk.CTkFrame) -> None:
        # 外枠フレーム
        self.frame = ctk.CTkFrame(master)
        self.frame.grid_rowconfigure(0, weight=1)
        self.frame.grid_columnconfigure(0, weight=1)

        # プレビューキャンバス
        self.canvas = tk.Canvas(self.frame, highlightthickness=0, takefocus=1)
        self.canvas.grid(row=0, column=0, sticky="nsew")

        self._image_tk: ImageTk.PhotoImage | None = None
        self._can_pan: bool = False
        self._presenter: Any = None

        # プレースホルダー
        self.canvas.create_text(
            250, 300,
            text="PDFを開いてください",
            fill="#808080",
            font=("Segoe UI", 16),
        )

        # マウスイベント（View 内部で完結）
        self.canvas.bind("<Button-1>", self._on_mouse_down)
        self.canvas.bind("<B1-Motion>", self._on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_mouse_up)
        self.canvas.bind("<Enter>", self._on_mouse_enter)
        self.canvas.bind("<Leave>", self._on_mouse_leave)
        self.canvas.bind("<FocusIn>", self._on_focus_in)
        self.canvas.bind("<FocusOut>", self._on_focus_out)

    # ------------------------------------------------------------------
    # Presenter 接続
    # ------------------------------------------------------------------

    def set_presenter(self, presenter) -> None:
        """キーボードイベントを Presenter メソッドへバインドする。"""
        self._presenter = presenter
        c = self.canvas

        # ページナビゲーション
        c.bind("<Prior>", self._wrap(presenter.prev_page))
        c.bind("<Next>", self._wrap(presenter.next_page))
        c.bind("<Control-Prior>", self._wrap(presenter.prev_10_pages))
        c.bind("<Control-Next>", self._wrap(presenter.next_10_pages))
        c.bind("<Home>", self._wrap(presenter.go_to_first_page))
        c.bind("<End>", self._wrap(presenter.go_to_last_page))

        # 分割操作
        c.bind("<Return>", self._on_enter_key)
        c.bind("<KP_Enter>", self._on_enter_key)
        c.bind("<Delete>", self._wrap(presenter.remove_split_point))
        c.bind("<Shift-Return>", self._wrap(presenter.execute_split))
        c.bind("<Shift-KP_Enter>", self._wrap(presenter.execute_split))

        # ズーム
        c.bind("<z>", self._wrap(presenter.zoom_in))
        c.bind("<Z>", self._wrap(presenter.zoom_out))
        c.bind("<d>", self._wrap(presenter.reset_zoom))

    # ------------------------------------------------------------------
    # Presenter から呼ばれる公開メソッド
    # ------------------------------------------------------------------

    @property
    def size(self) -> tuple[int, int]:
        """キャンバスの (幅, 高さ) を返す。初期化前は (500, 600) を返す。"""
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w <= 1 or h <= 1:
            return (500, 600)
        return (w, h)

    def display_image(
        self,
        pil_image: Image.Image,
        target_width: int,
        target_height: int,
    ) -> None:
        """PIL Image を ImageTk に変換してキャンバスに表示する。"""
        self._image_tk = ImageTk.PhotoImage(pil_image)

        frame_w, frame_h = self.size
        self.canvas.delete("all")

        image_x = max((frame_w - target_width) // 2, 0)
        image_y = max((frame_h - target_height) // 2, 0)
        self.canvas.create_image(image_x, image_y, anchor="nw", image=self._image_tk)

        scroll_w = max(frame_w, target_width)
        scroll_h = max(frame_h, target_height)
        self.canvas.configure(scrollregion=(0, 0, scroll_w, scroll_h))
        self.canvas.xview_moveto(0)
        self.canvas.yview_moveto(0)

        self._can_pan = target_width > frame_w or target_height > frame_h
        self._update_cursor()

    def show_placeholder(self, text: str = "PDFを開いてください") -> None:
        """プレースホルダーテキストを表示する。"""
        self.canvas.delete("all")
        self._image_tk = None
        self._can_pan = False
        self.canvas.create_text(
            250, 300, text=text, fill="#808080", font=("Segoe UI", 16),
        )

    def focus(self) -> None:
        """プレビューキャンバスにフォーカスを設定する。"""
        self.canvas.focus_set()

    # ------------------------------------------------------------------
    # 内部イベントハンドラ
    # ------------------------------------------------------------------

    @staticmethod
    def _wrap(callback):
        """callback を呼び出して 'break' を返す Tk イベントハンドラを生成する。"""
        def handler(event):
            callback()
            return "break"
        return handler

    def _on_enter_key(self, event):
        if not self._presenter:
            return "break"
        if event.state & 0x0001:  # Shift
            self._presenter.execute_split()
        else:
            self._presenter.add_split_point()
        return "break"

    def _on_mouse_down(self, event):
        self.canvas.focus_set()
        if self._can_pan:
            self.canvas.scan_mark(event.x, event.y)
            self.canvas.configure(cursor="fleur")

    def _on_mouse_drag(self, event):
        if self._can_pan:
            self.canvas.scan_dragto(event.x, event.y, gain=1)
        return "break"

    def _on_mouse_up(self, event):
        self._update_cursor()

    def _on_mouse_enter(self, event):
        self._update_cursor()

    def _on_mouse_leave(self, event):
        self.canvas.configure(cursor="")

    def _on_focus_in(self, event):
        self.canvas.configure(
            highlightthickness=1,
            highlightbackground="#3b82f6",
            highlightcolor="#3b82f6",
        )

    def _on_focus_out(self, event):
        self.canvas.configure(highlightthickness=0)

    def _update_cursor(self):
        cursor = "hand2" if self._can_pan else ""
        self.canvas.configure(cursor=cursor)
