from __future__ import annotations

import json
from pathlib import Path

import fitz
from PySide6.QtCore import QMimeData, QPointF, Qt, QUrl
from PySide6.QtGui import QDropEvent

from view.extract.extract_view import (
    EXTRACT_PAGES_MIME,
    ExtractUiState,
    ExtractView,
    PageThumbnailWidget,
    SourcePageItem,
    SourceSectionItem,
    TargetItem,
    TargetPageList,
)


# ── ヘルパー ──────────────────────────────────────────


def _make_source_section(
    doc_id: str = "doc-1",
    filename: str = "sample.pdf",
    page_count: int = 3,
    *,
    selected_indices: set[int] | None = None,
    thumbnail_bytes: bytes | None = None,
) -> SourceSectionItem:
    """テスト用 SourceSectionItem を組み立てる。"""
    pages = [
        SourcePageItem(
            doc_id=doc_id,
            page_index=i,
            is_selected=(i in selected_indices) if selected_indices else False,
            thumbnail_png_bytes=thumbnail_bytes,
            thumbnail_status="ready" if thumbnail_bytes else "idle",
        )
        for i in range(page_count)
    ]
    return SourceSectionItem(
        doc_id=doc_id,
        filename=filename,
        page_count=page_count,
        pages=pages,
    )


def _make_target_item(
    entry_id: str = "entry-1",
    doc_id: str = "doc-1",
    page_index: int = 0,
    source_filename: str = "sample.pdf",
    *,
    is_selected: bool = False,
    thumbnail_bytes: bytes | None = None,
) -> TargetItem:
    return TargetItem(
        entry_id=entry_id,
        doc_id=doc_id,
        page_index=page_index,
        source_filename=source_filename,
        is_selected=is_selected,
        thumbnail_png_bytes=thumbnail_bytes,
        thumbnail_status="ready" if thumbnail_bytes else "idle",
    )


def _render_thumbnail(pdf_path: Path, page_index: int = 0) -> bytes:
    """テスト用のサムネイル PNG バイトを生成する。"""
    with fitz.open(str(pdf_path)) as doc:
        pixmap = doc.load_page(page_index).get_pixmap(
            matrix=fitz.Matrix(0.1, 0.1), alpha=False,
        )
    return pixmap.tobytes("png")


# ── 基本インスタンス化 ────────────────────────────────


class TestExtractViewBasic:

    def test_can_instantiate(self, qtbot) -> None:
        view = ExtractView()
        qtbot.addWidget(view)

        assert view is not None

    def test_default_ui_state(self, qtbot) -> None:
        view = ExtractView()
        qtbot.addWidget(view)

        state = ExtractUiState()
        view.update_ui(state)

        assert view.btn_add_pdf.isEnabled() is True
        assert view.btn_remove_pdf.isEnabled() is False
        assert view.btn_extract.isEnabled() is False
        assert view.btn_execute.isEnabled() is False
        assert view.btn_back_home.isEnabled() is True
        assert view.lbl_progress.text() == "待機中"
        assert view.lbl_source_zoom.text() == "100%"
        assert view.lbl_target_zoom.text() == "100%"


# ── Source セクション ─────────────────────────────────


class TestSourceSections:

    def test_update_ui_creates_source_sections(self, qtbot) -> None:
        view = ExtractView()
        qtbot.addWidget(view)

        state = ExtractUiState(
            source_sections=[
                _make_source_section("doc-1", "a.pdf", 3),
                _make_source_section("doc-2", "b.pdf", 2),
            ],
        )
        view.update_ui(state)

        widgets = view.get_source_section_widgets()
        assert len(widgets) == 2
        assert widgets[0].doc_id == "doc-1"
        assert widgets[1].doc_id == "doc-2"

    def test_update_ui_replaces_sections_on_change(self, qtbot) -> None:
        view = ExtractView()
        qtbot.addWidget(view)

        view.update_ui(ExtractUiState(
            source_sections=[_make_source_section("doc-1", "a.pdf", 3)],
        ))
        assert len(view.get_source_section_widgets()) == 1

        view.update_ui(ExtractUiState(
            source_sections=[
                _make_source_section("doc-1", "a.pdf", 3),
                _make_source_section("doc-2", "b.pdf", 5),
            ],
        ))
        assert len(view.get_source_section_widgets()) == 2

    def test_empty_source_shows_placeholder(self, qtbot) -> None:
        view = ExtractView()
        qtbot.addWidget(view)

        view.update_ui(ExtractUiState(source_sections=[]))

        assert len(view.get_source_section_widgets()) == 0
        assert not view._source_empty_label.isHidden()

    def test_source_page_selection_shown(self, qtbot) -> None:
        view = ExtractView()
        qtbot.addWidget(view)

        section = _make_source_section("doc-1", "a.pdf", 3, selected_indices={0, 2})
        view.update_ui(ExtractUiState(source_sections=[section]))

        widgets = view.get_source_section_widgets()
        page_widgets = widgets[0].page_widgets
        assert page_widgets[0].is_selected is True
        assert page_widgets[1].is_selected is False
        assert page_widgets[2].is_selected is True

    def test_source_thumbnail_displayed(self, qtbot, sample_pdf: Path) -> None:
        view = ExtractView()
        qtbot.addWidget(view)

        png_bytes = _render_thumbnail(sample_pdf)
        section = _make_source_section(
            "doc-1", "sample.pdf", 1, thumbnail_bytes=png_bytes,
        )
        view.update_ui(ExtractUiState(source_sections=[section]))

        pw = view.get_source_section_widgets()[0].page_widgets[0]
        assert pw._image_label.pixmap() is not None
        assert not pw._image_label.pixmap().isNull()


# ── PageThumbnailWidget ───────────────────────────────


class TestPageThumbnailWidget:

    def test_displays_page_number(self, qtbot) -> None:
        widget = PageThumbnailWidget("doc-1", 4, zoom_percent=100)
        qtbot.addWidget(widget)

        assert widget._page_label.text() == "5"

    def test_selection_toggle_changes_border(self, qtbot) -> None:
        widget = PageThumbnailWidget("doc-1", 0, zoom_percent=100)
        qtbot.addWidget(widget)

        assert widget.is_selected is False
        widget.set_selected(True)
        assert widget.is_selected is True
        assert "2563eb" in widget._image_label.styleSheet()  # 青枠

        widget.set_selected(False)
        assert widget.is_selected is False
        assert "cbd5e1" in widget._image_label.styleSheet()  # 通常枠

    def test_set_thumbnail(self, qtbot, sample_pdf: Path) -> None:
        widget = PageThumbnailWidget("doc-1", 0)
        qtbot.addWidget(widget)

        png_bytes = _render_thumbnail(sample_pdf)
        widget.set_thumbnail(png_bytes)

        assert widget._image_label.pixmap() is not None
        assert not widget._image_label.pixmap().isNull()

    def test_set_thumbnail_none_shows_loading(self, qtbot) -> None:
        widget = PageThumbnailWidget("doc-1", 0)
        qtbot.addWidget(widget)

        widget.set_thumbnail(None)
        assert widget._image_label.text() == "読込中"

    def test_set_zoom_resizes(self, qtbot) -> None:
        widget = PageThumbnailWidget("doc-1", 0, zoom_percent=100)
        qtbot.addWidget(widget)

        original_size = widget.width()
        widget.set_zoom(200)
        assert widget.width() > original_size

    def test_click_emits_signal(self, qtbot) -> None:
        widget = PageThumbnailWidget("doc-1", 3)
        qtbot.addWidget(widget)

        received: list[tuple] = []
        widget.clicked.connect(lambda d, p, e: received.append((d, p)))

        qtbot.mouseClick(widget, Qt.MouseButton.LeftButton)
        assert len(received) == 1
        assert received[0] == ("doc-1", 3)

    def test_double_click_emits_signal(self, qtbot) -> None:
        widget = PageThumbnailWidget("doc-1", 7)
        qtbot.addWidget(widget)

        received: list[tuple] = []
        widget.double_clicked.connect(lambda d, p: received.append((d, p)))

        qtbot.mouseDClick(widget, Qt.MouseButton.LeftButton)
        assert len(received) == 1
        assert received[0] == ("doc-1", 7)


# ── Target リスト ─────────────────────────────────────


class TestTargetList:

    def test_update_ui_populates_target_list(self, qtbot) -> None:
        view = ExtractView()
        qtbot.addWidget(view)

        items = [
            _make_target_item("e1", "doc-1", 0, "a.pdf"),
            _make_target_item("e2", "doc-1", 1, "a.pdf"),
            _make_target_item("e3", "doc-2", 0, "b.pdf"),
        ]
        view.update_ui(ExtractUiState(target_items=items))

        assert view.target_list.count() == 3

    def test_target_item_stores_entry_id(self, qtbot) -> None:
        view = ExtractView()
        qtbot.addWidget(view)

        items = [_make_target_item("entry-42", "doc-1", 3, "a.pdf")]
        view.update_ui(ExtractUiState(target_items=items))

        qi = view.target_list.item(0)
        assert qi.data(Qt.ItemDataRole.UserRole) == "entry-42"

    def test_target_selection_restored(self, qtbot) -> None:
        view = ExtractView()
        qtbot.addWidget(view)

        items = [
            _make_target_item("e1", "doc-1", 0, "a.pdf", is_selected=True),
            _make_target_item("e2", "doc-1", 1, "a.pdf", is_selected=False),
        ]
        view.update_ui(ExtractUiState(target_items=items))

        assert view.target_list.item(0).isSelected() is True
        assert view.target_list.item(1).isSelected() is False

    def test_target_list_clears_on_empty(self, qtbot) -> None:
        view = ExtractView()
        qtbot.addWidget(view)

        view.update_ui(ExtractUiState(target_items=[
            _make_target_item("e1", "doc-1", 0, "a.pdf"),
        ]))
        assert view.target_list.count() == 1

        view.update_ui(ExtractUiState(target_items=[]))
        assert view.target_list.count() == 0

    def test_target_thumbnail_displayed(self, qtbot, sample_pdf: Path) -> None:
        view = ExtractView()
        qtbot.addWidget(view)

        png_bytes = _render_thumbnail(sample_pdf)
        items = [_make_target_item("e1", "doc-1", 0, "a.pdf", thumbnail_bytes=png_bytes)]
        view.update_ui(ExtractUiState(target_items=items))

        row = view.target_list.itemWidget(view.target_list.item(0))
        assert row.thumbnail_label.pixmap() is not None
        assert not row.thumbnail_label.pixmap().isNull()


# ── TargetPageList DnD ────────────────────────────────


class TestTargetPageListDnD:

    def test_accepts_extract_pages_mime(self, qtbot) -> None:
        tl = TargetPageList()
        qtbot.addWidget(tl)

        received: list[list[dict]] = []
        tl.pages_dropped_from_source.connect(received.append)

        pages = [{"doc_id": "doc-1", "page_index": 0}, {"doc_id": "doc-1", "page_index": 2}]
        mime = QMimeData()
        mime.setData(EXTRACT_PAGES_MIME, json.dumps(pages).encode("utf-8"))
        event = QDropEvent(
            QPointF(10, 10),
            Qt.DropAction.CopyAction,
            mime,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )

        tl.dropEvent(event)

        assert len(received) == 1
        assert received[0] == pages

    def test_selection_emits_ids(self, qtbot) -> None:
        view = ExtractView()
        qtbot.addWidget(view)

        items = [
            _make_target_item("e1", "doc-1", 0, "a.pdf"),
            _make_target_item("e2", "doc-1", 1, "a.pdf"),
        ]
        view.update_ui(ExtractUiState(target_items=items))

        received: list[list[str]] = []
        view.target_list.selection_changed_ids.connect(received.append)

        view.target_list.item(0).setSelected(True)

        assert len(received) >= 1
        assert "e1" in received[-1]


# ── ズーム表示 ─────────────────────────────────────────


class TestZoomDisplay:

    def test_source_zoom_label(self, qtbot) -> None:
        view = ExtractView()
        qtbot.addWidget(view)

        view.update_ui(ExtractUiState(source_zoom_percent=150))
        assert view.lbl_source_zoom.text() == "150%"

    def test_target_zoom_label(self, qtbot) -> None:
        view = ExtractView()
        qtbot.addWidget(view)

        view.update_ui(ExtractUiState(target_zoom_percent=75))
        assert view.lbl_target_zoom.text() == "75%"

    def test_zoom_independent(self, qtbot) -> None:
        view = ExtractView()
        qtbot.addWidget(view)

        view.update_ui(ExtractUiState(
            source_zoom_percent=50,
            target_zoom_percent=200,
        ))
        assert view.lbl_source_zoom.text() == "50%"
        assert view.lbl_target_zoom.text() == "200%"


# ── ボタン状態 ────────────────────────────────────────


class TestButtonStates:

    def test_update_ui_enables_buttons_per_state(self, qtbot) -> None:
        view = ExtractView()
        qtbot.addWidget(view)

        state = ExtractUiState(
            can_add_pdf=True,
            can_remove_pdf=True,
            can_extract=True,
            can_remove_target=True,
            can_clear_target=True,
            can_move_up=True,
            can_move_down=True,
            can_choose_output=True,
            can_execute=True,
            can_back_home=True,
        )
        view.update_ui(state)

        assert view.btn_add_pdf.isEnabled() is True
        assert view.btn_remove_pdf.isEnabled() is True
        assert view.btn_extract.isEnabled() is True
        assert view.btn_remove_target.isEnabled() is True
        assert view.btn_clear_target.isEnabled() is True
        assert view.btn_move_up.isEnabled() is True
        assert view.btn_move_down.isEnabled() is True
        assert view.btn_choose_output.isEnabled() is True
        assert view.btn_execute.isEnabled() is True
        assert view.btn_back_home.isEnabled() is True

    def test_update_ui_disables_all_buttons(self, qtbot) -> None:
        view = ExtractView()
        qtbot.addWidget(view)

        state = ExtractUiState(
            can_add_pdf=False,
            can_remove_pdf=False,
            can_extract=False,
            can_remove_target=False,
            can_clear_target=False,
            can_move_up=False,
            can_move_down=False,
            can_choose_output=False,
            can_execute=False,
            can_back_home=False,
        )
        view.update_ui(state)

        assert view.btn_add_pdf.isEnabled() is False
        assert view.btn_remove_pdf.isEnabled() is False
        assert view.btn_extract.isEnabled() is False
        assert view.btn_remove_target.isEnabled() is False
        assert view.btn_clear_target.isEnabled() is False
        assert view.btn_move_up.isEnabled() is False
        assert view.btn_move_down.isEnabled() is False
        assert view.btn_choose_output.isEnabled() is False
        assert view.btn_execute.isEnabled() is False
        assert view.btn_back_home.isEnabled() is False


# ── 実行中 (is_running) の UI 制御 ───────────────────


class TestRunningState:

    def test_disables_dnd_while_running(self, qtbot) -> None:
        view = ExtractView()
        qtbot.addWidget(view)

        state = ExtractUiState(is_running=True)
        view.update_ui(state)

        assert view.target_list.dragDropMode() == view.target_list.DragDropMode.NoDragDrop
        assert view.target_list.acceptDrops() is False

    def test_reenables_dnd_after_running(self, qtbot) -> None:
        view = ExtractView()
        qtbot.addWidget(view)

        view.update_ui(ExtractUiState(is_running=True))
        view.update_ui(ExtractUiState(is_running=False))

        assert view.target_list.dragDropMode() == view.target_list.DragDropMode.InternalMove
        assert view.target_list.acceptDrops() is True

    def test_disables_buttons_while_running(self, qtbot) -> None:
        view = ExtractView()
        qtbot.addWidget(view)

        state = ExtractUiState(
            can_add_pdf=False,
            can_choose_output=False,
            can_execute=False,
            can_back_home=False,
            is_running=True,
        )
        view.update_ui(state)

        assert view.btn_add_pdf.isEnabled() is False
        assert view.btn_choose_output.isEnabled() is False
        assert view.btn_execute.isEnabled() is False
        assert view.btn_back_home.isEnabled() is False

    def test_progress_text_shown(self, qtbot) -> None:
        view = ExtractView()
        qtbot.addWidget(view)

        state = ExtractUiState(
            progress_text="抽出中: 3 / 10 ページ",
            is_running=True,
        )
        view.update_ui(state)

        assert view.lbl_progress.text() == "抽出中: 3 / 10 ページ"


# ── 出力パス表示 ──────────────────────────────────────


class TestOutputDisplay:

    def test_output_path_shown(self, qtbot) -> None:
        view = ExtractView()
        qtbot.addWidget(view)

        state = ExtractUiState(output_path_text="C:/out/extracted.pdf")
        view.update_ui(state)

        assert view.txt_output_path.text() == "C:/out/extracted.pdf"

    def test_output_path_readonly(self, qtbot) -> None:
        view = ExtractView()
        qtbot.addWidget(view)

        assert view.txt_output_path.isReadOnly() is True


# ── シグナル発行 ──────────────────────────────────────


class TestSignalEmission:

    def test_btn_add_pdf_emits(self, qtbot) -> None:
        view = ExtractView()
        qtbot.addWidget(view)

        with qtbot.waitSignal(view.add_pdf_requested, timeout=500):
            view.btn_add_pdf.click()

    def test_btn_remove_pdf_emits(self, qtbot) -> None:
        view = ExtractView()
        qtbot.addWidget(view)

        with qtbot.waitSignal(view.remove_pdf_requested, timeout=500):
            view.btn_remove_pdf.click()

    def test_btn_extract_emits(self, qtbot) -> None:
        view = ExtractView()
        qtbot.addWidget(view)

        with qtbot.waitSignal(view.extract_to_target_requested, timeout=500):
            view.btn_extract.click()

    def test_btn_remove_target_emits(self, qtbot) -> None:
        view = ExtractView()
        qtbot.addWidget(view)

        with qtbot.waitSignal(view.remove_target_requested, timeout=500):
            view.btn_remove_target.click()

    def test_btn_clear_target_emits(self, qtbot) -> None:
        view = ExtractView()
        qtbot.addWidget(view)

        with qtbot.waitSignal(view.clear_target_requested, timeout=500):
            view.btn_clear_target.click()

    def test_btn_move_up_emits(self, qtbot) -> None:
        view = ExtractView()
        qtbot.addWidget(view)

        with qtbot.waitSignal(view.move_target_up_requested, timeout=500):
            view.btn_move_up.click()

    def test_btn_move_down_emits(self, qtbot) -> None:
        view = ExtractView()
        qtbot.addWidget(view)

        with qtbot.waitSignal(view.move_target_down_requested, timeout=500):
            view.btn_move_down.click()

    def test_btn_choose_output_emits(self, qtbot) -> None:
        view = ExtractView()
        qtbot.addWidget(view)

        with qtbot.waitSignal(view.choose_output_requested, timeout=500):
            view.btn_choose_output.click()

    def test_btn_execute_emits(self, qtbot) -> None:
        view = ExtractView()
        qtbot.addWidget(view)

        with qtbot.waitSignal(view.execute_requested, timeout=500):
            view.btn_execute.click()

    def test_btn_back_home_emits(self, qtbot) -> None:
        view = ExtractView()
        qtbot.addWidget(view)

        with qtbot.waitSignal(view.back_to_home_requested, timeout=500):
            view.btn_back_home.click()

    def test_source_zoom_buttons_emit(self, qtbot) -> None:
        view = ExtractView()
        qtbot.addWidget(view)

        with qtbot.waitSignal(view.source_zoom_in_requested, timeout=500):
            view.btn_source_zoom_in.click()

        with qtbot.waitSignal(view.source_zoom_out_requested, timeout=500):
            view.btn_source_zoom_out.click()

        with qtbot.waitSignal(view.source_zoom_reset_requested, timeout=500):
            view.btn_source_zoom_reset.click()

    def test_target_zoom_buttons_emit(self, qtbot) -> None:
        view = ExtractView()
        qtbot.addWidget(view)

        with qtbot.waitSignal(view.target_zoom_in_requested, timeout=500):
            view.btn_target_zoom_in.click()

        with qtbot.waitSignal(view.target_zoom_out_requested, timeout=500):
            view.btn_target_zoom_out.click()

        with qtbot.waitSignal(view.target_zoom_reset_requested, timeout=500):
            view.btn_target_zoom_reset.click()


# ── 外部ファイル DnD ──────────────────────────────────


class TestExternalFileDnD:

    def test_drop_pdf_emits_paths(self, qtbot, tmp_path: Path) -> None:
        view = ExtractView()
        qtbot.addWidget(view)

        received: list[list[str]] = []
        view.files_dropped.connect(received.append)

        pdf_path = tmp_path / "dropped.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\n")

        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(str(pdf_path))])
        event = QDropEvent(
            QPointF(10, 10),
            Qt.DropAction.CopyAction,
            mime,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )

        view.dropEvent(event)

        assert len(received) == 1
        assert Path(received[0][0]) == pdf_path


# ── collect_selected_source_refs ──────────────────────


class TestCollectSelectedRefs:

    def test_returns_selected_page_refs(self, qtbot) -> None:
        view = ExtractView()
        qtbot.addWidget(view)

        section = _make_source_section("doc-1", "a.pdf", 5, selected_indices={1, 3})
        view.update_ui(ExtractUiState(source_sections=[section]))

        refs = view.collect_selected_source_refs()
        assert refs == [("doc-1", 1), ("doc-1", 3)]

    def test_returns_empty_when_no_selection(self, qtbot) -> None:
        view = ExtractView()
        qtbot.addWidget(view)

        section = _make_source_section("doc-1", "a.pdf", 3)
        view.update_ui(ExtractUiState(source_sections=[section]))

        refs = view.collect_selected_source_refs()
        assert refs == []

    def test_multi_section_selection(self, qtbot) -> None:
        view = ExtractView()
        qtbot.addWidget(view)

        state = ExtractUiState(source_sections=[
            _make_source_section("doc-1", "a.pdf", 3, selected_indices={0}),
            _make_source_section("doc-2", "b.pdf", 2, selected_indices={1}),
        ])
        view.update_ui(state)

        refs = view.collect_selected_source_refs()
        assert ("doc-1", 0) in refs
        assert ("doc-2", 1) in refs
        assert len(refs) == 2
