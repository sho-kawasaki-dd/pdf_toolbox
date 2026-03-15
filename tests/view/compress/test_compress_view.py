from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QMimeData, QPointF, Qt, QUrl
from PySide6.QtGui import QDropEvent

from view.compress.compress_view import CompressionInputItem, CompressionUiState, CompressionView


class TestCompressView:

    def test_can_instantiate(self, qtbot) -> None:
        view = CompressionView()
        qtbot.addWidget(view)

        assert view is not None

    def test_default_settings_match_requirements(self, qtbot) -> None:
        view = CompressionView()
        qtbot.addWidget(view)

        assert view.sld_jpeg_quality.value() == 75
        assert view.sld_png_quality.value() == 75
        assert view.sld_dpi.value() == 150
        assert view.chk_clean_metadata.isChecked() is False

    def test_update_ui_populates_inputs_and_progress(self, qtbot) -> None:
        view = CompressionView()
        qtbot.addWidget(view)

        state = CompressionUiState(
            input_items=[CompressionInputItem(path="C:/work/sample.pdf", label="[PDF] C:/work/sample.pdf")],
            output_dir_text="C:/out",
            progress_text="進捗: 1 / 2 (50%)",
            summary_text="成功: 1件 / 失敗: 0件 / スキップ: 0件",
            progress_value=50,
            can_execute=True,
            can_remove_selected=True,
            can_clear_inputs=True,
        )

        view.update_ui(state)

        assert view.input_list.count() == 1
        assert view.txt_output_dir.text() == "C:/out"
        assert view.progress_bar.value() == 50
        assert view.btn_execute.isEnabled()

    def test_drop_event_emits_local_paths(self, qtbot, tmp_path) -> None:
        view = CompressionView()
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

    def test_update_ui_applies_toggle_state_and_disables_controls(self, qtbot) -> None:
        view = CompressionView()
        qtbot.addWidget(view)

        state = CompressionUiState(
            mode="lossless",
            linearize=False,
            object_streams=False,
            recompress_streams=False,
            remove_unreferenced=False,
            clean_metadata=True,
            can_add_inputs=False,
            can_choose_output=False,
            can_execute=False,
            can_edit_settings=False,
        )

        view.update_ui(state)

        assert view.cmb_mode.currentData() == "lossless"
        assert view.chk_linearize.isChecked() is False
        assert view.chk_object_streams.isChecked() is False
        assert view.chk_recompress_streams.isChecked() is False
        assert view.chk_remove_unreferenced.isChecked() is False
        assert view.chk_clean_metadata.isChecked() is True
        assert view.btn_add_pdf.isEnabled() is False
        assert view.btn_choose_output.isEnabled() is False
        assert view.cmb_mode.isEnabled() is False

    def test_selected_input_paths_return_underlying_paths(self, qtbot) -> None:
        view = CompressionView()
        qtbot.addWidget(view)

        state = CompressionUiState(
            input_items=[
                CompressionInputItem(path="C:/one.pdf", label="[PDF] C:/one.pdf"),
                CompressionInputItem(path="C:/two.pdf", label="[PDF] C:/two.pdf"),
            ],
            can_remove_selected=True,
            can_clear_inputs=True,
        )
        view.update_ui(state)

        view.input_list.item(1).setSelected(True)

        assert view.get_selected_input_paths() == ["C:/two.pdf"]
        assert view.btn_remove_selected.isEnabled() is True
