"""各種ボタン・入力エリアのコントロールウィジェット群。

NavigationBar     … ページ移動ボタン + ページ番号ラベル
SplitActionBar    … ズーム表示 + 分割点追加/消去ボタン
SectionPanel      … セクション情報・ファイル名入力・セクション間ナビゲーション
RightPanel        … PDF を開く・リセット・1 ページ分割・セクション・実行ボタン
"""

from __future__ import annotations

import tkinter as tk
from typing import Any

import customtkinter as ctk


# ======================================================================
# ナビゲーションバー（左フレーム: ページ移動）
# ======================================================================

class NavigationBar:
    """ページ移動ボタンとページ番号ラベル。"""

    def __init__(self, master: ctk.CTkFrame) -> None:
        self.frame = ctk.CTkFrame(master, fg_color="transparent")
        self.frame.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)

        self.btn_prev_10 = ctk.CTkButton(
            self.frame, text="<< -10", width=80, state="disabled",
        )
        self.btn_prev_10.grid(row=0, column=0, padx=5)

        self.btn_prev = ctk.CTkButton(
            self.frame, text="< 前のページ", state="disabled",
        )
        self.btn_prev.grid(row=0, column=1, padx=5)

        self.lbl_page_info = ctk.CTkLabel(self.frame, text="0 / 0")
        self.lbl_page_info.grid(row=0, column=2)

        self.btn_next = ctk.CTkButton(
            self.frame, text="次のページ >", state="disabled",
        )
        self.btn_next.grid(row=0, column=3, padx=5)

        self.btn_next_10 = ctk.CTkButton(
            self.frame, text="+10 >>", width=80, state="disabled",
        )
        self.btn_next_10.grid(row=0, column=4, padx=5)

    def set_presenter(self, presenter) -> None:
        self.btn_prev_10.configure(command=presenter.prev_10_pages)
        self.btn_prev.configure(command=presenter.prev_page)
        self.btn_next.configure(command=presenter.next_page)
        self.btn_next_10.configure(command=presenter.next_10_pages)

    def update(self, page_info_text: str, can_prev: bool, can_next: bool) -> None:
        self.lbl_page_info.configure(text=page_info_text)
        self.btn_prev.configure(state="normal" if can_prev else "disabled")
        self.btn_prev_10.configure(state="normal" if can_prev else "disabled")
        self.btn_next.configure(state="normal" if can_next else "disabled")
        self.btn_next_10.configure(state="normal" if can_next else "disabled")


# ======================================================================
# 分割操作バー（左フレーム: ズームラベル + 分割点ボタン）
# ======================================================================

class SplitActionBar:
    """ズーム倍率ラベルと分割点追加/消去ボタン。"""

    def __init__(self, master: ctk.CTkFrame) -> None:
        self.frame = ctk.CTkFrame(master, fg_color="transparent")
        self.frame.grid_columnconfigure(0, weight=1)
        self.frame.grid_columnconfigure(1, weight=1, uniform="split_action", minsize=260)
        self.frame.grid_columnconfigure(2, weight=1, uniform="split_action", minsize=260)
        self.frame.grid_columnconfigure(3, weight=1)

        self.lbl_zoom_info = ctk.CTkLabel(self.frame, text="倍率: 100%", anchor="w")
        self.lbl_zoom_info.grid(row=0, column=0, sticky="w", padx=(5, 10))

        self.btn_add_split = ctk.CTkButton(
            self.frame,
            text="現在のページに分割点を設定する",
            width=280,
            fg_color="#f39c12",
            hover_color="#d68910",
            text_color="#111111",
            text_color_disabled="#666666",
            state="disabled",
        )
        self.btn_add_split.grid(row=0, column=1, sticky="ew", padx=(0, 5))

        self.btn_remove_split = ctk.CTkButton(
            self.frame,
            text="現在のページの分割点を消去",
            width=280,
            fg_color="gray",
            hover_color="darkgray",
            state="disabled",
        )
        self.btn_remove_split.grid(row=0, column=2, sticky="ew")

    def set_presenter(self, presenter) -> None:
        self.btn_add_split.configure(command=presenter.add_split_point)
        self.btn_remove_split.configure(command=presenter.remove_split_point)

    def update(self, zoom_text: str, can_add: bool, can_remove: bool) -> None:
        self.lbl_zoom_info.configure(text=zoom_text)
        self.btn_add_split.configure(state="normal" if can_add else "disabled")
        self.btn_remove_split.configure(state="normal" if can_remove else "disabled")


# ======================================================================
# セクションパネル（右フレーム内: セクション情報・ファイル名・セクション移動）
# ======================================================================

class SectionPanel:
    """アクティブセクション情報の表示・ファイル名入力・セクション間ナビゲーション。"""

    def __init__(self, master: ctk.CTkFrame) -> None:
        self._presenter: Any = None

        self.frame = ctk.CTkFrame(master)
        self.frame.grid_columnconfigure(0, weight=1)

        lbl_title = ctk.CTkLabel(self.frame, text="現在のセクション:", anchor="w")
        lbl_title.grid(row=0, column=0, sticky="w", padx=5, pady=(5, 0))

        # セクション番号 + 色マーカー
        info_frame = ctk.CTkFrame(self.frame, fg_color="transparent")
        info_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=5)
        info_frame.grid_columnconfigure(1, weight=1)

        self.section_color_marker = tk.Canvas(
            info_frame, width=20, height=20, highlightthickness=0,
        )
        self.section_color_marker.grid(row=0, column=0, padx=(0, 8))

        self.lbl_section_info = ctk.CTkLabel(
            info_frame, text="- / -", anchor="w", font=ctk.CTkFont(size=14),
        )
        self.lbl_section_info.grid(row=0, column=1, sticky="w")

        # ページ範囲
        self.lbl_section_range = ctk.CTkLabel(
            self.frame, text="ページ範囲: -", anchor="w",
        )
        self.lbl_section_range.grid(row=2, column=0, sticky="w", padx=5, pady=(0, 5))

        # ファイル名入力
        lbl_filename = ctk.CTkLabel(self.frame, text="出力ファイル名:", anchor="w")
        lbl_filename.grid(row=3, column=0, sticky="w", padx=5)

        self.txt_filename = ctk.CTkEntry(
            self.frame, placeholder_text="ファイル名を入力",
        )
        self.txt_filename.grid(row=4, column=0, sticky="ew", padx=5, pady=(0, 5))

        # セクション間ナビゲーション
        nav_frame = ctk.CTkFrame(self.frame, fg_color="transparent")
        nav_frame.grid(row=5, column=0, sticky="ew", padx=5, pady=5)
        nav_frame.grid_columnconfigure((0, 1), weight=1)

        self.btn_prev_section = ctk.CTkButton(
            nav_frame, text="< 前のセクション", state="disabled",
        )
        self.btn_prev_section.grid(row=0, column=0, sticky="ew", padx=(0, 3))

        self.btn_next_section = ctk.CTkButton(
            nav_frame, text="次のセクション >", state="disabled",
        )
        self.btn_next_section.grid(row=0, column=1, sticky="ew", padx=(3, 0))

        # アクティブセクション分割点の消去
        self.btn_remove_active_split = ctk.CTkButton(
            self.frame,
            text="このセクションの開始分割点を消去",
            fg_color="gray",
            hover_color="darkgray",
            state="disabled",
        )
        self.btn_remove_active_split.grid(
            row=6, column=0, sticky="ew", padx=5, pady=(12, 5),
        )

    # ------------------------------------------------------------------
    # Presenter 接続
    # ------------------------------------------------------------------

    def set_presenter(self, presenter) -> None:
        self._presenter = presenter

        self.btn_prev_section.configure(command=presenter.prev_section)
        self.btn_next_section.configure(command=presenter.next_section)
        self.btn_remove_active_split.configure(
            command=presenter.remove_active_section_split_point,
        )

        # ファイル名入力欄のイベント
        self.txt_filename.bind("<Tab>", self._on_tab)
        self.txt_filename.bind("<Return>", self._on_return)
        self.txt_filename.bind("<KP_Enter>", self._on_return)
        self.txt_filename.bind("<Delete>", self._on_delete)
        self.txt_filename.bind("<Shift-Return>", self._on_shift_return)
        self.txt_filename.bind("<Shift-KP_Enter>", self._on_shift_return)
        self.txt_filename.bind("<FocusOut>", self._on_focus_out)

    # ------------------------------------------------------------------
    # ファイル名入力欄のイベントハンドラ
    # ------------------------------------------------------------------

    def _on_tab(self, event):
        self._presenter.save_and_advance_section()
        return "break"

    def _on_return(self, event):
        if event.state & 0x0001:  # Shift
            self._presenter.execute_split()
        else:
            self._presenter.save_and_advance_section()
        return "break"

    def _on_shift_return(self, event):
        self._presenter.execute_split()
        return "break"

    def _on_delete(self, event):
        self._presenter.remove_active_section_split_point()
        return "break"

    def _on_focus_out(self, event):
        self._presenter.save_section_filename()

    # ------------------------------------------------------------------
    # Presenter から呼ばれる公開メソッド
    # ------------------------------------------------------------------

    def get_filename(self) -> str:
        return self.txt_filename.get()

    def set_filename(self, text: str) -> None:
        current = self.txt_filename.get()
        if current != text:
            self.txt_filename.delete(0, "end")
            self.txt_filename.insert(0, text)

    def focus_and_select(self) -> None:
        """ファイル名入力欄にフォーカスを設定し全選択する。"""
        self.txt_filename.focus_set()
        self.txt_filename.select_range(0, "end")
        self.txt_filename.icursor("end")

    def update(
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
        self.lbl_section_info.configure(text=section_info_text)
        self.lbl_section_range.configure(text=section_range_text)
        self.section_color_marker.configure(bg=section_color)
        self.set_filename(section_filename)
        self.btn_prev_section.configure(
            state="normal" if can_prev_section else "disabled",
        )
        self.btn_next_section.configure(
            state="normal" if can_next_section else "disabled",
        )
        self.btn_remove_active_split.configure(
            state="normal" if can_remove_active_split else "disabled",
        )
        self.txt_filename.configure(
            state="normal" if can_edit_filename else "disabled",
        )


# ======================================================================
# 右パネル（PDF を開く・リセット・1 ページ分割・セクション・実行）
# ======================================================================

class RightPanel:
    """右側パネル全体。"""

    def __init__(self, master: ctk.CTk) -> None:
        self.frame = ctk.CTkFrame(master)
        self.frame.grid_columnconfigure(0, weight=1)
        self.frame.grid_rowconfigure(4, weight=1)

        self.btn_open = ctk.CTkButton(self.frame, text="PDFを開く")
        self.btn_open.grid(row=0, column=0, sticky="ew", padx=10, pady=10)

        self.btn_clear_split = ctk.CTkButton(
            self.frame,
            text="すべての分割点をリセット",
            fg_color="gray",
            hover_color="darkgray",
            state="disabled",
        )
        self.btn_clear_split.grid(row=2, column=0, sticky="ew", padx=10, pady=5)

        self.btn_split_every = ctk.CTkButton(
            self.frame,
            text="全体を1ページずつ分割する",
            fg_color="#b04a4a",
            hover_color="#953f3f",
            state="disabled",
        )
        self.btn_split_every.grid(row=3, column=0, sticky="ew", padx=10, pady=5)

        # セクションパネル
        self.section = SectionPanel(self.frame)
        self.section.frame.grid(
            row=4, column=0, sticky="nsew", padx=10, pady=(10, 5),
        )

        self.btn_execute = ctk.CTkButton(
            self.frame,
            text="分割を実行",
            fg_color="#2ecc71",
            hover_color="#27ae60",
            text_color="white",
            state="disabled",
        )
        self.btn_execute.grid(row=6, column=0, sticky="ew", padx=10, pady=10)

    def set_presenter(self, presenter) -> None:
        self.btn_open.configure(command=presenter.open_pdf)
        self.btn_clear_split.configure(command=presenter.clear_split_points)
        self.btn_split_every.configure(command=presenter.split_every_page)
        self.btn_execute.configure(command=presenter.execute_split)
        self.section.set_presenter(presenter)

    def update(
        self,
        can_open: bool,
        can_clear_split: bool,
        can_split_every: bool,
        can_execute: bool,
    ) -> None:
        self.btn_open.configure(state="normal" if can_open else "disabled")
        self.btn_clear_split.configure(
            state="normal" if can_clear_split else "disabled",
        )
        self.btn_split_every.configure(
            state="normal" if can_split_every else "disabled",
        )
        self.btn_execute.configure(state="normal" if can_execute else "disabled")
