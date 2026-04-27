from __future__ import annotations

from pathlib import Path

from model.flatten.flatten_session import (
    FlattenBatchPlan,
    FlattenCandidate,
    FlattenConflict,
    FlattenJob,
    FlattenSession,
)
from model.flatten.flatten_processor import FlattenProcessor
from view.flatten.flatten_view import FlattenInputItem, FlattenUiState
from view.main_window import MainWindow


_OVERWRITE_PREVIEW_LIMIT = 3


class FlattenPresenter:
    """Model と PDF フラット化画面 View を調停する Presenter。"""

    def __init__(self, view: MainWindow) -> None:
        self._view = view
        self._session = FlattenSession()
        self._processor = FlattenProcessor()
        self._poll_job_id: str | None = None
        self._close_after_cancel = False
        self._status = "idle"
        self._last_error_message: str | None = None
        self._recent_successes: list[dict[str, object]] = []
        self._recent_failures: list[dict[str, object]] = []
        self._recent_warnings: list[dict[str, object]] = []
        self._recent_skips: list[dict[str, object]] = []
        self._input_items_cache: list[FlattenInputItem] = []

        self._session.refresh_external_tool_state()
        self._view.set_flatten_presenter(self)
        self._refresh_ui()

    def has_active_session(self) -> bool:
        return bool(self._session.input_paths)

    def is_busy(self) -> bool:
        return self._processor.is_running

    def add_pdf_files(self) -> None:
        paths = self._view.ask_open_files("PDFファイルを選択", "PDF Files (*.pdf)")
        self._append_inputs(paths)

    def add_folder(self) -> None:
        path = self._view.ask_directory("入力フォルダを選択")
        if path:
            self._append_inputs([path])

    def handle_dropped_paths(self, paths: list[str]) -> None:
        self._append_inputs(paths)

    def remove_selected_inputs(self) -> None:
        if self._processor.is_running:
            self._view.show_info("実行中", "フラット化処理の実行中は入力を変更できません。")
            return

        for path in self._view.get_selected_flatten_inputs():
            self._session.remove_input(path)
        self._rebuild_input_items_cache()
        self._refresh_ui()

    def clear_inputs(self) -> None:
        if self._processor.is_running:
            self._view.show_info("実行中", "フラット化処理の実行中は入力を変更できません。")
            return

        self._session.clear_inputs()
        self._input_items_cache = []
        self._refresh_ui()

    def set_post_compression_enabled(self, enabled: bool) -> None:
        self._session.refresh_external_tool_state()
        if enabled and not self._session.ghostscript_available:
            self._view.show_error("Ghostscript未検出", "Ghostscript が見つからないため、後処理圧縮は有効化できません。")
            self._session.set_post_compression_enabled(False)
        else:
            self._session.set_post_compression_enabled(enabled)
        self._refresh_ui()

    def set_flatten_annots_enabled(self, enabled: bool) -> None:
        self._session.set_flatten_annots_enabled(enabled)
        self._refresh_ui()

    def set_flatten_widgets_enabled(self, enabled: bool) -> None:
        self._session.set_flatten_widgets_enabled(enabled)
        self._refresh_ui()

    def set_ghostscript_preset(self, preset: str) -> None:
        self._session.set_ghostscript_preset(preset)
        self._refresh_ui()

    def set_post_compression_use_pikepdf(self, enabled: bool) -> None:
        self._session.set_post_compression_use_pikepdf(enabled)
        self._refresh_ui()

    def execute_flatten(self) -> None:
        if self._processor.is_running:
            return

        if not self._session.input_paths:
            self._view.show_error("入力不足", "フラット化対象のPDFまたはフォルダを追加してください。")
            return

        if not (self._session.flatten_annots_enabled or self._session.flatten_widgets_enabled):
            self._view.show_error("設定不足", "アノテーションまたはフォームフィールドの少なくとも一方を有効にしてください。")
            return

        self._session.refresh_external_tool_state()

        initial_plan = self._processor.prepare_batch(self._session)
        resolved_plan = self._resolve_plan(initial_plan)
        if not resolved_plan.jobs and not resolved_plan.preflight_issues:
            self._view.show_info("対象なし", "処理対象のPDFが見つかりませんでした。")
            return

        self._session.begin_batch(0)
        self._recent_successes.clear()
        self._recent_failures.clear()
        self._recent_warnings.clear()
        self._recent_skips.clear()
        self._close_after_cancel = False
        self._status = "running"
        self._last_error_message = None
        self._processor.start_flatten(self._session, resolved_plan)
        self._refresh_ui()
        self._ensure_polling(delay_ms=0, force_initial=True)

    def on_closing(self) -> None:
        if self._processor.is_running:
            if not self._view.ask_ok_cancel(
                "確認",
                "現在PDFフラット化処理中です。終了すると未完了ジョブが中断されます。本当に終了しますか？",
            ):
                return

            self._close_after_cancel = True
            self._status = "cancelling"
            self._processor.request_cancel()
            self._refresh_ui()
            self._ensure_polling()
            return

        if self._poll_job_id is not None:
            self._view.cancel_schedule(self._poll_job_id)
            self._poll_job_id = None

        self._view.destroy_window()

    def _append_inputs(self, paths: list[str]) -> None:
        if self._processor.is_running:
            self._view.show_info("実行中", "フラット化処理の実行中は入力を変更できません。")
            return

        existing = {Path(path).as_posix().casefold() for path in self._session.input_paths}
        accepted: list[str] = []
        ignored: list[str] = []

        for raw_path in paths:
            normalized = str(Path(raw_path))
            key = Path(normalized).as_posix().casefold()
            if key in existing:
                continue

            path = Path(normalized)
            if path.exists() and ((path.is_file() and path.suffix.lower() == ".pdf") or path.is_dir()):
                accepted.append(normalized)
                existing.add(key)
            else:
                ignored.append(normalized)

        if accepted:
            self._session.add_inputs(accepted)
            self._rebuild_input_items_cache()
            self._refresh_ui()

        if ignored:
            preview = "\n".join(f"- {path}" for path in ignored[:5])
            suffix = "\n..." if len(ignored) > 5 else ""
            self._view.show_info(
                "一部入力を無視",
                f"PDF 以外、存在しないファイル、または不正な入力は追加しませんでした。\n{preview}{suffix}",
            )

    def _poll_flatten_results(self) -> None:
        finished_result: dict[str, object] | None = None
        top_level_failure: dict[str, object] | None = None
        cancelled_result: dict[str, object] | None = None

        for result in self._processor.poll_results():
            result_type = result.get("type")
            if result_type == "success":
                self._recent_successes.append(result)
            if result_type == "failure" and result.get("item") is None:
                top_level_failure = result
            elif result_type == "warning":
                self._recent_warnings.append(result)
            elif result_type == "failure":
                self._recent_failures.append(result)
            elif result_type == "skipped":
                self._recent_skips.append(result)
            elif result_type == "finished":
                finished_result = result
            elif result_type == "cancelled":
                cancelled_result = result

        self._refresh_ui()

        if self._processor.is_running:
            self._poll_job_id = self._view.schedule(100, self._poll_flatten_results)
            return

        self._poll_job_id = None

        if cancelled_result is not None:
            self._status = "cancelled"
            self._refresh_ui()
            if self._close_after_cancel:
                self._close_after_cancel = False
                self.on_closing()
                return

            self._view.show_info(
                "キャンセル",
                str(cancelled_result.get("message", "PDFフラット化をキャンセルしました。")),
            )
            return

        if top_level_failure is not None:
            self._status = "error"
            self._last_error_message = str(
                top_level_failure.get("message", "PDFフラット化中にエラーが発生しました。"),
            )
            self._refresh_ui()
            self._view.show_error("フラット化エラー", self._last_error_message)
            return

        if finished_result is not None:
            self._status = "finished"
            self._refresh_ui()
            self._view.show_info(self._build_completion_title(), self._build_completion_message(finished_result))

    def _build_completion_title(self) -> str:
        if self._recent_warnings:
            return "フラット化完了（圧縮は一部スキップされました）"
        return "フラット化完了"

    def _build_completion_message(self, result: dict[str, object]) -> str:
        lines = [
            "PDFフラット化が完了しました。",
            f"成功: {result.get('success_count', 0)}件",
            f"警告: {result.get('warning_count', 0)}件",
            f"失敗: {result.get('failure_count', 0)}件",
            f"スキップ: {result.get('skip_count', 0)}件",
        ]

        size_lines = self._build_size_lines()
        if size_lines:
            lines.append("")
            lines.extend(size_lines)

        if self._recent_warnings:
            lines.append("")
            lines.append("圧縮スキップ例:")
            for warning in self._recent_warnings[:3]:
                lines.append(
                    f"- {warning.get('item', 'unknown')}: {warning.get('message', 'warning')}",
                )

        if self._recent_failures:
            lines.append("")
            lines.append("失敗例:")
            for failure in self._recent_failures[:3]:
                lines.append(
                    f"- {failure.get('item', 'unknown')}: {failure.get('message', 'error')}",
                )

        if self._recent_skips:
            lines.append("")
            lines.append("スキップ例:")
            for skipped in self._recent_skips[:3]:
                lines.append(
                    f"- {skipped.get('item', 'unknown')}: {skipped.get('reason', 'skipped')}",
                )

        return "\n".join(lines)

    def _build_size_lines(self) -> list[str]:
        successful_results = self._recent_successes + self._recent_warnings
        if not successful_results:
            return []

        total_input = 0
        total_output = 0
        for result in successful_results:
            total_input += self._coerce_int(result.get("input_bytes", 0))
            total_output += self._coerce_int(result.get("output_bytes", 0))

        if total_input <= 0:
            return [
                "フラット化前総容量: 算出不可",
                "フラット化後総容量: 算出不可",
                "増減量: 算出不可",
            ]

        delta_bytes = total_output - total_input
        sign = "+" if delta_bytes >= 0 else "-"
        return [
            f"フラット化前総容量: {self._format_size(total_input)}",
            f"フラット化後総容量: {self._format_size(total_output)}",
            f"増減量: {sign}{self._format_size(abs(delta_bytes))}",
        ]

    def _format_size(self, size_bytes: int) -> str:
        units = ("B", "KB", "MB", "GB", "TB")
        value = float(max(0, size_bytes))
        unit_index = 0
        while value >= 1024 and unit_index < len(units) - 1:
            value /= 1024
            unit_index += 1
        return f"{value:.1f} {units[unit_index]}"

    def _coerce_int(self, value: object) -> int:
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                return 0
        return 0

    def _build_ui_state(self) -> FlattenUiState:
        is_running = self._processor.is_running
        total_items = self._session.total_items
        processed_items = self._session.processed_items
        progress_value = 0 if is_running and total_items == 0 else self._session.progress_percent

        if self._status == "cancelling":
            progress_text = "キャンセル中..."
        elif is_running and total_items > 0:
            progress_text = (
                f"進捗: {processed_items} / {total_items} "
                f"({progress_value}%)"
            )
        else:
            progress_text = "待機中"

        summary_text = (
            f"成功: {self._session.success_count}件 / "
            f"警告: {self._session.warning_count}件 / "
            f"失敗: {self._session.failure_count}件 / "
            f"スキップ: {self._session.skip_count}件"
        )

        return FlattenUiState(
            input_items=list(self._input_items_cache),
            progress_text=progress_text,
            summary_text=summary_text,
            progress_value=progress_value,
            flatten_annots_enabled=self._session.flatten_annots_enabled,
            flatten_widgets_enabled=self._session.flatten_widgets_enabled,
            post_compression_enabled=self._session.post_compression_enabled,
            ghostscript_preset=self._session.ghostscript_preset,
            post_compression_use_pikepdf=self._session.post_compression_use_pikepdf,
            ghostscript_available=self._session.ghostscript_available,
            ghostscript_status_text=self._build_ghostscript_status_text(),
            can_add_inputs=not is_running,
            can_remove_selected=bool(self._session.input_paths) and not is_running,
            can_clear_inputs=bool(self._session.input_paths) and not is_running,
            can_execute=(
                bool(self._session.input_paths)
                and (self._session.flatten_annots_enabled or self._session.flatten_widgets_enabled)
                and not is_running
            ),
            can_back_home=not is_running,
            can_edit_flatten_options=not is_running,
            can_edit_post_compression=not is_running,
            can_edit_post_compression_details=(
                not is_running
                and self._session.post_compression_enabled
                and self._session.ghostscript_available
            ),
            is_running=is_running,
        )

    def _build_ghostscript_status_text(self) -> str:
        if self._session.ghostscript_available:
            return ""
        return "Ghostscript が見つからないため、フラット化後の圧縮は利用できません。Windows レジストリ、PATH、同梱バイナリの順で探索します。"

    def _refresh_ui(self) -> None:
        self._view.update_flatten_ui(self._build_ui_state())

    def _rebuild_input_items_cache(self) -> None:
        items: list[FlattenInputItem] = []
        for raw_path in self._session.input_paths:
            path = Path(raw_path)
            prefix = "[DIR]" if path.is_dir() else "[PDF]"
            items.append(FlattenInputItem(path=raw_path, label=f"{prefix} {raw_path}"))
        self._input_items_cache = items

    def _ensure_polling(self, delay_ms: int = 100, force_initial: bool = False) -> None:
        if self._poll_job_id is None and (force_initial or self._processor.is_running):
            self._poll_job_id = self._view.schedule(delay_ms, self._poll_flatten_results)

    def _resolve_plan(self, initial_plan: FlattenBatchPlan) -> FlattenBatchPlan:
        if not initial_plan.conflicts:
            return initial_plan

        conflicts = list(initial_plan.conflicts)
        overwrite = self._view.ask_yes_no(
            "上書き確認",
            self._build_overwrite_confirmation_message(conflicts),
        )

        jobs = list(initial_plan.jobs)
        preflight_issues = list(initial_plan.preflight_issues)

        if overwrite:
            jobs.extend(self._conflicts_to_jobs(conflicts))
        else:
            preflight_issues.extend(self._conflicts_to_skip_issues(conflicts))

        return FlattenBatchPlan(jobs=jobs, conflicts=[], preflight_issues=preflight_issues)

    def _conflicts_to_jobs(self, conflicts: list[FlattenConflict]) -> list[FlattenJob]:
        jobs: list[FlattenJob] = []
        for conflict in conflicts:
            jobs.append(
                FlattenJob(
                    candidate=FlattenCandidate(
                        source_path=conflict.source_path,
                        source_label=conflict.source_path,
                    ),
                    output_path=conflict.output_path,
                    allow_overwrite=True,
                ),
            )
        return jobs

    def _conflicts_to_skip_issues(self, conflicts: list[FlattenConflict]) -> list[dict[str, object]]:
        issues: list[dict[str, object]] = []
        for conflict in conflicts:
            issues.append(
                {
                    "type": "skipped",
                    "item": conflict.source_path,
                    "reason": f"existing output: {conflict.output_path}",
                },
            )
        return issues

    def _build_overwrite_confirmation_message(self, conflicts: list[FlattenConflict]) -> str:
        lines = [
            f"出力先に既存のフラット化済みPDFが {len(conflicts)} 件あります。",
            "はい: 衝突分も一括で上書きして続行します。",
            "いいえ: 衝突分だけスキップして続行します。",
            "",
            "競合例:",
        ]
        for conflict in conflicts[:_OVERWRITE_PREVIEW_LIMIT]:
            lines.append(f"- {conflict.output_path}")
        if len(conflicts) > _OVERWRITE_PREVIEW_LIMIT:
            lines.append("- ...")
        return "\n".join(lines)