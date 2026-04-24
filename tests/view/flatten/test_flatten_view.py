from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QMimeData, QPointF, Qt, QUrl
from PySide6.QtGui import QDropEvent

from view.flatten.flatten_view import FlattenInputItem, FlattenUiState, FlattenView


class TestFlattenView:

    def test_can_instantiate(self, qtbot) -> None:
        view = FlattenView()
        qtbot.addWidget(view)

        assert view is not None

    def test_initial_button_states_match_requirements(self, qtbot) -> None:
        view = FlattenView()
        qtbot.addWidget(view)

        assert view.btn_add_pdf.isEnabled() is True
        assert view.btn_add_folder.isEnabled() is True
        assert view.btn_remove_selected.isEnabled() is False
        assert view.btn_clear.isEnabled() is False
        assert view.btn_execute.isEnabled() is False
        assert view.btn_back_home.isEnabled() is True

    def test_update_ui_populates_inputs_and_progress(self, qtbot) -> None:
        view = FlattenView()
        qtbot.addWidget(view)

        state = FlattenUiState(
            input_items=[FlattenInputItem(path="C:/work/sample.pdf", label="[PDF] C:/work/sample.pdf")],
            progress_text="進捗: 1 / 2 (50%)",
            summary_text="成功: 1件 / 失敗: 0件 / スキップ: 0件",
            progress_value=50,
            can_execute=True,
            can_clear_inputs=True,
        )

        view.update_ui(state)

        assert view.input_list.count() == 1
        assert view.progress_bar.value() == 50
        assert view.lbl_progress.text() == "進捗: 1 / 2 (50%)"
        assert view.btn_execute.isEnabled() is True

    def test_selection_enables_remove_button_when_allowed(self, qtbot) -> None:
        view = FlattenView()
        qtbot.addWidget(view)

        view.update_ui(
            FlattenUiState(
                input_items=[
                    FlattenInputItem(path="C:/one.pdf", label="[PDF] C:/one.pdf"),
                    FlattenInputItem(path="C:/two.pdf", label="[PDF] C:/two.pdf"),
                ],
                can_remove_selected=True,
                can_clear_inputs=True,
            ),
        )

        view.input_list.item(1).setSelected(True)

        assert view.get_selected_input_paths() == ["C:/two.pdf"]
        assert view.btn_remove_selected.isEnabled() is True

    def test_running_state_disables_input_controls(self, qtbot) -> None:
        view = FlattenView()
        qtbot.addWidget(view)

        view.update_ui(
            FlattenUiState(
                input_items=[FlattenInputItem(path="C:/work/sample.pdf", label="[PDF] C:/work/sample.pdf")],
                can_add_inputs=False,
                can_remove_selected=False,
                can_clear_inputs=False,
                can_execute=False,
                can_back_home=False,
                is_running=True,
            ),
        )

        assert view.btn_add_pdf.isEnabled() is False
        assert view.btn_add_folder.isEnabled() is False
        assert view.btn_remove_selected.isEnabled() is False
        assert view.btn_clear.isEnabled() is False
        assert view.btn_execute.isEnabled() is False
        assert view.btn_back_home.isEnabled() is False
        assert view.input_list.acceptDrops() is False

    def test_drop_event_emits_local_pdf_and_folder_paths(self, qtbot, tmp_path: Path) -> None:
        view = FlattenView()
        qtbot.addWidget(view)
        received: list[list[str]] = []
        view.input_list.paths_dropped.connect(received.append)

        pdf_path = tmp_path / "sample.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\n")
        folder = tmp_path / "folder"
        folder.mkdir()

        mime_data = QMimeData()
        mime_data.setUrls([
            QUrl.fromLocalFile(str(pdf_path)),
            QUrl.fromLocalFile(str(folder)),
        ])
        event = QDropEvent(
            QPointF(10, 10),
            Qt.DropAction.CopyAction,
            mime_data,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )

        view.input_list.dropEvent(event)

        assert len(received) == 1
        assert [Path(path) for path in received[0]] == [pdf_path, folder]

    def test_drop_event_ignores_non_file_urls(self, qtbot) -> None:
        view = FlattenView()
        qtbot.addWidget(view)
        received: list[list[str]] = []
        view.input_list.paths_dropped.connect(received.append)

        mime_data = QMimeData()
        mime_data.setUrls([QUrl("https://example.com/sample.pdf")])
        event = QDropEvent(
            QPointF(10, 10),
            Qt.DropAction.CopyAction,
            mime_data,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )

        view.input_list.dropEvent(event)

        assert received == []

    def test_back_button_emits_signal(self, qtbot) -> None:
        view = FlattenView()
        qtbot.addWidget(view)
        received: list[bool] = []
        view.back_to_home_requested.connect(lambda: received.append(True))

        view.btn_back_home.click()

        assert received == [True]