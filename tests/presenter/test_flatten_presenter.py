from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from model.compress.settings import PDF_GHOSTSCRIPT_PRESET_PRINTER
from model.flatten.flatten_session import FlattenBatchPlan, FlattenConflict, FlattenJob
from presenter.flatten_presenter import FlattenPresenter


def _make_mock_view() -> MagicMock:
    view = MagicMock()
    view.ask_open_files.return_value = []
    view.ask_directory.return_value = None
    view.get_selected_flatten_inputs.return_value = []
    view.ask_ok_cancel.return_value = False
    view.ask_yes_no.return_value = True
    view.schedule.return_value = "timer_1"
    return view


class TestFlattenPresenter:

    def test_defaults_disable_execution(self) -> None:
        view = _make_mock_view()
        FlattenPresenter(view)

        state = view.update_flatten_ui.call_args[0][0]
        assert state.progress_text == "待機中"
        assert state.can_execute is False
        assert state.can_clear_inputs is False
        assert state.can_back_home is True

    def test_unavailable_ghostscript_disables_post_compression_controls(self, monkeypatch) -> None:
        monkeypatch.setattr("model.flatten.flatten_session.is_ghostscript_available", lambda: False)
        view = _make_mock_view()

        FlattenPresenter(view)

        state = view.update_flatten_ui.call_args[0][0]
        assert state.ghostscript_available is False
        assert state.post_compression_enabled is False
        assert "Ghostscript が見つからない" in state.ghostscript_status_text

    def test_post_compression_settings_propagate_to_ui(self, monkeypatch) -> None:
        monkeypatch.setattr("model.flatten.flatten_session.is_ghostscript_available", lambda: True)
        view = _make_mock_view()
        presenter = FlattenPresenter(view)
        view.reset_mock()

        presenter.set_post_compression_enabled(True)
        presenter.set_ghostscript_preset(PDF_GHOSTSCRIPT_PRESET_PRINTER)
        presenter.set_post_compression_use_pikepdf(True)

        state = view.update_flatten_ui.call_args[0][0]
        assert state.post_compression_enabled is True
        assert state.ghostscript_preset == PDF_GHOSTSCRIPT_PRESET_PRINTER
        assert state.post_compression_use_pikepdf is True
        assert state.can_edit_post_compression_details is True

    def test_add_pdf_files_updates_input_list(self, sample_pdf: Path) -> None:
        view = _make_mock_view()
        view.ask_open_files.return_value = [str(sample_pdf)]
        presenter = FlattenPresenter(view)
        view.reset_mock()

        presenter.add_pdf_files()

        state = view.update_flatten_ui.call_args[0][0]
        assert len(state.input_items) == 1
        assert state.input_items[0].path == str(sample_pdf)
        assert state.can_execute is True

    def test_add_folder_updates_input_list(self, tmp_path: Path) -> None:
        folder = tmp_path / "inputs"
        folder.mkdir()
        view = _make_mock_view()
        view.ask_directory.return_value = str(folder)
        presenter = FlattenPresenter(view)
        view.reset_mock()

        presenter.add_folder()

        state = view.update_flatten_ui.call_args[0][0]
        assert len(state.input_items) == 1
        assert state.input_items[0].path == str(folder)
        assert "[DIR]" in state.input_items[0].label

    def test_handle_dropped_paths_ignores_unsupported_inputs(self, sample_pdf: Path, tmp_path: Path) -> None:
        view = _make_mock_view()
        unsupported = tmp_path / "notes.txt"
        unsupported.write_text("ignore", encoding="utf-8")
        presenter = FlattenPresenter(view)
        view.reset_mock()

        presenter.handle_dropped_paths([str(sample_pdf), str(unsupported), str(tmp_path / "missing.pdf")])

        state = view.update_flatten_ui.call_args[0][0]
        assert len(state.input_items) == 1
        assert state.input_items[0].path == str(sample_pdf)
        view.show_info.assert_called_once()
        assert "不正な入力" in view.show_info.call_args[0][1]

    def test_handle_dropped_paths_deduplicates_existing_inputs(self, sample_pdf: Path) -> None:
        view = _make_mock_view()
        presenter = FlattenPresenter(view)
        presenter.handle_dropped_paths([str(sample_pdf)])
        view.reset_mock()

        presenter.handle_dropped_paths([str(sample_pdf)])

        assert presenter.has_active_session() is True
        assert presenter._session.input_paths == [str(sample_pdf)]
        view.update_flatten_ui.assert_not_called()

    def test_remove_selected_inputs_updates_state(self, sample_pdf: Path, tmp_path: Path) -> None:
        second_pdf = tmp_path / "second.pdf"
        second_pdf.write_bytes(sample_pdf.read_bytes())
        view = _make_mock_view()
        view.get_selected_flatten_inputs.return_value = [str(sample_pdf)]
        presenter = FlattenPresenter(view)
        presenter.handle_dropped_paths([str(sample_pdf), str(second_pdf)])
        view.reset_mock()

        presenter.remove_selected_inputs()

        state = view.update_flatten_ui.call_args[0][0]
        assert [item.path for item in state.input_items] == [str(second_pdf)]

    def test_clear_inputs_clears_session(self, sample_pdf: Path) -> None:
        view = _make_mock_view()
        presenter = FlattenPresenter(view)
        presenter.handle_dropped_paths([str(sample_pdf)])
        view.reset_mock()

        presenter.clear_inputs()

        state = view.update_flatten_ui.call_args[0][0]
        assert state.input_items == []
        assert state.can_execute is False
        assert presenter.has_active_session() is False

    def test_execute_flatten_starts_processor_and_polling(self, sample_pdf: Path, tmp_path: Path) -> None:
        view = _make_mock_view()
        presenter = FlattenPresenter(view)
        presenter.handle_dropped_paths([str(sample_pdf)])

        plan = FlattenBatchPlan(
            jobs=[
                FlattenJob(
                    candidate=presenter._session and presenter._processor.prepare_batch(presenter._session).jobs[0].candidate,
                    output_path=str(tmp_path / "sample_flattened.pdf"),
                ),
            ],
        )

        def fake_start(_session, _plan) -> None:
            presenter._processor.is_running = True

        presenter._processor.prepare_batch = MagicMock(return_value=plan)
        presenter._processor.start_flatten = MagicMock(side_effect=fake_start)
        view.reset_mock()

        presenter.execute_flatten()

        presenter._processor.start_flatten.assert_called_once()
        view.schedule.assert_called_once()
        assert view.schedule.call_args[0][0] == 0
        state = view.update_flatten_ui.call_args[0][0]
        assert state.can_execute is False
        assert presenter.is_busy() is True

    def test_execute_flatten_yes_branch_converts_conflicts_to_overwrite_jobs(self, sample_pdf: Path) -> None:
        view = _make_mock_view()
        view.ask_yes_no.return_value = True
        presenter = FlattenPresenter(view)
        presenter.handle_dropped_paths([str(sample_pdf)])
        output_path = str(sample_pdf.with_name(f"{sample_pdf.stem}_flattened.pdf"))
        presenter._processor.prepare_batch = MagicMock(
            return_value=FlattenBatchPlan(
                conflicts=[FlattenConflict(source_path=str(sample_pdf), output_path=output_path)],
            ),
        )

        captured_plan: FlattenBatchPlan | None = None

        def fake_start(_session, plan: FlattenBatchPlan) -> None:
            nonlocal captured_plan
            captured_plan = plan
            presenter._processor.is_running = True

        presenter._processor.start_flatten = MagicMock(side_effect=fake_start)
        view.reset_mock()

        presenter.execute_flatten()

        view.ask_yes_no.assert_called_once()
        assert captured_plan is not None
        assert len(captured_plan.jobs) == 1
        assert captured_plan.jobs[0].allow_overwrite is True
        assert captured_plan.preflight_issues == []

    def test_execute_flatten_no_branch_converts_conflicts_to_skips(self, sample_pdf: Path) -> None:
        view = _make_mock_view()
        view.ask_yes_no.return_value = False
        presenter = FlattenPresenter(view)
        presenter.handle_dropped_paths([str(sample_pdf)])
        output_path = str(sample_pdf.with_name(f"{sample_pdf.stem}_flattened.pdf"))
        presenter._processor.prepare_batch = MagicMock(
            return_value=FlattenBatchPlan(
                conflicts=[FlattenConflict(source_path=str(sample_pdf), output_path=output_path)],
            ),
        )

        captured_plan: FlattenBatchPlan | None = None

        def fake_start(_session, plan: FlattenBatchPlan) -> None:
            nonlocal captured_plan
            captured_plan = plan
            presenter._processor.is_running = True

        presenter._processor.start_flatten = MagicMock(side_effect=fake_start)
        view.reset_mock()

        presenter.execute_flatten()

        view.ask_yes_no.assert_called_once()
        assert captured_plan is not None
        assert captured_plan.jobs == []
        assert len(captured_plan.preflight_issues) == 1
        assert captured_plan.preflight_issues[0]["type"] == "skipped"
        assert "existing output" in str(captured_plan.preflight_issues[0]["reason"])

    def test_poll_results_reschedules_while_running(self) -> None:
        view = _make_mock_view()
        presenter = FlattenPresenter(view)
        presenter._processor.is_running = True
        presenter._processor.poll_results = MagicMock(return_value=[
            {"type": "failure", "item": "bad.pdf", "message": "broken"},
        ])
        view.reset_mock()

        presenter._poll_flatten_results()

        view.schedule.assert_called_once()
        view.show_error.assert_not_called()
        assert presenter._recent_failures[0]["message"] == "broken"

    def test_poll_results_shows_completion_dialog(self) -> None:
        view = _make_mock_view()
        presenter = FlattenPresenter(view)
        presenter._processor.is_running = False
        presenter._processor.poll_results = MagicMock(return_value=[
            {"type": "failure", "item": "bad.pdf", "message": "broken"},
            {"type": "skipped", "item": "skip.pdf", "reason": "existing output"},
            {"type": "finished", "success_count": 2, "failure_count": 1, "skip_count": 1},
        ])

        presenter._poll_flatten_results()

        view.show_info.assert_called_once()
        assert view.show_info.call_args[0][0] == "フラット化完了"
        message = view.show_info.call_args[0][1]
        assert "成功: 2件" in message
        assert "失敗例:" in message
        assert "スキップ例:" in message

    def test_poll_results_shows_partial_success_message(self) -> None:
        view = _make_mock_view()
        presenter = FlattenPresenter(view)
        presenter._processor.is_running = False
        presenter._processor.poll_results = MagicMock(return_value=[
            {
                "type": "warning",
                "item": "sample.pdf",
                "message": "フラット化完了（圧縮はスキップされました）: Ghostscript compression failed",
            },
            {"type": "finished", "success_count": 0, "warning_count": 1, "failure_count": 0, "skip_count": 0},
        ])

        presenter._poll_flatten_results()

        view.show_info.assert_called_once()
        assert view.show_info.call_args[0][0] == "フラット化完了（圧縮は一部スキップされました）"
        message = view.show_info.call_args[0][1]
        assert "警告: 1件" in message
        assert "圧縮スキップ例:" in message

    def test_on_closing_requests_cancel_while_busy(self) -> None:
        view = _make_mock_view()
        view.ask_ok_cancel.return_value = True
        presenter = FlattenPresenter(view)
        presenter._processor.is_running = True
        presenter._processor.request_cancel = MagicMock()
        view.reset_mock()

        presenter.on_closing()

        presenter._processor.request_cancel.assert_called_once()
        view.schedule.assert_called_once()
        state = view.update_flatten_ui.call_args[0][0]
        assert state.can_back_home is False

    def test_on_closing_destroys_window_when_idle(self) -> None:
        view = _make_mock_view()
        presenter = FlattenPresenter(view)
        presenter._poll_job_id = "timer_1"
        view.reset_mock()

        presenter.on_closing()

        view.cancel_schedule.assert_called_once_with("timer_1")
        view.destroy_window.assert_called_once()