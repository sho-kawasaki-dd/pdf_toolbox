"""色分けされた分割プログレスバーウィジェット。"""

from __future__ import annotations

import tkinter as tk

import customtkinter as ctk

SECTION_COLORS: list[str] = [
    "#3498db",
    "#e74c3c",
    "#2ecc71",
    "#f39c12",
    "#9b59b6",
    "#1abc9c",
]


class CustomSplitBar(tk.Canvas):
    """標準の tk.Canvas を使って色分けされたバーを描画する。"""

    def __init__(self, master: ctk.CTkFrame, **kwargs) -> None:
        bg_color = master.cget("fg_color")
        if isinstance(bg_color, (tuple, list)):
            mode = ctk.get_appearance_mode()
            bg_color = bg_color[0] if mode == "Light" else bg_color[1]

        super().__init__(master, height=30, bg=bg_color, highlightthickness=0, **kwargs)

        self.total_pages: int = 0
        self.current_page: int = 0
        self.split_points: list[int] = []
        self.active_section_index: int = -1
        self._on_page_click = None  # set via set_on_page_click

        self.bind("<Configure>", self._on_resize)
        self.bind("<Button-1>", self._on_click)
        self.bind("<B1-Motion>", self._on_drag)

    # ------------------------------------------------------------------
    # 公開メソッド
    # ------------------------------------------------------------------

    def set_on_page_click(self, callback) -> None:
        """ページクリック時のコールバックを設定する。"""
        self._on_page_click = callback

    def update_state(
        self,
        total: int,
        current: int,
        splits: list[int],
        active_section_index: int = -1,
    ) -> None:
        self.total_pages = total
        self.current_page = current
        self.split_points = sorted(splits)
        self.active_section_index = active_section_index
        self._draw()

    # ------------------------------------------------------------------
    # イベントハンドラ
    # ------------------------------------------------------------------

    def _on_resize(self, event) -> None:
        self._draw()

    def _event_to_page(self, event) -> int | None:
        if self.total_pages <= 0:
            return None
        width = self.winfo_width()
        if width <= 1:
            return None
        x_pos = min(max(event.x, 0), width - 1)
        target_page = int((x_pos / width) * self.total_pages)
        return min(max(target_page, 0), self.total_pages - 1)

    def _on_click(self, event) -> None:
        page = self._event_to_page(event)
        if page is not None and self._on_page_click:
            self._on_page_click(page)

    def _on_drag(self, event) -> None:
        page = self._event_to_page(event)
        if page is not None and self._on_page_click:
            self._on_page_click(page)

    # ------------------------------------------------------------------
    # 描画
    # ------------------------------------------------------------------

    def _draw(self) -> None:
        self.delete("all")
        if self.total_pages <= 0:
            return

        width = self.winfo_width()
        height = self.winfo_height()
        if width <= 1:
            return

        page_width = width / self.total_pages

        # 1. 分割範囲ごとの色分け描画
        start_page = 0
        color_idx = 0
        points = self.split_points + [self.total_pages]
        for point in points:
            if point <= start_page:
                continue
            x_start = start_page * page_width
            x_end = point * page_width
            color = SECTION_COLORS[color_idx % len(SECTION_COLORS)]
            self.create_rectangle(x_start, 0, x_end, height, fill=color, outline="")
            start_page = point
            color_idx += 1

        # 2. 分割線の描画
        for point in self.split_points:
            x_pos = point * page_width
            self.create_line(x_pos, 0, x_pos, height, fill="black", width=2)

        # 3. アクティブセクションの白枠ハイライト
        if self.active_section_index >= 0:
            boundaries = [0] + self.split_points + [self.total_pages]
            if self.active_section_index < len(boundaries) - 1:
                sec_start = boundaries[self.active_section_index]
                sec_end = boundaries[self.active_section_index + 1]
                x_s = sec_start * page_width
                x_e = sec_end * page_width
                self.create_rectangle(
                    x_s + 1, 1, x_e - 1, height - 1,
                    fill="", outline="white", width=2,
                )

        # 4. 現在位置のインジケーター（逆三角形）
        cx = (self.current_page + 0.5) * page_width
        self.create_polygon(
            cx - 6, 0, cx + 6, 0, cx, 10,
            fill="white", outline="black",
        )
