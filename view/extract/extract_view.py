"""PDF 抽出画面の View。

左右分割ペイン UI で Source（複数PDFのページサムネイル一覧）から
Target（抽出先・並べ替え可）へページを DnD/ボタンで移動し、
単一PDFとして出力する。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Sequence

from PySide6.QtCore import QEvent, QMimeData, QPoint, QRect, Qt, Signal
from PySide6.QtGui import QDrag, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from view.font_config import make_app_font


# ── カスタム MIME タイプ ────────────────────────────────

EXTRACT_PAGES_MIME = "application/x-pdf-extract-pages"


# ── UI 状態データクラス群 ──────────────────────────────


@dataclass(slots=True)
class SourceSectionItem:
    """Source パネルの 1 セクション（= 1 PDF）の表示データ。"""

    doc_id: str
    filename: str
    page_count: int
    pages: list[SourcePageItem] = field(default_factory=list)


@dataclass(slots=True)
class SourcePageItem:
    """Source 側 1 ページの表示データ。"""

    doc_id: str
    page_index: int
    thumbnail_png_bytes: bytes | None = None
    thumbnail_status: str = "idle"
    is_selected: bool = False


@dataclass(slots=True)
class TargetItem:
    """Target リスト 1 行の表示データ。"""

    entry_id: str
    doc_id: str
    page_index: int
    source_filename: str
    thumbnail_png_bytes: bytes | None = None
    thumbnail_status: str = "idle"
    is_selected: bool = False


@dataclass(slots=True)
class ExtractUiState:
    """ExtractView を 1 回で描画更新するための状態スナップショット。"""

    source_sections: list[SourceSectionItem] = field(default_factory=list)
    target_items: list[TargetItem] = field(default_factory=list)
    source_zoom_percent: int = 100
    target_zoom_percent: int = 100
    output_path_text: str = "抽出後PDFの保存先を選択してください"
    progress_text: str = "待機中"
    can_add_pdf: bool = True
    can_remove_pdf: bool = False
    can_extract: bool = False
    can_remove_target: bool = False
    can_clear_target: bool = False
    can_move_up: bool = False
    can_move_down: bool = False
    can_choose_output: bool = True
    can_execute: bool = False
    can_back_home: bool = True
    is_running: bool = False


# ── PageThumbnailWidget ────────────────────────────────


class PageThumbnailWidget(QWidget):
    """サムネイル画像 + ページ番号を表示する 1 ページ分ウィジェット。"""

    clicked = Signal(str, int, object)  # doc_id, page_index, QMouseEvent
    double_clicked = Signal(str, int)    # doc_id, page_index

    THUMBNAIL_BASE_PX = 128

    def __init__(
        self,
        doc_id: str,
        page_index: int,
        zoom_percent: int = 100,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._doc_id = doc_id
        self._page_index = page_index
        self._is_selected = False
        self._zoom_percent = zoom_percent
        self._thumbnail_png_bytes: bytes | None = None
        self._thumbnail_status = "idle"
        self._drag_start_pos: QPoint | None = None
        self._drag_payload_provider: Callable[[str, int], list[dict[str, object]]] | None = None
        self._drag_enabled_provider: Callable[[], bool] | None = None

        size = self._display_size()
        self.setFixedSize(size + 8, size + 28)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        self._image_label = QLabel()
        self._image_label.setFixedSize(size, size)
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_label.setStyleSheet(
            "background-color: #e2e8f0;"
            " border: 1px solid #cbd5e1;"
            " border-radius: 4px;"
        )
        layout.addWidget(self._image_label, alignment=Qt.AlignmentFlag.AlignCenter)

        self._page_label = QLabel(str(page_index + 1))
        self._page_label.setFont(make_app_font(9))
        self._page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._page_label, alignment=Qt.AlignmentFlag.AlignCenter)

        self._update_border()

    @property
    def doc_id(self) -> str:
        return self._doc_id

    @property
    def page_index(self) -> int:
        return self._page_index

    @property
    def is_selected(self) -> bool:
        return self._is_selected

    def set_selected(self, selected: bool) -> None:
        if self._is_selected != selected:
            self._is_selected = selected
            self._update_border()

    def set_thumbnail(self, png_bytes: bytes | None) -> None:
        self.set_thumbnail_state(png_bytes, "ready" if png_bytes else "loading")

    def _apply_thumbnail_state(self) -> None:
        size = self._display_size()
        if self._thumbnail_png_bytes:
            pixmap = QPixmap()
            if pixmap.loadFromData(self._thumbnail_png_bytes):
                scaled = pixmap.scaled(
                    size, size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self._image_label.setPixmap(scaled)
                self._image_label.setText("")
                return
        self._image_label.setPixmap(QPixmap())
        self._image_label.setText("エラー" if self._thumbnail_status == "error" else "読込中")

    def set_thumbnail_state(self, png_bytes: bytes | None, status: str) -> None:
        if self._thumbnail_png_bytes == png_bytes and self._thumbnail_status == status:
            return
        self._thumbnail_png_bytes = png_bytes
        self._thumbnail_status = status
        self._apply_thumbnail_state()

    def set_zoom(self, zoom_percent: int) -> None:
        if self._zoom_percent == zoom_percent:
            return
        self._zoom_percent = zoom_percent
        size = self._display_size()
        self.setFixedSize(size + 8, size + 28)
        self._image_label.setFixedSize(size, size)
        self._apply_thumbnail_state()

    def set_drag_context(
        self,
        payload_provider: Callable[[str, int], list[dict[str, object]]],
        enabled_provider: Callable[[], bool],
    ) -> None:
        self._drag_payload_provider = payload_provider
        self._drag_enabled_provider = enabled_provider

    def _display_size(self) -> int:
        return max(32, int(self.THUMBNAIL_BASE_PX * self._zoom_percent / 100))

    def _update_border(self) -> None:
        if self._is_selected:
            self._image_label.setStyleSheet(
                "background-color: #e2e8f0;"
                " border: 3px solid #2563eb;"
                " border-radius: 4px;"
            )
        else:
            self._image_label.setStyleSheet(
                "background-color: #e2e8f0;"
                " border: 1px solid #cbd5e1;"
                " border-radius: 4px;"
            )

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.position().toPoint()
        self.clicked.emit(self._doc_id, self._page_index, event)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if (
            self._drag_start_pos is not None
            and event.buttons() & Qt.MouseButton.LeftButton
            and self._can_start_drag()
        ):
            distance = (event.position().toPoint() - self._drag_start_pos).manhattanLength()
            if distance >= QApplication.startDragDistance():
                self._begin_drag()
                return
        super().mouseMoveEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        self.double_clicked.emit(self._doc_id, self._page_index)
        super().mouseDoubleClickEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_start_pos = None
        super().mouseReleaseEvent(event)

    def _can_start_drag(self) -> bool:
        if self._drag_payload_provider is None:
            return False
        if self._drag_enabled_provider is None:
            return True
        return self._drag_enabled_provider()

    def _begin_drag(self) -> bool:
        if self._drag_payload_provider is None:
            return False

        pages = self._drag_payload_provider(self._doc_id, self._page_index)
        if not pages:
            return False

        mime = QMimeData()
        mime.setData(EXTRACT_PAGES_MIME, json.dumps(pages).encode("utf-8"))

        drag = QDrag(self)
        drag.setMimeData(mime)
        if self._image_label.pixmap() and not self._image_label.pixmap().isNull():
            drag.setPixmap(self._image_label.pixmap())

        self._drag_start_pos = None
        drag.exec(Qt.DropAction.CopyAction)
        return True


# ── SourceSectionWidget ────────────────────────────────


class SourceSectionWidget(QWidget):
    """Source パネルの 1 PDF セクション（ファイル名 + ページグリッド）。"""

    page_clicked = Signal(str, int, object)
    page_double_clicked = Signal(str, int)

    def __init__(
        self,
        section: SourceSectionItem,
        zoom_percent: int = 100,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._doc_id = section.doc_id
        self._zoom_percent = zoom_percent
        self._page_widgets: list[PageThumbnailWidget] = []
        self._page_widget_by_index: dict[int, PageThumbnailWidget] = {}
        self._drag_payload_provider: Callable[[str, int], list[dict[str, object]]] | None = None
        self._drag_enabled_provider: Callable[[], bool] | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # セクションヘッダー
        self._header_label = QLabel()
        self._header_label.setFont(make_app_font(11, bold=True))
        self._header_label.setStyleSheet(
            "background-color: #f1f5f9;"
            " padding: 6px 8px;"
            " border-radius: 4px;"
        )
        layout.addWidget(self._header_label)

        # ページグリッド用コンテナ
        self._grid_container = QWidget()
        self._grid_layout = _FlowLayout(self._grid_container, margin=4, spacing=4)
        layout.addWidget(self._grid_container)

        self.update_section(section, zoom_percent)

    @property
    def doc_id(self) -> str:
        return self._doc_id

    @property
    def page_widgets(self) -> list[PageThumbnailWidget]:
        return self._page_widgets

    def set_drag_context(
        self,
        payload_provider: Callable[[str, int], list[dict[str, object]]],
        enabled_provider: Callable[[], bool],
    ) -> None:
        self._drag_payload_provider = payload_provider
        self._drag_enabled_provider = enabled_provider
        for page_widget in self._page_widgets:
            page_widget.set_drag_context(payload_provider, enabled_provider)

    def update_section(self, section: SourceSectionItem, zoom_percent: int) -> None:
        self._zoom_percent = zoom_percent
        self._header_label.setText(f"📄 {section.filename}  ({section.page_count}ページ)")

        removed_indices = set(self._page_widget_by_index)
        ordered_widgets: list[PageThumbnailWidget] = []
        for page_item in section.pages:
            page_widget = self._page_widget_by_index.get(page_item.page_index)
            if page_widget is None:
                page_widget = PageThumbnailWidget(
                    page_item.doc_id,
                    page_item.page_index,
                    zoom_percent,
                )
                page_widget.clicked.connect(self.page_clicked.emit)
                page_widget.double_clicked.connect(self.page_double_clicked.emit)
                if self._drag_payload_provider is not None and self._drag_enabled_provider is not None:
                    page_widget.set_drag_context(
                        self._drag_payload_provider,
                        self._drag_enabled_provider,
                    )
                self._page_widget_by_index[page_item.page_index] = page_widget
            removed_indices.discard(page_item.page_index)
            page_widget.set_zoom(zoom_percent)
            page_widget.set_selected(page_item.is_selected)
            page_widget.set_thumbnail_state(page_item.thumbnail_png_bytes, page_item.thumbnail_status)
            ordered_widgets.append(page_widget)

        for page_index in removed_indices:
            page_widget = self._page_widget_by_index.pop(page_index)
            page_widget.setParent(None)
            page_widget.deleteLater()

        self._page_widgets = ordered_widgets
        self._grid_layout.set_widgets(ordered_widgets)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._grid_layout.refresh()

    def update_page_thumbnail(self, page_index: int, png_bytes: bytes | None, status: str) -> bool:
        page_widget = self._page_widget_by_index.get(page_index)
        if page_widget is None:
            return False
        page_widget.set_thumbnail_state(png_bytes, status)
        return True


# ── FlowLayout ─────────────────────────────────────────


class _FlowLayout(QVBoxLayout):
    """簡易フローレイアウト: 横に並べきれない場合に折り返す。

    完全な FlowLayout 実装は複雑なため、ここでは QVBoxLayout + 行ごとの
    QHBoxLayout で擬似的にフロー配置を実現する。
    ウィジェット追加後に親リサイズで再配置が必要な場合は rebuild() を呼ぶ。
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        margin: int = 0,
        spacing: int = 4,
    ) -> None:
        super().__init__(parent)  # type: ignore[arg-type]
        self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)
        self._widgets: list[QWidget] = []
        self._spacing = spacing
        self._last_available_width = -1
        self._last_widget_signature: tuple[tuple[int, int], ...] = ()

    def addWidget(self, widget: QWidget, *args, **kwargs) -> None:  # type: ignore[override]
        if widget not in self._widgets:
            self._widgets.append(widget)
        self.refresh(force=True)

    def removeWidget(self, widget: QWidget) -> None:  # type: ignore[override]
        if widget in self._widgets:
            self._widgets.remove(widget)
            self.refresh(force=True)

    def set_widgets(self, widgets: Sequence[QWidget]) -> None:
        self._widgets = list(widgets)
        self.refresh()

    def refresh(self, force: bool = False) -> None:
        available_width = self._available_width()
        signature = self._build_signature()
        if not force and available_width == self._last_available_width and signature == self._last_widget_signature:
            return
        self._rebuild()
        self._last_available_width = available_width
        self._last_widget_signature = signature

    def _available_width(self) -> int:
        parent = self.parentWidget()
        if parent is None:
            return 800
        margins = self.contentsMargins()
        return max(1, parent.width() - margins.left() - margins.right())

    def _build_signature(self) -> tuple[tuple[int, int], ...]:
        return tuple((id(widget), widget.sizeHint().width()) for widget in self._widgets)

    def _rebuild(self) -> None:
        # 既存の行レイアウトを削除
        while self.count():
            item = self.takeAt(0)
            if item is None:
                continue
            layout = item.layout()
            if layout is not None:
                while layout.count():
                    child = layout.takeAt(0)
                    # ウィジェットは保持するので hide しない
                    if child is None:
                        continue
                    child_widget = child.widget()
                    if child_widget is not None:
                        child_widget.setParent(None)

        available_width = self._available_width()

        row = QHBoxLayout()
        row.setSpacing(self._spacing)
        row_width = 0

        for w in self._widgets:
            w_width = w.sizeHint().width()
            if row_width > 0 and row_width + self._spacing + w_width > available_width:
                row.addStretch()
                super().addLayout(row)
                row = QHBoxLayout()
                row.setSpacing(self._spacing)
                row_width = 0

            row.addWidget(w)
            row_width += w_width + (self._spacing if row_width > 0 else 0)

        if self._widgets:
            row.addStretch()
            super().addLayout(row)


# ── TargetPageList ─────────────────────────────────────


class TargetPageList(QListWidget):
    """Target 側のページリスト。InternalMove DnD + Source からのカスタム MIME 受け入れ。"""

    pages_dropped_from_source = Signal(list)  # list[dict] with doc_id, page_index
    order_changed = Signal(list)  # list[str] entry_ids
    selection_changed_ids = Signal(list)  # list[str] entry_ids

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)  # type: ignore[arg-type]
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setAlternatingRowColors(True)
        self.setUniformItemSizes(True)
        self.itemSelectionChanged.connect(self._emit_selection_ids)

    def dragEnterEvent(self, event) -> None:
        if event.source() is self:
            event.acceptProposedAction()
            return
        mime = event.mimeData()
        if mime.hasFormat(EXTRACT_PAGES_MIME):
            event.acceptProposedAction()
            return
        event.ignore()
        return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:
        if event.source() is self:
            event.acceptProposedAction()
            return
        mime = event.mimeData()
        if mime.hasFormat(EXTRACT_PAGES_MIME):
            event.acceptProposedAction()
            return
        event.ignore()
        return
        super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:
        if event.source() is self:
            super().dropEvent(event)
            self.order_changed.emit(self.current_entry_ids())
            return

        mime = event.mimeData()
        if mime.hasFormat(EXTRACT_PAGES_MIME):
            raw = bytes(mime.data(EXTRACT_PAGES_MIME)).decode("utf-8")
            pages = json.loads(raw)
            if pages:
                self.pages_dropped_from_source.emit(pages)
                event.acceptProposedAction()
            return

        event.ignore()
        return

        super().dropEvent(event)

    def current_entry_ids(self) -> list[str]:
        return [
            self.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self.count())
        ]

    def selected_entry_ids(self) -> list[str]:
        return [item.data(Qt.ItemDataRole.UserRole) for item in self.selectedItems()]

    def _emit_selection_ids(self) -> None:
        self.selection_changed_ids.emit(self.selected_entry_ids())


class TargetRow(QWidget):
    """Target リストのカスタム行ウィジェット。"""

    def __init__(self, item: TargetItem, zoom_percent: int = 100, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._zoom_percent = zoom_percent
        self._title_text = ""
        self._thumbnail_png_bytes: bytes | None = None
        self._thumbnail_status = "idle"
        root = QHBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(8)

        self.thumbnail_label = QLabel()
        self.thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumbnail_label.setStyleSheet(
            "background-color: #e2e8f0;"
            " border: 1px solid #cbd5e1;"
            " border-radius: 4px;"
        )
        root.addWidget(self.thumbnail_label, stretch=0)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        self.title_label = QLabel()
        self.title_label.setFont(make_app_font(11, bold=True))
        text_layout.addWidget(self.title_label)
        root.addLayout(text_layout, stretch=1)

        self.update_item(item, zoom_percent)

    def _apply_thumbnail(self, item: TargetItem, size: int) -> None:
        if item.thumbnail_png_bytes:
            pixmap = QPixmap()
            if pixmap.loadFromData(item.thumbnail_png_bytes):
                scaled = pixmap.scaled(
                    size, size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self.thumbnail_label.setPixmap(scaled)
                self.thumbnail_label.setText("")
                return
        self.thumbnail_label.setPixmap(QPixmap())
        self.thumbnail_label.setText("エラー" if item.thumbnail_status == "error" else "…")
        self.thumbnail_label.setFont(make_app_font(9))

    def update_item(self, item: TargetItem, zoom_percent: int) -> None:
        zoom_changed = self._zoom_percent != zoom_percent
        self._zoom_percent = zoom_percent
        thumb_size = max(32, int(48 * zoom_percent / 100))
        if self.thumbnail_label.width() != thumb_size or self.thumbnail_label.height() != thumb_size:
            self.thumbnail_label.setFixedSize(thumb_size, thumb_size)

        title_text = f"{item.source_filename} - p.{item.page_index + 1}"
        if self._title_text != title_text:
            self._title_text = title_text
            self.title_label.setText(title_text)

        if (
            zoom_changed
            or self._thumbnail_png_bytes != item.thumbnail_png_bytes
            or self._thumbnail_status != item.thumbnail_status
        ):
            self._thumbnail_png_bytes = item.thumbnail_png_bytes
            self._thumbnail_status = item.thumbnail_status
            self._apply_thumbnail(item, thumb_size)

    def update_thumbnail(self, png_bytes: bytes | None, status: str) -> None:
        if self._thumbnail_png_bytes == png_bytes and self._thumbnail_status == status:
            return
        self._thumbnail_png_bytes = png_bytes
        self._thumbnail_status = status
        item = TargetItem(
            entry_id="",
            doc_id="",
            page_index=0,
            source_filename="",
            thumbnail_png_bytes=png_bytes,
            thumbnail_status=status,
        )
        self._apply_thumbnail(item, self.thumbnail_label.width())


# ── ExtractView ────────────────────────────────────────


class ExtractView(QWidget):
    """PDF 抽出画面の二分割ペイン UI。"""

    back_to_home_requested = Signal()
    # Source 操作シグナル
    add_pdf_requested = Signal()
    remove_pdf_requested = Signal()
    source_page_clicked = Signal(str, int, object)   # doc_id, page_index, event
    source_page_double_clicked = Signal(str, int)     # doc_id, page_index
    source_zoom_in_requested = Signal()
    source_zoom_out_requested = Signal()
    source_zoom_reset_requested = Signal()
    source_viewport_changed = Signal()
    # Target 操作シグナル
    extract_to_target_requested = Signal()
    remove_target_requested = Signal()
    clear_target_requested = Signal()
    move_target_up_requested = Signal()
    move_target_down_requested = Signal()
    target_zoom_in_requested = Signal()
    target_zoom_out_requested = Signal()
    target_zoom_reset_requested = Signal()
    target_viewport_changed = Signal()
    # 出力シグナル
    choose_output_requested = Signal()
    execute_requested = Signal()
    # DnD
    files_dropped = Signal(list)  # list[str] paths

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._shortcuts: list[QShortcut] = []
        self._source_section_widgets: list[SourceSectionWidget] = []
        self._source_section_widget_map: dict[str, SourceSectionWidget] = {}
        self._source_layout_doc_ids: list[str] = []
        self._target_list_items: dict[str, QListWidgetItem] = {}
        self._target_row_widgets: dict[str, TargetRow] = {}
        self._source_drag_enabled = True
        self._build_ui()
        self._setup_shortcuts()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        # ── ヘッダー ──
        header = QHBoxLayout()
        header.setSpacing(12)
        self.btn_back_home = QPushButton("← ホーム")
        self.btn_back_home.setMinimumHeight(40)
        self.btn_back_home.clicked.connect(
            lambda checked=False: self.back_to_home_requested.emit(),
        )
        header.addWidget(self.btn_back_home, stretch=0)

        title_box = QVBoxLayout()
        title = QLabel("PDF 抽出")
        title.setFont(make_app_font(22, bold=True))
        subtitle = QLabel("複数PDFからページを選んで抽出し、1つのPDFにまとめます")
        subtitle.setFont(make_app_font(12))
        subtitle.setStyleSheet("color: #475569;")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box, stretch=1)
        root.addLayout(header)

        # ── 二分割スプリッター ──
        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setChildrenCollapsible(False)
        root.addWidget(self._splitter, stretch=1)

        self._build_source_panel()
        self._build_target_panel()

        self._splitter.setSizes([500, 500])

    # ── Source パネル ──

    def _build_source_panel(self) -> None:
        source_panel = QWidget()
        source_layout = QVBoxLayout(source_panel)
        source_layout.setContentsMargins(4, 4, 4, 4)
        source_layout.setSpacing(8)

        # ボタン行
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self.btn_add_pdf = QPushButton("PDF追加")
        self.btn_add_pdf.setMinimumHeight(34)
        self.btn_add_pdf.clicked.connect(
            lambda checked=False: self.add_pdf_requested.emit(),
        )
        self.btn_remove_pdf = QPushButton("PDF削除")
        self.btn_remove_pdf.setMinimumHeight(34)
        self.btn_remove_pdf.clicked.connect(
            lambda checked=False: self.remove_pdf_requested.emit(),
        )
        btn_row.addWidget(self.btn_add_pdf)
        btn_row.addWidget(self.btn_remove_pdf)
        btn_row.addStretch()

        # Source ズームコントロール
        self.btn_source_zoom_out = QPushButton("−")
        self.btn_source_zoom_out.setFixedWidth(32)
        self.btn_source_zoom_out.setMinimumHeight(34)
        self.btn_source_zoom_out.clicked.connect(
            lambda checked=False: self.source_zoom_out_requested.emit(),
        )
        self.lbl_source_zoom = QLabel("100%")
        self.lbl_source_zoom.setFont(make_app_font(10))
        self.lbl_source_zoom.setFixedWidth(48)
        self.lbl_source_zoom.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.btn_source_zoom_in = QPushButton("+")
        self.btn_source_zoom_in.setFixedWidth(32)
        self.btn_source_zoom_in.setMinimumHeight(34)
        self.btn_source_zoom_in.clicked.connect(
            lambda checked=False: self.source_zoom_in_requested.emit(),
        )
        self.btn_source_zoom_reset = QPushButton("⟳")
        self.btn_source_zoom_reset.setFixedWidth(32)
        self.btn_source_zoom_reset.setMinimumHeight(34)
        self.btn_source_zoom_reset.clicked.connect(
            lambda checked=False: self.source_zoom_reset_requested.emit(),
        )
        btn_row.addWidget(self.btn_source_zoom_out)
        btn_row.addWidget(self.lbl_source_zoom)
        btn_row.addWidget(self.btn_source_zoom_in)
        btn_row.addWidget(self.btn_source_zoom_reset)
        source_layout.addLayout(btn_row)

        # Source 抽出ボタン（→）
        extract_row = QHBoxLayout()
        self.btn_extract = QPushButton("選択ページを Target へ →")
        self.btn_extract.setMinimumHeight(36)
        self.btn_extract.setFont(make_app_font(11, bold=True))
        self.btn_extract.setStyleSheet(
            "QPushButton { background-color: #0369a1; color: white; border-radius: 6px; }"
            "QPushButton:disabled { background-color: #94a3b8; color: #e2e8f0; }"
        )
        self.btn_extract.clicked.connect(
            lambda checked=False: self.extract_to_target_requested.emit(),
        )
        extract_row.addWidget(self.btn_extract)
        source_layout.addLayout(extract_row)

        # スクロール可能なセクション領域
        self._source_scroll = QScrollArea()
        self._source_scroll.setWidgetResizable(True)
        self._source_scroll.setAcceptDrops(True)
        self._source_scroll.viewport().setAcceptDrops(True)
        self._source_scroll.setStyleSheet(
            "QScrollArea { border: 1px solid #cbd5e1; border-radius: 6px; }"
        )
        self._source_content = QWidget()
        self._source_content.setAcceptDrops(True)
        self._source_content_layout = QVBoxLayout(self._source_content)
        self._source_content_layout.setContentsMargins(4, 4, 4, 4)
        self._source_content_layout.setSpacing(8)
        self._source_content_layout.addStretch()

        self._source_empty_label = QLabel(
            "PDFファイルを追加してください\n（ボタンまたはドラッグ&ドロップ）"
        )
        self._source_empty_label.setFont(make_app_font(12))
        self._source_empty_label.setStyleSheet("color: #94a3b8;")
        self._source_empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._source_content_layout.insertWidget(0, self._source_empty_label)

        self._source_scroll.setWidget(self._source_content)
        self._source_scroll.installEventFilter(self)
        self._source_scroll.viewport().installEventFilter(self)
        self._source_content.installEventFilter(self)
        self._source_scroll.verticalScrollBar().valueChanged.connect(
            lambda value: self.source_viewport_changed.emit(),
        )
        source_layout.addWidget(self._source_scroll, stretch=1)

        self._splitter.addWidget(source_panel)

    # ── Target パネル ──

    def _build_target_panel(self) -> None:
        target_panel = QWidget()
        target_layout = QVBoxLayout(target_panel)
        target_layout.setContentsMargins(4, 4, 4, 4)
        target_layout.setSpacing(8)

        # Target 操作ボタン行
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self.btn_remove_target = QPushButton("選択削除")
        self.btn_remove_target.setMinimumHeight(34)
        self.btn_remove_target.clicked.connect(
            lambda checked=False: self.remove_target_requested.emit(),
        )
        self.btn_clear_target = QPushButton("全クリア")
        self.btn_clear_target.setMinimumHeight(34)
        self.btn_clear_target.clicked.connect(
            lambda checked=False: self.clear_target_requested.emit(),
        )
        self.btn_move_up = QPushButton("↑")
        self.btn_move_up.setFixedWidth(36)
        self.btn_move_up.setMinimumHeight(34)
        self.btn_move_up.clicked.connect(
            lambda checked=False: self.move_target_up_requested.emit(),
        )
        self.btn_move_down = QPushButton("↓")
        self.btn_move_down.setFixedWidth(36)
        self.btn_move_down.setMinimumHeight(34)
        self.btn_move_down.clicked.connect(
            lambda checked=False: self.move_target_down_requested.emit(),
        )
        btn_row.addWidget(self.btn_remove_target)
        btn_row.addWidget(self.btn_clear_target)
        btn_row.addWidget(self.btn_move_up)
        btn_row.addWidget(self.btn_move_down)
        btn_row.addStretch()

        # Target ズームコントロール
        self.btn_target_zoom_out = QPushButton("−")
        self.btn_target_zoom_out.setFixedWidth(32)
        self.btn_target_zoom_out.setMinimumHeight(34)
        self.btn_target_zoom_out.clicked.connect(
            lambda checked=False: self.target_zoom_out_requested.emit(),
        )
        self.lbl_target_zoom = QLabel("100%")
        self.lbl_target_zoom.setFont(make_app_font(10))
        self.lbl_target_zoom.setFixedWidth(48)
        self.lbl_target_zoom.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.btn_target_zoom_in = QPushButton("+")
        self.btn_target_zoom_in.setFixedWidth(32)
        self.btn_target_zoom_in.setMinimumHeight(34)
        self.btn_target_zoom_in.clicked.connect(
            lambda checked=False: self.target_zoom_in_requested.emit(),
        )
        self.btn_target_zoom_reset = QPushButton("⟳")
        self.btn_target_zoom_reset.setFixedWidth(32)
        self.btn_target_zoom_reset.setMinimumHeight(34)
        self.btn_target_zoom_reset.clicked.connect(
            lambda checked=False: self.target_zoom_reset_requested.emit(),
        )
        btn_row.addWidget(self.btn_target_zoom_out)
        btn_row.addWidget(self.lbl_target_zoom)
        btn_row.addWidget(self.btn_target_zoom_in)
        btn_row.addWidget(self.btn_target_zoom_reset)
        target_layout.addLayout(btn_row)

        # Target リスト
        self.target_list = TargetPageList()
        self.target_list.setObjectName("extract_target_list")
        self.target_list.verticalScrollBar().valueChanged.connect(
            lambda value: self.target_viewport_changed.emit(),
        )
        target_layout.addWidget(self.target_list, stretch=1)

        # 出力グループ
        output_group = QGroupBox("出力")
        output_layout_inner = QVBoxLayout(output_group)
        output_layout_inner.setSpacing(8)

        output_row = QHBoxLayout()
        output_row.setSpacing(8)
        self.txt_output_path = QLineEdit()
        self.txt_output_path.setReadOnly(True)
        self.txt_output_path.setPlaceholderText("抽出後PDFの保存先を選択してください")
        self.btn_choose_output = QPushButton("保存先を選択")
        self.btn_choose_output.setMinimumHeight(34)
        self.btn_choose_output.clicked.connect(
            lambda checked=False: self.choose_output_requested.emit(),
        )
        output_row.addWidget(self.txt_output_path, stretch=1)
        output_row.addWidget(self.btn_choose_output)
        output_layout_inner.addLayout(output_row)

        self.lbl_progress = QLabel("待機中")
        self.lbl_progress.setFont(make_app_font(11, bold=True))
        output_layout_inner.addWidget(self.lbl_progress)

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet("color: #cbd5e1;")
        output_layout_inner.addWidget(divider)

        self.btn_execute = QPushButton("抽出を実行")
        self.btn_execute.setMinimumHeight(44)
        self.btn_execute.setFont(make_app_font(14, bold=True))
        self.btn_execute.setStyleSheet(
            "QPushButton { background-color: #0f766e; color: white; border-radius: 8px; }"
            "QPushButton:disabled { background-color: #94a3b8; color: #e2e8f0; }"
        )
        self.btn_execute.clicked.connect(
            lambda checked=False: self.execute_requested.emit(),
        )
        output_layout_inner.addWidget(self.btn_execute)
        target_layout.addWidget(output_group, stretch=0)

        self._splitter.addWidget(target_panel)

    # ── ショートカット ──

    def _setup_shortcuts(self) -> None:
        shortcuts = [
            ("Ctrl+PgUp", lambda: self._navigate_source_section(-1)),
            ("Ctrl+PgDown", lambda: self._navigate_source_section(1)),
            ("Return", lambda: self.extract_to_target_requested.emit()),
            ("Right", lambda: self.extract_to_target_requested.emit()),
            ("Delete", lambda: self._handle_delete()),
            ("Ctrl+A", lambda: self._handle_select_all()),
            ("Ctrl+Shift+A", lambda: self._handle_select_all_source()),
            ("Up", lambda: self.move_target_up_requested.emit()),
            ("Down", lambda: self.move_target_down_requested.emit()),
        ]
        for key_seq, slot in shortcuts:
            sc = QShortcut(QKeySequence(key_seq), self)
            sc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            sc.activated.connect(slot)
            self._shortcuts.append(sc)

    def _navigate_source_section(self, direction: int) -> None:
        """Source セクション間を移動して先頭にスクロール。"""
        if not self._source_section_widgets:
            return
        # 現在表示中のセクションを見つける
        scroll_y = self._source_scroll.verticalScrollBar().value()
        current_idx = 0
        for i, sw in enumerate(self._source_section_widgets):
            if sw.y() <= scroll_y + 10:
                current_idx = i
        target_idx = max(0, min(len(self._source_section_widgets) - 1, current_idx + direction))
        widget = self._source_section_widgets[target_idx]
        self._source_scroll.ensureWidgetVisible(widget, 0, 0)

    def _handle_delete(self) -> None:
        """Delete キー: Target にフォーカスがあれば Target 削除、なければ Source PDF 削除。"""
        if self.target_list.hasFocus():
            self.remove_target_requested.emit()
        else:
            self.remove_pdf_requested.emit()

    def _handle_select_all(self) -> None:
        """Ctrl+A: Target にフォーカスがあれば Target 全選択、なければ Source セクション全選択。"""
        if self.target_list.hasFocus():
            self.target_list.selectAll()
        else:
            self._select_visible_source_section_pages()

    def _handle_select_all_source(self) -> None:
        """Ctrl+Shift+A: Source 全ページ選択。"""
        for sw in self._source_section_widgets:
            for pw in sw.page_widgets:
                pw.set_selected(True)
        self._emit_source_selection()

    def _select_visible_source_section_pages(self) -> None:
        """現在スクロール位置にあるセクションの全ページを選択。"""
        if not self._source_section_widgets:
            return
        scroll_y = self._source_scroll.verticalScrollBar().value()
        viewport_h = self._source_scroll.viewport().height()
        for sw in self._source_section_widgets:
            wy = sw.y()
            if wy <= scroll_y + viewport_h and wy + sw.height() >= scroll_y:
                for pw in sw.page_widgets:
                    pw.set_selected(True)
                self._emit_source_selection()
                return

    def _emit_source_selection(self) -> None:
        """全セクションの選択状態を集約してシグナルを発行する。"""
        # Presenter 側が接続している source_page_clicked を使わず、
        # 一括選択の場合は Presenter の公開メソッドを直接呼ぶ。
        # ここでは選択状態の変更を source_page_clicked で通知するのではなく
        # Presenter に _collect_selected_refs() を呼んでもらう設計。
        pass  # Presenter が set_presenter() で接続する

    def eventFilter(self, watched, event) -> bool:
        if watched in {
            self._source_scroll,
            self._source_scroll.viewport(),
            self._source_content,
        } and event.type() in {
            QEvent.Type.DragEnter,
            QEvent.Type.DragMove,
            QEvent.Type.Drop,
        }:
            return self._handle_source_drop_event(event)
        return super().eventFilter(watched, event)

    # ── 外部ファイル DnD ──

    def _handle_source_drop_event(self, event) -> bool:
        if not event.mimeData().hasUrls():
            event.ignore()
            return False

        if event.type() in {QEvent.Type.DragEnter, QEvent.Type.DragMove}:
            event.acceptProposedAction()
            return True

        paths = [
            url.toLocalFile()
            for url in event.mimeData().urls()
            if url.isLocalFile()
        ]
        if paths:
            self.files_dropped.emit(paths)
            event.acceptProposedAction()
            return True

        event.ignore()
        return False

    def dragEnterEvent(self, event) -> None:
        self._handle_source_drop_event(event)

    def dragMoveEvent(self, event) -> None:
        self._handle_source_drop_event(event)

    def dropEvent(self, event) -> None:
        self._handle_source_drop_event(event)

    # ── Presenter 接続 ──

    def set_presenter(self, presenter: Any) -> None:
        """View の操作シグナルを Presenter の公開メソッドへ接続する。"""
        self._presenter = presenter

    # ── UI 更新 ──

    def update_ui(self, state: ExtractUiState) -> None:
        """受け取った状態スナップショットで画面全体を更新する。"""
        self._apply_common_ui_state(state)
        self.update_source_ui(state.source_sections, state.source_zoom_percent)
        self.update_target_ui(state.target_items, state.target_zoom_percent)

    def _apply_common_ui_state(self, state: ExtractUiState) -> None:
        """Source/Target 共通の操作可能状態だけを更新する。"""
        # ボタン有効/無効
        self.btn_back_home.setEnabled(state.can_back_home)
        self.btn_add_pdf.setEnabled(state.can_add_pdf)
        self.btn_remove_pdf.setEnabled(state.can_remove_pdf)
        self.btn_extract.setEnabled(state.can_extract)
        self.btn_remove_target.setEnabled(state.can_remove_target)
        self.btn_clear_target.setEnabled(state.can_clear_target)
        self.btn_move_up.setEnabled(state.can_move_up)
        self.btn_move_down.setEnabled(state.can_move_down)
        self.btn_choose_output.setEnabled(state.can_choose_output)
        self.btn_execute.setEnabled(state.can_execute)

        # ズーム表示
        self.lbl_source_zoom.setText(f"{state.source_zoom_percent}%")
        self.lbl_target_zoom.setText(f"{state.target_zoom_percent}%")

        # 出力 / 進捗
        self.txt_output_path.setText(state.output_path_text)
        self.lbl_progress.setText(state.progress_text)

        self._source_drag_enabled = not state.is_running

        # DnD 無効化（実行中）
        self.target_list.setDragEnabled(not state.is_running)
        self.target_list.setAcceptDrops(not state.is_running)
        self.target_list.setDropIndicatorShown(not state.is_running)
        self.target_list.setDragDropMode(
            QAbstractItemView.DragDropMode.NoDragDrop if state.is_running
            else QAbstractItemView.DragDropMode.InternalMove,
        )

    def update_source_ui(self, source_sections: list[SourceSectionItem], zoom_percent: int) -> None:
        """Source セクション更新責務を独立させる。"""
        self._update_source_sections(source_sections, zoom_percent)

    def update_target_ui(self, target_items: list[TargetItem], zoom_percent: int) -> None:
        """Target リスト更新責務を独立させる。"""
        self._update_target_list(target_items, zoom_percent)

    def _update_source_sections(
        self,
        source_sections: list[SourceSectionItem],
        zoom_percent: int,
    ) -> None:
        """Source セクション群を既存 widget 再利用で更新する。"""
        desired_doc_id_order = [section.doc_id for section in source_sections]
        desired_doc_ids = {section.doc_id for section in source_sections}
        removed_doc_ids = [doc_id for doc_id in self._source_section_widget_map if doc_id not in desired_doc_ids]
        for doc_id in removed_doc_ids:
            widget = self._source_section_widget_map.pop(doc_id)
            widget.setParent(None)
            widget.deleteLater()

        ordered_widgets: list[SourceSectionWidget] = []
        for section in source_sections:
            widget = self._source_section_widget_map.get(section.doc_id)
            if widget is None:
                widget = SourceSectionWidget(section, zoom_percent)
                widget.page_clicked.connect(self.source_page_clicked.emit)
                widget.page_double_clicked.connect(self.source_page_double_clicked.emit)
                self._source_section_widget_map[section.doc_id] = widget
            else:
                widget.update_section(section, zoom_percent)
            widget.set_drag_context(self._build_source_drag_pages, self._can_drag_source_pages)
            ordered_widgets.append(widget)

        self._source_section_widgets = ordered_widgets
        if self._source_layout_doc_ids != desired_doc_id_order:
            self._rebuild_source_layout(ordered_widgets)
            self._source_layout_doc_ids = desired_doc_id_order

    def _update_target_list(self, target_items: list[TargetItem], zoom_percent: int) -> None:
        """Target リストを既存 item / row 再利用で更新する。"""
        self.target_list.blockSignals(True)
        self.target_list.setUpdatesEnabled(False)
        had_focus = self.target_list.hasFocus()
        current_item = self.target_list.currentItem()
        current_entry_id = (
            current_item.data(Qt.ItemDataRole.UserRole)
            if current_item is not None else None
        )
        scroll_value = self.target_list.verticalScrollBar().value()

        desired_ids = {target_item.entry_id for target_item in target_items}
        removed_ids = [entry_id for entry_id in self._target_list_items if entry_id not in desired_ids]
        for entry_id in removed_ids:
            item = self._target_list_items.pop(entry_id)
            row = self._target_row_widgets.pop(entry_id)
            list_row = self.target_list.row(item)
            if list_row >= 0:
                self.target_list.takeItem(list_row)
            row.setParent(None)
            row.deleteLater()

        selected_ids = {target_item.entry_id for target_item in target_items if target_item.is_selected}
        for target_item in target_items:
            item = self._target_list_items.get(target_item.entry_id)
            row = self._target_row_widgets.get(target_item.entry_id)
            if item is None or row is None:
                item = QListWidgetItem()
                item.setData(Qt.ItemDataRole.UserRole, target_item.entry_id)
                row = TargetRow(target_item, zoom_percent)
                self._target_list_items[target_item.entry_id] = item
                self._target_row_widgets[target_item.entry_id] = row
            else:
                row.update_item(target_item, zoom_percent)
            item.setSizeHint(row.sizeHint())

        self._sync_target_list_order(target_items)
        for target_item in target_items:
            item = self._target_list_items[target_item.entry_id]
            item.setSelected(target_item.entry_id in selected_ids)
            if current_entry_id == target_item.entry_id:
                self.target_list.setCurrentItem(item)

        self.target_list.verticalScrollBar().setValue(scroll_value)
        if had_focus:
            self.target_list.setFocus()
        self.target_list.setUpdatesEnabled(True)
        self.target_list.blockSignals(False)

    def update_source_page_thumbnail(self, doc_id: str, page_index: int, png_bytes: bytes | None, status: str) -> bool:
        section_widget = self._source_section_widget_map.get(doc_id)
        if section_widget is None:
            return False
        return section_widget.update_page_thumbnail(page_index, png_bytes, status)

    def update_target_entry_thumbnail(self, entry_id: str, png_bytes: bytes | None, status: str) -> bool:
        row = self._target_row_widgets.get(entry_id)
        if row is None:
            return False
        row.update_thumbnail(png_bytes, status)
        return True

    def _rebuild_source_layout(self, ordered_widgets: list[SourceSectionWidget]) -> None:
        self._source_content.setUpdatesEnabled(False)
        while self._source_content_layout.count():
            self._source_content_layout.takeAt(0)

        if not ordered_widgets:
            self._source_empty_label.setVisible(True)
            self._source_content_layout.addWidget(self._source_empty_label)
            self._source_content_layout.addStretch()
            self._source_content.setUpdatesEnabled(True)
            return

        self._source_empty_label.setVisible(False)
        for widget in ordered_widgets:
            self._source_content_layout.addWidget(widget)
        self._source_content_layout.addStretch()
        self._source_content.setUpdatesEnabled(True)

    def _sync_target_list_order(self, target_items: list[TargetItem]) -> None:
        for desired_row, target_item in enumerate(target_items):
            item = self._target_list_items[target_item.entry_id]
            row = self._target_row_widgets[target_item.entry_id]
            current_row = self.target_list.row(item)
            if current_row == -1:
                self.target_list.insertItem(desired_row, item)
                self.target_list.setItemWidget(item, row)
                continue
            if current_row != desired_row:
                moved_item = self.target_list.takeItem(current_row)
                self.target_list.insertItem(desired_row, moved_item)
                self.target_list.setItemWidget(moved_item, row)

    def get_source_section_widgets(self) -> list[SourceSectionWidget]:
        """Presenter が可視セクション判定に使う。"""
        return self._source_section_widgets

    def get_source_scroll_area(self) -> QScrollArea:
        """Presenter が Lazy Loading の可視判定に使う。"""
        return self._source_scroll

    def get_visible_source_page_refs(self) -> list[tuple[str, int]]:
        """Source スクロール領域で現在可視なページ参照を返す。"""
        if not self.isVisible() or not self._source_scroll.isVisible():
            return self._fallback_source_page_refs()

        visible_rect = self._get_source_visible_rect()
        if visible_rect is None:
            return self._fallback_source_page_refs()

        refs: list[tuple[str, int]] = []
        for sw in self._source_section_widgets:
            for pw in sw.page_widgets:
                page_rect = QRect(
                    pw.mapTo(self._source_content, QPoint(0, 0)),
                    pw.size(),
                )
                if page_rect.intersects(visible_rect):
                    refs.append((pw.doc_id, pw.page_index))

        return refs or self._fallback_source_page_refs()

    def get_visible_target_row_range(self) -> tuple[int, int] | None:
        """Target リストで現在可視な行範囲を返す。"""
        if self.target_list.count() == 0:
            return None

        viewport = self.target_list.viewport()
        if viewport.width() <= 0 or viewport.height() <= 0:
            return (0, min(self.target_list.count() - 1, 0))

        top_index = self.target_list.indexAt(QPoint(0, 0))
        bottom_index = self.target_list.indexAt(
            QPoint(0, max(0, viewport.height() - 1)),
        )

        start = top_index.row() if top_index.isValid() else 0
        end = bottom_index.row() if bottom_index.isValid() else self.target_list.count() - 1
        if end < start:
            end = start
        return (start, min(end, self.target_list.count() - 1))

    def collect_selected_source_refs(self) -> list[tuple[str, int]]:
        """全セクションから選択されたページの (doc_id, page_index) を返す。"""
        refs: list[tuple[str, int]] = []
        for sw in self._source_section_widgets:
            for pw in sw.page_widgets:
                if pw.is_selected:
                    refs.append((pw.doc_id, pw.page_index))
        return refs

    def _build_source_drag_pages(self, doc_id: str, page_index: int) -> list[dict[str, object]]:
        refs = self.collect_selected_source_refs()
        if (doc_id, page_index) not in refs:
            refs = [(doc_id, page_index)]
        return [
            {"doc_id": selected_doc_id, "page_index": selected_page_index}
            for selected_doc_id, selected_page_index in refs
        ]

    def _can_drag_source_pages(self) -> bool:
        return self._source_drag_enabled

    def _get_source_visible_rect(self) -> QRect | None:
        """Source viewport の可視領域を source content 座標で返す。"""
        viewport = self._source_scroll.viewport()
        if viewport.width() <= 0 or viewport.height() <= 0:
            return None

        top_left = self._source_content.mapFromGlobal(
            viewport.mapToGlobal(viewport.rect().topLeft()),
        )
        bottom_right = self._source_content.mapFromGlobal(
            viewport.mapToGlobal(viewport.rect().bottomRight()),
        )
        return QRect(top_left, bottom_right).normalized()

    def _fallback_source_page_refs(self) -> list[tuple[str, int]]:
        """レイアウト未確定時の初回要求向けに先頭ページを返す。"""
        refs: list[tuple[str, int]] = []
        for sw in self._source_section_widgets[:1]:
            refs.extend((pw.doc_id, pw.page_index) for pw in sw.page_widgets[:1])
        return refs
