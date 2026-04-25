from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from view.font_config import make_app_font


@dataclass(slots=True)
class FlattenInputItem:
    """入力一覧 1 行ぶんの表示データ。"""

    path: str
    label: str


@dataclass(slots=True)
class FlattenUiState:
    """FlattenView を 1 回で描画更新するための状態スナップショット。"""

    input_items: list[FlattenInputItem] = field(default_factory=list)
    progress_text: str = "待機中"
    summary_text: str = "成功: 0件 / 失敗: 0件 / スキップ: 0件"
    progress_value: int = 0
    can_add_inputs: bool = True
    can_remove_selected: bool = False
    can_clear_inputs: bool = False
    can_execute: bool = False
    can_back_home: bool = True
    is_running: bool = False


class DroppableInputList(QListWidget):
    """ローカルファイルやフォルダの DnD を Presenter へ中継する一覧。"""

    paths_dropped = Signal(list)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setAlternatingRowColors(True)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:
        if not event.mimeData().hasUrls():
            super().dropEvent(event)
            return

        paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        if paths:
            self.paths_dropped.emit(paths)
            event.acceptProposedAction()
            return

        super().dropEvent(event)


class FlattenView(QWidget):
    """PDF フラット化画面のウィジェット構築と表示更新を担う。"""

    back_to_home_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._can_remove_selected = False
        self._build_ui()
        self.update_ui(FlattenUiState())

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(16)

        header = QHBoxLayout()
        header.setSpacing(12)
        self.btn_back_home = QPushButton("← ホーム")
        self.btn_back_home.setMinimumHeight(40)
        self.btn_back_home.clicked.connect(
            lambda checked=False: self.back_to_home_requested.emit(),
        )
        header.addWidget(self.btn_back_home, stretch=0)

        title_box = QVBoxLayout()
        title = QLabel("PDF フラット化")
        title.setFont(make_app_font(24, bold=True))
        subtitle = QLabel("複数PDF / フォルダ / DnD に対応した一括フラット化")
        subtitle.setFont(make_app_font(13))
        subtitle.setStyleSheet("color: #475569;")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box, stretch=1)
        root.addLayout(header)

        body = QGridLayout()
        body.setHorizontalSpacing(16)
        body.setVerticalSpacing(16)
        body.setColumnStretch(0, 5)
        body.setColumnStretch(1, 4)
        root.addLayout(body, stretch=1)

        self.input_group = QGroupBox("入力ソース")
        input_layout = QVBoxLayout(self.input_group)
        input_layout.setSpacing(12)

        input_buttons = QHBoxLayout()
        input_buttons.setSpacing(8)
        self.btn_add_pdf = QPushButton("PDF追加")
        self.btn_add_folder = QPushButton("フォルダ追加")
        self.btn_remove_selected = QPushButton("選択削除")
        self.btn_clear = QPushButton("一覧クリア")
        for button in (
            self.btn_add_pdf,
            self.btn_add_folder,
            self.btn_remove_selected,
            self.btn_clear,
        ):
            button.setMinimumHeight(38)
            input_buttons.addWidget(button)
        input_layout.addLayout(input_buttons)

        self.lbl_drop_hint = QLabel("PDF / フォルダをこの一覧へドラッグ&ドロップできます")
        self.lbl_drop_hint.setFont(make_app_font(12))
        self.lbl_drop_hint.setStyleSheet("color: #64748b;")
        input_layout.addWidget(self.lbl_drop_hint)

        self.input_list = DroppableInputList()
        self.input_list.setObjectName("flatten_input_list")
        self.input_list.itemSelectionChanged.connect(self._update_selection_buttons)
        input_layout.addWidget(self.input_list, stretch=1)
        body.addWidget(self.input_group, 0, 0)

        self.progress_group = QGroupBox("進捗")
        progress_layout = QVBoxLayout(self.progress_group)
        progress_layout.setSpacing(12)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar)

        self.lbl_progress = QLabel("待機中")
        self.lbl_progress.setFont(make_app_font(12, bold=True))
        self.lbl_summary = QLabel("成功: 0件 / 失敗: 0件 / スキップ: 0件")
        self.lbl_summary.setFont(make_app_font(11))
        self.lbl_summary.setWordWrap(True)
        progress_layout.addWidget(self.lbl_progress)
        progress_layout.addWidget(self.lbl_summary)

        self.btn_execute = QPushButton("フラット化を実行")
        self.btn_execute.setMinimumHeight(48)
        self.btn_execute.setFont(make_app_font(16, bold=True))
        self.btn_execute.setStyleSheet(
            "QPushButton { background-color: #0f766e; color: white; border-radius: 8px; }"
            "QPushButton:disabled { background-color: #94a3b8; color: #e2e8f0; }"
        )
        progress_layout.addWidget(self.btn_execute)
        progress_layout.addStretch(1)
        body.addWidget(self.progress_group, 0, 1)

    def set_presenter(self, presenter: Any) -> None:
        self.btn_add_pdf.clicked.connect(presenter.add_pdf_files)
        self.btn_add_folder.clicked.connect(presenter.add_folder)
        self.btn_remove_selected.clicked.connect(presenter.remove_selected_inputs)
        self.btn_clear.clicked.connect(presenter.clear_inputs)
        self.btn_execute.clicked.connect(presenter.execute_flatten)
        self.input_list.paths_dropped.connect(presenter.handle_dropped_paths)

    def update_ui(self, state: FlattenUiState) -> None:
        self.input_list.clear()
        for item_state in state.input_items:
            item = QListWidgetItem(item_state.label)
            item.setData(Qt.ItemDataRole.UserRole, item_state.path)
            self.input_list.addItem(item)

        self.progress_bar.setValue(state.progress_value)
        self.lbl_progress.setText(state.progress_text)
        self.lbl_summary.setText(state.summary_text)

        self._can_remove_selected = state.can_remove_selected
        self.btn_add_pdf.setEnabled(state.can_add_inputs)
        self.btn_add_folder.setEnabled(state.can_add_inputs)
        self.btn_clear.setEnabled(state.can_clear_inputs)
        self.btn_execute.setEnabled(state.can_execute)
        self.btn_back_home.setEnabled(state.can_back_home)
        self.input_list.setAcceptDrops(not state.is_running)

        self._update_selection_buttons()

    def get_selected_input_paths(self) -> list[str]:
        return [item.data(Qt.ItemDataRole.UserRole) for item in self.input_list.selectedItems()]

    def _update_selection_buttons(self) -> None:
        has_selection = bool(self.input_list.selectedItems())
        self.btn_remove_selected.setEnabled(self._can_remove_selected and has_selection)