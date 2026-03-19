from __future__ import annotations

from pathlib import Path

from model.merge.merge_processor import MergeProcessor
from model.merge.merge_session import MergeSession
from model.merge.thumbnail_loader import ThumbnailLoader
from view.main_window import MainWindow
from view.merge.merge_view import MergeInputItem, MergeUiState


class MergePresenter:
    """Model と PDF 結合画面 View を調停する Presenter。"""

    def __init__(self, view: MainWindow) -> None:
        self._view = view
        self._session = MergeSession()
        self._merge_processor = MergeProcessor()
        self._thumbnail_loader = ThumbnailLoader()
        self._thumbnail_poll_job_id: str | None = None
        self._merge_poll_job_id: str | None = None
        self._close_after_cancel = False
        self._last_progress_processed = 0
        self._last_progress_total = 0
        self._last_progress_unit_label = "ページ"
        self._last_status = "idle"
        self._last_finished_output: str | None = None
        self._last_error_message: str | None = None

        self._view.set_merge_presenter(self)
        self._refresh_ui()

    def has_active_session(self) -> bool:
        return self._session.has_active_session()

    def is_busy(self) -> bool:
        return self._merge_processor.is_merging

    def add_pdf_files(self) -> None:
        """複数 PDF 選択ダイアログから入力候補を追加する。"""
        paths = self._view.ask_open_files("PDFファイルを選択", "PDF Files (*.pdf)")
        self._append_inputs(paths)

    def handle_dropped_paths(self, paths: list[str]) -> None:
        """DnD で渡されたローカルパス群を入力候補へ流す。"""
        self._append_inputs(paths)

    def set_selected_inputs(self, paths: list[str]) -> None:
        """View 側の現在選択を Session へ反映する。"""
        self._session.set_selected_paths(paths)
        self._refresh_ui()

    def move_selected_up(self) -> None:
        if self._merge_processor.is_merging:
            self._view.show_info("実行中", "結合処理の実行中は並び順を変更できません。")
            return

        if self._session.move_selected_up():
            self._reset_runtime_feedback()
            self._refresh_ui()

    def move_selected_down(self) -> None:
        if self._merge_processor.is_merging:
            self._view.show_info("実行中", "結合処理の実行中は並び順を変更できません。")
            return

        if self._session.move_selected_down():
            self._reset_runtime_feedback()
            self._refresh_ui()

    def reorder_inputs(self, paths: list[str]) -> None:
        """View 側 DnD の結果順序を Session へ反映する。"""
        if self._merge_processor.is_merging:
            self._view.show_info("実行中", "結合処理の実行中は並び順を変更できません。")
            return

        if self._session.reorder_inputs(paths):
            self._reset_runtime_feedback()
            self._refresh_ui()

    def remove_selected_inputs(self) -> None:
        if self._merge_processor.is_merging:
            self._view.show_info("実行中", "結合処理の実行中は入力を変更できません。")
            return

        if self._session.remove_selected_inputs():
            self._reset_runtime_feedback()
            self._refresh_ui()

    def choose_output_file(self) -> None:
        if self._merge_processor.is_merging:
            self._view.show_info("実行中", "結合処理の実行中は保存先を変更できません。")
            return

        path = self._view.ask_save_file("結合後PDFの保存先を選択", "PDF Files (*.pdf)")
        if path:
            self._session.set_output_path(path)
            self._reset_runtime_feedback()
            self._refresh_ui()

    def execute_merge(self) -> None:
        """入力検証後に結合処理を開始し、結果ポーリングを起動する。"""
        if self._merge_processor.is_merging:
            return

        if not self._session.input_paths:
            self._view.show_error("入力不足", "結合対象のPDFを追加してください。")
            return

        if self._session.output_path is None:
            self._view.show_error("保存先未選択", "結合後PDFの保存先を選択してください。")
            return

        output_path = Path(self._session.output_path)
        if output_path.exists() and not self._view.ask_yes_no(
            "上書き確認",
            f"保存先ファイルは既に存在します。上書きしてもよろしいですか？\n{output_path}",
        ):
            return

        self._session.begin_execution()
        self._close_after_cancel = False
        self._last_progress_processed = 0
        self._last_progress_total = 0
        self._last_progress_unit_label = "ページ"
        self._last_status = "running"
        self._last_finished_output = None
        self._last_error_message = None
        self._merge_processor.start_merge(self._session.input_paths, self._session.output_path)
        self._refresh_ui()
        self._ensure_merge_polling(delay_ms=0)

    def on_closing(self) -> None:
        """実行中ならキャンセル要求を出し、停止後に終了する。"""
        if self._merge_processor.is_merging:
            if not self._view.ask_ok_cancel(
                "確認",
                "現在PDF結合処理中です。終了すると未完了ジョブが中断されます。本当に終了しますか？",
            ):
                return

            self._close_after_cancel = True
            self._session.request_cancel()
            self._last_status = "cancelling"
            self._merge_processor.request_cancel()
            self._refresh_ui()
            self._ensure_merge_polling()
            return

        if self._thumbnail_poll_job_id is not None:
            self._view.cancel_schedule(self._thumbnail_poll_job_id)
            self._thumbnail_poll_job_id = None

        if self._merge_poll_job_id is not None:
            self._view.cancel_schedule(self._merge_poll_job_id)
            self._merge_poll_job_id = None

        self._view.destroy_window()

    def _append_inputs(self, paths: list[str]) -> None:
        if self._merge_processor.is_merging:
            self._view.show_info("実行中", "結合処理の実行中は入力を変更できません。")
            return

        accepted: list[str] = []
        ignored: list[str] = []
        duplicate_or_existing = {Path(path).as_posix().casefold() for path in self._session.input_paths}

        for raw_path in paths:
            normalized = str(Path(raw_path))
            key = Path(normalized).as_posix().casefold()
            if key in duplicate_or_existing:
                continue

            path = Path(normalized)
            if path.exists() and path.is_file() and path.suffix.lower() == ".pdf":
                accepted.append(normalized)
                duplicate_or_existing.add(key)
            else:
                ignored.append(normalized)

        if accepted:
            self._session.add_inputs(accepted)
            self._thumbnail_loader.request_thumbnails(accepted)
            self._ensure_thumbnail_polling()
            self._reset_runtime_feedback()
            self._refresh_ui()

        if ignored:
            preview = "\n".join(f"- {path}" for path in ignored[:5])
            suffix = "\n..." if len(ignored) > 5 else ""
            self._view.show_info(
                "一部入力を無視",
                f"PDF 以外、存在しないファイル、またはフォルダは追加しませんでした。\n{preview}{suffix}",
            )

    def _refresh_ui(self) -> None:
        self._view.update_merge_ui(self._build_ui_state())

    def _reset_runtime_feedback(self) -> None:
        """入力や保存先変更後に古い進捗・結果表示を初期状態へ戻す。"""
        if self._session.is_running:
            return

        self._last_progress_processed = 0
        self._last_progress_total = 0
        self._last_progress_unit_label = "ページ"
        self._last_status = "idle"
        self._last_finished_output = None
        self._last_error_message = None

    def _ensure_thumbnail_polling(self) -> None:
        if self._thumbnail_poll_job_id is None and self._thumbnail_loader.is_loading:
            self._thumbnail_poll_job_id = self._view.schedule(100, self._poll_thumbnail_results)

    def _ensure_merge_polling(self, delay_ms: int = 50) -> None:
        if self._merge_poll_job_id is None and self._merge_processor.is_merging:
            self._merge_poll_job_id = self._view.schedule(delay_ms, self._poll_merge_results)

    def _poll_thumbnail_results(self) -> None:
        results = self._thumbnail_loader.poll_results()
        if results:
            self._refresh_ui()

        if self._thumbnail_loader.is_loading:
            self._thumbnail_poll_job_id = self._view.schedule(100, self._poll_thumbnail_results)
            return

        self._thumbnail_poll_job_id = None

    def _poll_merge_results(self) -> None:
        finished_result: dict[str, object] | None = None
        failure_result: dict[str, object] | None = None
        cancelled_result: dict[str, object] | None = None

        for result in self._merge_processor.poll_results():
            result_type = result.get("type")
            if result_type == "progress":
                self._apply_progress_result(result)
            elif result_type == "finished":
                finished_result = result
            elif result_type == "failure":
                failure_result = result
            elif result_type == "cancelled":
                cancelled_result = result

        self._refresh_ui()

        if self._merge_processor.is_merging:
            self._merge_poll_job_id = self._view.schedule(50, self._poll_merge_results)
            return

        self._merge_poll_job_id = None
        self._session.finish_execution()
        self._session.cancel_requested = False

        if finished_result is not None:
            self._last_status = "finished"
            self._apply_progress_result(finished_result)
            self._last_finished_output = str(finished_result.get("output_path", ""))
            self._refresh_ui()
            self._view.schedule(0, lambda: self._view.show_info("結合完了", self._build_completion_message()))
            return

        if failure_result is not None:
            self._last_status = "error"
            self._last_error_message = str(failure_result.get("message", "PDF結合中にエラーが発生しました。"))
            self._apply_progress_result(failure_result)
            self._refresh_ui()
            self._view.schedule(0, lambda: self._view.show_error("結合エラー", self._last_error_message or "PDF結合中にエラーが発生しました。"))
            return

        if cancelled_result is not None:
            self._last_status = "cancelled"
            self._apply_progress_result(cancelled_result)
            self._refresh_ui()
            if self._close_after_cancel:
                self._close_after_cancel = False
                self.on_closing()
                return

            self._view.schedule(0, lambda: self._view.show_info("キャンセル", str(cancelled_result.get("message", "PDF結合をキャンセルしました。"))))

    def _to_int(self, value: object, default: int = 0) -> int:
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                return default
        return default

    def _apply_progress_result(self, result: dict[str, object]) -> None:
        total_pages = self._to_int(result.get("total_pages"))
        processed_pages = self._to_int(result.get("processed_pages"))
        if total_pages > 0:
            self._last_progress_processed = processed_pages
            self._last_progress_total = total_pages
            self._last_progress_unit_label = "ページ"
            return

        self._last_progress_processed = self._to_int(result.get("processed_items"))
        self._last_progress_total = self._to_int(result.get("total_items"))
        self._last_progress_unit_label = "件"

    def _build_completion_message(self) -> str:
        lines = [
            "PDF結合が完了しました。",
            f"入力数: {len(self._session.input_paths)}件",
            f"保存先: {self._last_finished_output or self._session.output_path or '-'}",
        ]
        return "\n".join(lines)

    def _calculate_progress_value(self) -> int:
        if self._last_status == "finished" and self._last_progress_total > 0:
            return 100

        if self._last_progress_total <= 0:
            return 0

        bounded_processed = min(self._last_progress_processed, self._last_progress_total)
        return int((bounded_processed / self._last_progress_total) * 100)

    def _build_ui_state(self) -> MergeUiState:
        items: list[MergeInputItem] = []
        for path in self._session.input_paths:
            thumbnail_result = self._thumbnail_loader.get_cached_result(path)
            thumbnail_status = "idle"
            thumbnail_text = "サムネイル\n未読込"
            thumbnail_png_bytes: bytes | None = None

            if thumbnail_result is not None:
                thumbnail_status = thumbnail_result.status
                if thumbnail_result.status == "ready":
                    thumbnail_png_bytes = thumbnail_result.image_bytes
                    thumbnail_text = ""
                else:
                    thumbnail_text = "サムネイル\n読込失敗"
            elif self._thumbnail_loader.is_pending(path):
                thumbnail_status = "loading"
                thumbnail_text = "サムネイル\n読込中"

            items.append(
                MergeInputItem(
                    path=path,
                    title=Path(path).name,
                    detail=path,
                    thumbnail_text=thumbnail_text,
                    thumbnail_status=thumbnail_status,
                    thumbnail_png_bytes=thumbnail_png_bytes,
                )
            )

        selected = self._session.selected_paths
        path_to_index = {path: index for index, path in enumerate(self._session.input_paths)}
        selected_indexes = [path_to_index[path] for path in selected if path in path_to_index]

        can_reorder = not self._session.is_running and bool(selected_indexes)
        can_move_up = can_reorder and min(selected_indexes) > 0
        can_move_down = can_reorder and max(selected_indexes) < len(self._session.input_paths) - 1

        if self._last_status == "running" and self._last_progress_total == 0:
            progress_text = "結合ジョブを準備しています..."
        elif self._last_status == "running":
            progress_text = f"結合中: {self._last_progress_processed} / {self._last_progress_total} {self._last_progress_unit_label}"
        elif self._last_status == "cancelling":
            progress_text = f"キャンセル中: {self._last_progress_processed} / {self._last_progress_total} {self._last_progress_unit_label}"
        elif self._last_status == "finished":
            progress_text = f"完了: {self._last_progress_total} / {self._last_progress_total} {self._last_progress_unit_label}"
        elif self._last_status == "error":
            progress_text = f"エラー: {self._last_progress_processed} / {self._last_progress_total} {self._last_progress_unit_label}"
        elif self._last_status == "cancelled":
            progress_text = f"キャンセル済み: {self._last_progress_processed} / {self._last_progress_total} {self._last_progress_unit_label}"
        else:
            progress_text = "待機中"

        progress_value = self._calculate_progress_value()

        return MergeUiState(
            input_items=items,
            selected_paths=selected[:],
            output_path_text=self._session.output_path or "結合後PDFの保存先を選択してください",
            progress_text=progress_text,
            progress_value=progress_value,
            can_add_inputs=not self._session.is_running,
            can_remove_selected=not self._session.is_running and bool(selected),
            can_move_up=can_move_up,
            can_move_down=can_move_down,
            can_choose_output=not self._session.is_running,
            can_execute=not self._session.is_running and bool(self._session.input_paths) and bool(self._session.output_path),
            can_back_home=not self._session.is_running,
            is_running=self._session.is_running,
        )