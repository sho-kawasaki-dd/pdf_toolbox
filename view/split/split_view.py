"""Split feature screen and UI state DTO."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from PIL import Image
from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from view.split.components.controls import NavigationBar, RightPanel, SplitActionBar
from view.split.components.preview import PreviewPanel
from view.split.components.split_bar import SplitBar


@dataclass
class UiState:
    """Presenter -> View batch update DTO."""

    page_info_text: str = "0 / 0"
    zoom_info_text: str = "倍率: 100%"

    total_pages: int = 0
    current_page: int = 0
    split_points: list[int] = field(default_factory=list)
    active_section_index: int = -1

    section_info_text: str = "- / -"
    section_range_text: str = "ページ範囲: -"
    section_color: str = "gray"
    section_filename: str = ""

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


class SplitView(QWidget):
    """Split feature screen composed from split-specific widgets."""

    back_to_home_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

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

        right_pane = QVBoxLayout()
        right_pane.setContentsMargins(0, 0, 0, 0)
        right_pane.setSpacing(10)

        self.btn_back_home = QPushButton("← ホーム")
        self.btn_back_home.setMinimumHeight(40)
        self.btn_back_home.clicked.connect(
            lambda checked=False: self.back_to_home_requested.emit(),
        )
        right_pane.addWidget(self.btn_back_home)

        self.right_panel = RightPanel()
        right_pane.addWidget(self.right_panel, stretch=1)
        main_layout.addLayout(right_pane, stretch=3)

    def set_presenter(self, presenter: Any) -> None:
        self.preview.set_presenter(presenter)
        self.nav_bar.set_presenter(presenter)
        self.split_action_bar.set_presenter(presenter)
        self.split_bar.set_on_page_click(presenter.go_to_page)
        self.right_panel.set_presenter(presenter)

    def update_ui(self, state: UiState) -> None:
        self.nav_bar.apply_state(state.page_info_text, state.can_prev, state.can_next)
        self.split_bar.update_state(
            state.total_pages,
            state.current_page,
            state.split_points,
            state.active_section_index,
        )
        self.split_action_bar.apply_state(
            state.zoom_info_text,
            state.can_add_split,
            state.can_remove_split,
        )
        self.right_panel.apply_state(
            state.can_open,
            state.can_clear_split,
            state.can_split_every,
            state.can_execute,
        )
        self.right_panel.section.apply_state(
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
        self.preview.display_image(pil_image, target_width, target_height)

    def get_preview_size(self) -> tuple[int, int]:
        return self.preview.size

    def get_section_filename(self) -> str:
        return self.right_panel.section.get_filename()

    def set_section_filename(self, text: str) -> None:
        self.right_panel.section.set_filename(text)

    def schedule_focus_filename_entry(self) -> None:
        QTimer.singleShot(10, self.right_panel.section.focus_and_select)
