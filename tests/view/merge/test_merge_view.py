from __future__ import annotations

import fitz
from pathlib import Path

from PySide6.QtCore import QMimeData, QPointF, Qt, QUrl
from PySide6.QtGui import QDropEvent

from view.merge.merge_view import MergeInputItem, MergeUiState, MergeView


class TestMergeView:

    def test_can_instantiate(self, qtbot) -> None:
        view = MergeView()
        qtbot.addWidget(view)

        assert view is not None

    def test_update_ui_populates_inputs_and_output(self, qtbot) -> None:
        view = MergeView()
        qtbot.addWidget(view)

        state = MergeUiState(
            input_items=[
                MergeInputItem(
                    path="C:/work/sample.pdf",
                    title="sample.pdf",
                    detail="C:/work/sample.pdf",
                ),
            ],
            selected_paths=["C:/work/sample.pdf"],
            output_path_text="C:/out/merged.pdf",
            progress_text="待機中",
            progress_value=0,
            can_remove_selected=True,
            can_execute=True,
        )

        view.update_ui(state)

        assert view.input_list.count() == 1
        assert view.txt_output_path.text() == "C:/out/merged.pdf"
        assert view.progress_bar.value() == 0
        assert view.btn_execute.isEnabled() is True
        assert view.btn_remove_selected.isEnabled() is True

    def test_update_ui_updates_progress_bar_value(self, qtbot) -> None:
        view = MergeView()
        qtbot.addWidget(view)

        state = MergeUiState(
            input_items=[
                MergeInputItem(path="C:/work/sample.pdf", title="sample.pdf", detail="C:/work/sample.pdf"),
            ],
            progress_text="結合中: 1 / 4 ページ",
            progress_value=25,
            is_running=True,
        )

        view.update_ui(state)

        assert view.progress_bar.value() == 25
        assert view.lbl_progress.text() == "結合中: 1 / 4 ページ"

    def test_update_ui_shows_thumbnail_pixmap(self, qtbot, sample_pdf: Path) -> None:
        view = MergeView()
        qtbot.addWidget(view)

        with fitz.open(str(sample_pdf)) as document:
            pixmap = document.load_page(0).get_pixmap(matrix=fitz.Matrix(0.1, 0.1), alpha=False)
        png_bytes = pixmap.tobytes("png")

        state = MergeUiState(
            input_items=[
                MergeInputItem(
                    path=str(sample_pdf),
                    title=sample_pdf.name,
                    detail=str(sample_pdf),
                    thumbnail_status="ready",
                    thumbnail_png_bytes=png_bytes,
                ),
            ],
        )

        view.update_ui(state)

        row = view.input_list.itemWidget(view.input_list.item(0))
        assert row.thumbnail_label.pixmap() is not None
        assert not row.thumbnail_label.pixmap().isNull()

    def test_update_ui_shows_error_placeholder_when_thumbnail_missing(self, qtbot) -> None:
        view = MergeView()
        qtbot.addWidget(view)

        state = MergeUiState(
            input_items=[
                MergeInputItem(
                    path="C:/broken.pdf",
                    title="broken.pdf",
                    detail="C:/broken.pdf",
                    thumbnail_status="error",
                    thumbnail_text="サムネイル\n読込失敗",
                ),
            ],
        )

        view.update_ui(state)

        row = view.input_list.itemWidget(view.input_list.item(0))
        assert row.thumbnail_label.text() == "サムネイル\n読込失敗"

    def test_drop_event_emits_local_paths(self, qtbot, tmp_path: Path) -> None:
        view = MergeView()
        qtbot.addWidget(view)
        received: list[list[str]] = []
        view.input_list.paths_dropped.connect(received.append)

        pdf_path = tmp_path / "sample.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\n")

        mime_data = QMimeData()
        mime_data.setUrls([QUrl.fromLocalFile(str(pdf_path))])
        event = QDropEvent(
            QPointF(10, 10),
            Qt.DropAction.CopyAction,
            mime_data,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )

        view.input_list.dropEvent(event)

        assert len(received) == 1
        assert [Path(path) for path in received[0]] == [pdf_path]

    def test_selection_changes_enable_move_buttons(self, qtbot) -> None:
        view = MergeView()
        qtbot.addWidget(view)

        state = MergeUiState(
            input_items=[
                MergeInputItem(path="C:/one.pdf", title="one.pdf", detail="C:/one.pdf"),
                MergeInputItem(path="C:/two.pdf", title="two.pdf", detail="C:/two.pdf"),
            ],
            can_remove_selected=True,
            can_move_up=True,
            can_move_down=False,
        )
        view.update_ui(state)

        view.input_list.item(1).setSelected(True)
        view._update_selection_buttons()

        assert view.get_selected_input_paths() == ["C:/two.pdf"]
        assert view.btn_remove_selected.isEnabled() is True
        assert view.btn_move_up.isEnabled() is True
        assert view.btn_move_down.isEnabled() is False

    def test_update_ui_disables_reorder_while_running(self, qtbot) -> None:
        view = MergeView()
        qtbot.addWidget(view)

        state = MergeUiState(
            input_items=[MergeInputItem(path="C:/one.pdf", title="one.pdf", detail="C:/one.pdf")],
            is_running=True,
            progress_text="結合中: 0 / 1 ページ",
            progress_value=0,
        )

        view.update_ui(state)

        assert view.input_list.dragDropMode() == view.input_list.DragDropMode.NoDragDrop
        assert view.input_list.acceptDrops() is False
        assert view.progress_bar.value() == 0

    def test_update_ui_disables_buttons_while_running(self, qtbot) -> None:
        view = MergeView()
        qtbot.addWidget(view)

        state = MergeUiState(
            input_items=[MergeInputItem(path="C:/one.pdf", title="one.pdf", detail="C:/one.pdf")],
            can_add_inputs=False,
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