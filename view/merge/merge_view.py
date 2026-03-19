from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from view.font_config import make_app_font


@dataclass(slots=True)
class MergeInputItem:
    """入力一覧 1 行ぶんの表示データ。"""

    path: str
    title: str
    detail: str
    thumbnail_text: str = "サムネイル\n準備中"
    thumbnail_status: str = "idle"
    thumbnail_png_bytes: bytes | None = None


@dataclass(slots=True)
class MergeUiState:
    """MergeView を 1 回で描画更新するための状態スナップショット。"""

    input_items: list[MergeInputItem] = field(default_factory=list)
    selected_paths: list[str] = field(default_factory=list)
    output_path_text: str = "結合後PDFの保存先を選択してください"
    progress_text: str = "待機中"
    progress_value: int = 0
    can_add_inputs: bool = True
    can_remove_selected: bool = False
    can_move_up: bool = False
    can_move_down: bool = False
    can_choose_output: bool = True
    can_execute: bool = False
    can_back_home: bool = True
    is_running: bool = False


class MergeInputList(QListWidget):
    """外部 DnD と内部並び替えを Presenter へ中継する一覧。"""

    paths_dropped = Signal(list)
    order_changed = Signal(list)
    selection_paths_changed = Signal(list)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setAlternatingRowColors(True)
        self.itemSelectionChanged.connect(self._emit_selection_paths)

    def dragEnterEvent(self, event) -> None:
        if event.source() is self or event.mimeData().hasUrls():
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:
        if event.source() is self or event.mimeData().hasUrls():
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:
        if event.source() is self:
            super().dropEvent(event)
            self.order_changed.emit(self.current_paths())
            return

        if not event.mimeData().hasUrls():
            super().dropEvent(event)
            return

        paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        if paths:
            self.paths_dropped.emit(paths)
            event.acceptProposedAction()
            return

        super().dropEvent(event)

    def current_paths(self) -> list[str]:
        return [self.item(index).data(Qt.ItemDataRole.UserRole) for index in range(self.count())]

    def selected_paths(self) -> list[str]:
        return [item.data(Qt.ItemDataRole.UserRole) for item in self.selectedItems()]

    def _emit_selection_paths(self) -> None:
        self.selection_paths_changed.emit(self.selected_paths())


class MergeInputRow(QWidget):
    """サムネイル欄を含む入力一覧の行ウィジェット。"""

    def __init__(self, item: MergeInputItem, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        root = QHBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(12)

        self.thumbnail_label = QLabel(item.thumbnail_text)
        self.thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumbnail_label.setFixedSize(72, 96)
        self.thumbnail_label.setStyleSheet(
            "QLabel {"
            " background-color: #e2e8f0;"
            " border: 1px solid #cbd5e1;"
            " border-radius: 8px;"
            " color: #475569;"
            "}"
        )
        self.thumbnail_label.setFont(make_app_font(10))
        self._apply_thumbnail(item)
        root.addWidget(self.thumbnail_label, stretch=0)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)
        self.title_label = QLabel(item.title)
        self.title_label.setFont(make_app_font(12, bold=True))
        self.detail_label = QLabel(item.detail)
        self.detail_label.setWordWrap(True)
        self.detail_label.setStyleSheet("color: #64748b;")
        self.detail_label.setFont(make_app_font(10))
        text_layout.addWidget(self.title_label)
        text_layout.addWidget(self.detail_label)
        root.addLayout(text_layout, stretch=1)

    def _apply_thumbnail(self, item: MergeInputItem) -> None:
        if item.thumbnail_png_bytes:
            pixmap = QPixmap()
            if pixmap.loadFromData(item.thumbnail_png_bytes):
                scaled = pixmap.scaled(
                    self.thumbnail_label.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self.thumbnail_label.setPixmap(scaled)
                self.thumbnail_label.setText("")
                return

        self.thumbnail_label.setPixmap(QPixmap())
        self.thumbnail_label.setText(item.thumbnail_text)


class MergeView(QWidget):
    """PDF 結合画面のウィジェット構築と表示更新を担う。"""

    back_to_home_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._can_remove_selected = False
        self._can_move_up = False
        self._can_move_down = False
        self._build_ui()

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
        title = QLabel("PDF 結合")
        title.setFont(make_app_font(24, bold=True))
        subtitle = QLabel("複数PDFを並び替えて 1 つのPDFへまとめます")
        subtitle.setFont(make_app_font(13))
        subtitle.setStyleSheet("color: #475569;")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box, stretch=1)
        root.addLayout(header)

        self.inputs_group = QGroupBox("入力PDF")
        inputs_layout = QVBoxLayout(self.inputs_group)
        inputs_layout.setSpacing(12)

        button_row = QHBoxLayout()
        button_row.setSpacing(8)
        self.btn_add_pdf = QPushButton("PDF追加")
        self.btn_remove_selected = QPushButton("選択削除")
        self.btn_move_up = QPushButton("上へ")
        self.btn_move_down = QPushButton("下へ")
        for button in (
            self.btn_add_pdf,
            self.btn_remove_selected,
            self.btn_move_up,
            self.btn_move_down,
        ):
            button.setMinimumHeight(38)
            button_row.addWidget(button)
        button_row.addStretch(1)
        inputs_layout.addLayout(button_row)

        self.lbl_drop_hint = QLabel("PDF をこの一覧へドラッグ&ドロップして追加できます")
        self.lbl_drop_hint.setFont(make_app_font(12))
        self.lbl_drop_hint.setStyleSheet("color: #64748b;")
        inputs_layout.addWidget(self.lbl_drop_hint)

        self.input_list = MergeInputList()
        self.input_list.setObjectName("merge_input_list")
        self.input_list.itemSelectionChanged.connect(self._update_selection_buttons)
        inputs_layout.addWidget(self.input_list, stretch=1)
        root.addWidget(self.inputs_group, stretch=1)

        self.output_group = QGroupBox("出力と進捗")
        output_layout = QVBoxLayout(self.output_group)
        output_layout.setSpacing(12)

        output_row = QHBoxLayout()
        output_row.setSpacing(8)
        self.txt_output_path = QLineEdit()
        self.txt_output_path.setReadOnly(True)
        self.txt_output_path.setPlaceholderText("結合後PDFの保存先を選択してください")
        self.btn_choose_output = QPushButton("保存先を選択")
        self.btn_choose_output.setMinimumHeight(38)
        output_row.addWidget(self.txt_output_path, stretch=1)
        output_row.addWidget(self.btn_choose_output)
        output_layout.addLayout(output_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        output_layout.addWidget(self.progress_bar)

        self.lbl_progress = QLabel("待機中")
        self.lbl_progress.setFont(make_app_font(12, bold=True))
        output_layout.addWidget(self.lbl_progress)

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet("color: #cbd5e1;")
        output_layout.addWidget(divider)

        self.btn_execute = QPushButton("結合を実行")
        self.btn_execute.setMinimumHeight(48)
        self.btn_execute.setFont(make_app_font(16, bold=True))
        self.btn_execute.setStyleSheet(
            "QPushButton { background-color: #0f766e; color: white; border-radius: 8px; }"
            "QPushButton:disabled { background-color: #94a3b8; color: #e2e8f0; }"
        )
        output_layout.addWidget(self.btn_execute)
        root.addWidget(self.output_group, stretch=0)

    def set_presenter(self, presenter: Any) -> None:
        """View の操作シグナルを Presenter の公開メソッドへ接続する。"""
        self.btn_add_pdf.clicked.connect(presenter.add_pdf_files)
        self.btn_remove_selected.clicked.connect(presenter.remove_selected_inputs)
        self.btn_move_up.clicked.connect(presenter.move_selected_up)
        self.btn_move_down.clicked.connect(presenter.move_selected_down)
        self.btn_choose_output.clicked.connect(presenter.choose_output_file)
        self.btn_execute.clicked.connect(presenter.execute_merge)
        self.input_list.paths_dropped.connect(presenter.handle_dropped_paths)
        self.input_list.order_changed.connect(presenter.reorder_inputs)
        self.input_list.selection_paths_changed.connect(presenter.set_selected_inputs)

    def update_ui(self, state: MergeUiState) -> None:
        """受け取った状態スナップショットで画面全体を更新する。"""
        self._can_remove_selected = state.can_remove_selected
        self._can_move_up = state.can_move_up
        self._can_move_down = state.can_move_down

        self.btn_back_home.setEnabled(state.can_back_home)
        self.btn_add_pdf.setEnabled(state.can_add_inputs)
        self.btn_choose_output.setEnabled(state.can_choose_output)
        self.btn_execute.setEnabled(state.can_execute)
        self.txt_output_path.setText(state.output_path_text)
        self.progress_bar.setValue(state.progress_value)
        self.lbl_progress.setText(state.progress_text)
        self.input_list.setDragEnabled(not state.is_running)
        self.input_list.setAcceptDrops(not state.is_running)
        self.input_list.setDropIndicatorShown(not state.is_running)
        self.input_list.setDragDropMode(
            QAbstractItemView.DragDropMode.NoDragDrop if state.is_running
            else QAbstractItemView.DragDropMode.InternalMove,
        )

        self._rebuild_input_list(state)
        self._update_selection_buttons()

    def get_selected_input_paths(self) -> list[str]:
        """一覧で選択中の入力パスを返す。"""
        return self.input_list.selected_paths()

    def _rebuild_input_list(self, state: MergeUiState) -> None:
        self.input_list.blockSignals(True)
        self.input_list.clear()

        selected = set(state.selected_paths)
        for item_data in state.input_items:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, item_data.path)
            row = MergeInputRow(item_data)
            item.setSizeHint(row.sizeHint())
            self.input_list.addItem(item)
            self.input_list.setItemWidget(item, row)
            if item_data.path in selected:
                item.setSelected(True)

        self.input_list.blockSignals(False)

    def _update_selection_buttons(self) -> None:
        has_selection = bool(self.input_list.selectedItems())
        self.btn_remove_selected.setEnabled(self._can_remove_selected and has_selection)
        self.btn_move_up.setEnabled(self._can_move_up and has_selection)
        self.btn_move_down.setEnabled(self._can_move_down and has_selection)