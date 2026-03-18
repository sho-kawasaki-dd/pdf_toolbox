"""PDF 抽出機能の Presenter。

Session / Processor / PageThumbnailLoader を統合し、
ExtractView の操作シグナルに応じて Model を更新→ UI 再描画する。
"""

from __future__ import annotations

from pathlib import Path

from model.extract.extract_processor import ExtractPageSpec, ExtractProcessor
from model.extract.extract_session import ExtractSession, SourcePageRef
from model.extract.page_thumbnail_loader import PageThumbnailLoader
from view.extract.extract_view import (
    ExtractUiState,
    SourcePageItem,
    SourceSectionItem,
    TargetItem,
)
from view.main_window import MainWindow


class ExtractPresenter:
    """Model と PDF 抽出画面 View を調停する Presenter。"""

    def __init__(self, view: MainWindow) -> None:
        self._view = view
        self._session = ExtractSession()
        self._processor = ExtractProcessor()
        self._thumbnail_loader = PageThumbnailLoader()
        self._thumbnail_poll_job_id: str | None = None
        self._extract_poll_job_id: str | None = None
        self._close_after_cancel = False
        self._last_progress_processed = 0
        self._last_progress_total = 0
        self._last_status = "idle"
        self._last_finished_output: str | None = None
        self._last_error_message: str | None = None

        self._view.set_extract_presenter(self)
        ev = self._view.extract_view

        # Source 操作
        ev.add_pdf_requested.connect(self.add_pdf_files)
        ev.remove_pdf_requested.connect(self.remove_selected_source)
        ev.source_page_clicked.connect(self._on_source_page_clicked)
        ev.source_page_double_clicked.connect(self._on_source_page_double_clicked)
        ev.source_zoom_in_requested.connect(self.zoom_in_source)
        ev.source_zoom_out_requested.connect(self.zoom_out_source)
        ev.source_zoom_reset_requested.connect(self.reset_source_zoom)
        ev.files_dropped.connect(self.handle_dropped_paths)

        # Target 操作
        ev.extract_to_target_requested.connect(self.extract_selected_to_target)
        ev.remove_target_requested.connect(self.remove_selected_targets)
        ev.clear_target_requested.connect(self.clear_target)
        ev.move_target_up_requested.connect(self.move_target_up)
        ev.move_target_down_requested.connect(self.move_target_down)
        ev.target_zoom_in_requested.connect(self.zoom_in_target)
        ev.target_zoom_out_requested.connect(self.zoom_out_target)
        ev.target_zoom_reset_requested.connect(self.reset_target_zoom)
        ev.target_list.selection_changed_ids.connect(self._on_target_selection_changed)
        ev.target_list.order_changed.connect(self._on_target_order_changed)
        ev.target_list.pages_dropped_from_source.connect(self._on_pages_dropped_from_source)

        # 出力
        ev.choose_output_requested.connect(self.choose_output_file)
        ev.execute_requested.connect(self.execute_extract)

        self._refresh_ui()

    # ── 公開クエリ ───────────────────────────────────────

    def has_active_session(self) -> bool:
        return self._session.has_active_session()

    def is_busy(self) -> bool:
        return self._processor.is_running

    # ── Source 操作 ──────────────────────────────────────

    def add_pdf_files(self) -> None:
        """複数 PDF 選択ダイアログから Source に追加する。"""
        paths = self._view.ask_open_files("PDFファイルを選択", "PDF Files (*.pdf)")
        self._append_sources(paths)

    def handle_dropped_paths(self, paths: list[str]) -> None:
        """DnD で渡されたパス群を Source に追加する。"""
        self._append_sources(paths)

    def remove_selected_source(self) -> None:
        """Source 上で最初に見つかった選択ページの所属 PDF を丸ごと削除する。"""
        if self._processor.is_running:
            self._view.show_info("実行中", "抽出処理の実行中は入力を変更できません。")
            return
        if not self._session.selected_source_pages:
            return
        doc_id = self._session.selected_source_pages[0].doc_id
        # パスを削除前に取得（削除後は get できない）
        doc = self._session.get_source_document(doc_id)
        doc_path = doc.path if doc else ""
        if self._session.remove_source(doc_id):
            if doc_path:
                self._thumbnail_loader.invalidate(doc_path)
            self._reset_runtime_feedback()
            self._refresh_ui()

    # ── Source 選択 ──────────────────────────────────────

    def _on_source_page_clicked(self, doc_id: str, page_index: int, event: object) -> None:
        """Source ページクリック: Ctrl / Shift 修飾で複数選択を制御する。"""
        from PySide6.QtCore import Qt

        modifiers = event.modifiers() if hasattr(event, "modifiers") else Qt.KeyboardModifier.NoModifier
        ref = SourcePageRef(doc_id=doc_id, page_index=page_index)

        if modifiers & Qt.KeyboardModifier.ControlModifier:
            # トグル
            current = list(self._session.selected_source_pages)
            if ref in current:
                current.remove(ref)
            else:
                current.append(ref)
            self._session.set_selected_source_pages(current)
        elif modifiers & Qt.KeyboardModifier.ShiftModifier:
            # 範囲選択: 同一 doc_id 内で最後の選択～クリック位置まで
            current = list(self._session.selected_source_pages)
            same_doc = [r for r in current if r.doc_id == doc_id]
            if same_doc:
                last = same_doc[-1].page_index
                lo, hi = min(last, page_index), max(last, page_index)
                for pi in range(lo, hi + 1):
                    r = SourcePageRef(doc_id=doc_id, page_index=pi)
                    if r not in current:
                        current.append(r)
                self._session.set_selected_source_pages(current)
            else:
                current.append(ref)
                self._session.set_selected_source_pages(current)
        else:
            self._session.set_selected_source_pages([ref])

        self._refresh_ui()

    def _on_source_page_double_clicked(self, doc_id: str, page_index: int) -> None:
        """Source ページダブルクリック: 即 Target に追加。"""
        ref = SourcePageRef(doc_id=doc_id, page_index=page_index)
        self._session.add_to_target([ref])
        self._reset_runtime_feedback()
        self._refresh_ui()

    def set_source_selection(self, refs: list[SourcePageRef]) -> None:
        """外部 (Ctrl+A 系) から選択を一括セットする。"""
        self._session.set_selected_source_pages(refs)
        self._refresh_ui()

    # ── Target 操作 ──────────────────────────────────────

    def extract_selected_to_target(self) -> None:
        """Source 選択ページを Target に追加する。"""
        if self._processor.is_running:
            return
        if not self._session.selected_source_pages:
            return
        self._session.add_to_target(list(self._session.selected_source_pages))
        self._reset_runtime_feedback()
        self._refresh_ui()

    def remove_selected_targets(self) -> None:
        if self._processor.is_running:
            self._view.show_info("実行中", "抽出処理の実行中は Target を変更できません。")
            return
        if self._session.remove_selected_targets():
            self._reset_runtime_feedback()
            self._refresh_ui()

    def clear_target(self) -> None:
        if self._processor.is_running:
            self._view.show_info("実行中", "抽出処理の実行中は Target を変更できません。")
            return
        if self._session.clear_target():
            self._reset_runtime_feedback()
            self._refresh_ui()

    def move_target_up(self) -> None:
        if self._processor.is_running:
            return
        if self._session.move_selected_target_up():
            self._reset_runtime_feedback()
            self._refresh_ui()

    def move_target_down(self) -> None:
        if self._processor.is_running:
            return
        if self._session.move_selected_target_down():
            self._reset_runtime_feedback()
            self._refresh_ui()

    def _on_target_selection_changed(self, ids: list[str]) -> None:
        self._session.set_selected_target_ids(ids)
        self._refresh_ui()

    def _on_target_order_changed(self, ordered_ids: list[str]) -> None:
        if self._processor.is_running:
            return
        if self._session.reorder_target(ordered_ids):
            self._reset_runtime_feedback()
            self._refresh_ui()

    def _on_pages_dropped_from_source(self, pages: list[dict]) -> None:
        """Target リストへ Source からドロップされたページを追加する。"""
        refs = [
            SourcePageRef(doc_id=p["doc_id"], page_index=p["page_index"])
            for p in pages
        ]
        self._session.add_to_target(refs)
        self._reset_runtime_feedback()
        self._refresh_ui()

    # ── ズーム ───────────────────────────────────────────

    def zoom_in_source(self) -> None:
        self._session.zoom_in_source()
        self._refresh_ui()

    def zoom_out_source(self) -> None:
        self._session.zoom_out_source()
        self._refresh_ui()

    def reset_source_zoom(self) -> None:
        self._session.reset_source_zoom()
        self._refresh_ui()

    def zoom_in_target(self) -> None:
        self._session.zoom_in_target()
        self._refresh_ui()

    def zoom_out_target(self) -> None:
        self._session.zoom_out_target()
        self._refresh_ui()

    def reset_target_zoom(self) -> None:
        self._session.reset_target_zoom()
        self._refresh_ui()

    # ── 出力 / 実行 ─────────────────────────────────────

    def choose_output_file(self) -> None:
        if self._processor.is_running:
            self._view.show_info("実行中", "抽出処理の実行中は保存先を変更できません。")
            return
        path = self._view.ask_save_file("抽出後PDFの保存先を選択", "PDF Files (*.pdf)")
        if path:
            self._session.set_output_path(path)
            self._reset_runtime_feedback()
            self._refresh_ui()

    def execute_extract(self) -> None:
        """入力検証後に抽出処理を開始し、結果ポーリングを起動する。"""
        if self._processor.is_running:
            return

        if not self._session.target_entries:
            self._view.show_error("入力不足", "抽出対象のページを Target に追加してください。")
            return

        if self._session.output_path is None:
            self._view.show_error("保存先未選択", "抽出後PDFの保存先を選択してください。")
            return

        output_path = Path(self._session.output_path)
        if output_path.exists() and not self._view.ask_yes_no(
            "上書き確認",
            f"保存先ファイルは既に存在します。上書きしてもよろしいですか？\n{output_path}",
        ):
            return

        # ページスペック構築
        pages: list[ExtractPageSpec] = []
        for entry in self._session.target_entries:
            doc = self._session.get_source_document(entry.source_ref.doc_id)
            if doc is None:
                continue
            pages.append(ExtractPageSpec(source_path=doc.path, page_index=entry.source_ref.page_index))

        self._session.begin_execution()
        self._close_after_cancel = False
        self._last_progress_processed = 0
        self._last_progress_total = len(pages)
        self._last_status = "running"
        self._last_finished_output = None
        self._last_error_message = None
        self._processor.start_extract(pages, self._session.output_path)
        self._refresh_ui()
        self._ensure_extract_polling()

    # ── 終了制御 ─────────────────────────────────────────

    def on_closing(self) -> None:
        """ウィンドウ終了時の処理。"""
        if self._processor.is_running:
            if not self._view.ask_ok_cancel(
                "確認",
                "現在PDF抽出処理中です。終了すると未完了ジョブが中断されます。本当に終了しますか？",
            ):
                return

            self._close_after_cancel = True
            self._session.request_cancel()
            self._last_status = "cancelling"
            self._processor.request_cancel()
            self._refresh_ui()
            self._ensure_extract_polling()
            return

        if self._thumbnail_poll_job_id is not None:
            self._view.cancel_schedule(self._thumbnail_poll_job_id)
            self._thumbnail_poll_job_id = None

        if self._extract_poll_job_id is not None:
            self._view.cancel_schedule(self._extract_poll_job_id)
            self._extract_poll_job_id = None

        self._view.destroy_window()

    # ── 内部: Source 追加 ────────────────────────────────

    def _append_sources(self, paths: list[str]) -> None:
        if self._processor.is_running:
            self._view.show_info("実行中", "抽出処理の実行中は入力を変更できません。")
            return

        import fitz

        accepted: list[str] = []
        ignored: list[str] = []

        for raw_path in paths:
            normalized = str(Path(raw_path))
            p = Path(normalized)
            if not p.exists() or not p.is_file() or p.suffix.lower() != ".pdf":
                ignored.append(normalized)
                continue

            try:
                doc = fitz.open(normalized)
                page_count = doc.page_count
                doc.close()
            except Exception:
                ignored.append(normalized)
                continue

            result = self._session.add_source(normalized, page_count)
            if result is None:
                # 重複
                continue
            accepted.append(normalized)

        if accepted:
            # サムネイルリクエスト: 追加した全ページ
            thumb_requests: list[tuple[str, int]] = []
            for path in accepted:
                for doc in self._session.source_documents:
                    if doc.path == path:
                        for pi in range(doc.page_count):
                            thumb_requests.append((path, pi))
                        break
            if thumb_requests:
                self._thumbnail_loader.request_thumbnails(thumb_requests)
                self._ensure_thumbnail_polling()
            self._reset_runtime_feedback()
            self._refresh_ui()

        if ignored:
            preview = "\n".join(f"- {p}" for p in ignored[:5])
            suffix = "\n..." if len(ignored) > 5 else ""
            self._view.show_info(
                "一部入力を無視",
                f"PDF以外、存在しないファイル、または不正なPDFは追加しませんでした。\n{preview}{suffix}",
            )

    # ── 内部: ポーリング ─────────────────────────────────

    def _ensure_thumbnail_polling(self) -> None:
        if self._thumbnail_poll_job_id is None and self._thumbnail_loader.is_loading:
            self._thumbnail_poll_job_id = self._view.schedule(100, self._poll_thumbnail_results)

    def _ensure_extract_polling(self) -> None:
        if self._extract_poll_job_id is None and self._processor.is_running:
            self._extract_poll_job_id = self._view.schedule(100, self._poll_extract_results)

    def _poll_thumbnail_results(self) -> None:
        results = self._thumbnail_loader.poll_results()
        if results:
            self._refresh_ui()

        if self._thumbnail_loader.is_loading:
            self._thumbnail_poll_job_id = self._view.schedule(100, self._poll_thumbnail_results)
            return

        self._thumbnail_poll_job_id = None

    def _poll_extract_results(self) -> None:
        finished_result: dict[str, object] | None = None
        failure_result: dict[str, object] | None = None
        cancelled_result: dict[str, object] | None = None

        for result in self._processor.poll_results():
            result_type = result.get("type")
            if result_type == "progress":
                self._last_progress_processed = int(result.get("processed", 0))
                self._last_progress_total = int(result.get("total", 0))
            elif result_type == "finished":
                finished_result = result
            elif result_type == "failure":
                failure_result = result
            elif result_type == "cancelled":
                cancelled_result = result

        self._refresh_ui()

        if self._processor.is_running:
            self._extract_poll_job_id = self._view.schedule(100, self._poll_extract_results)
            return

        self._extract_poll_job_id = None
        self._session.finish_execution()
        self._session.cancel_requested = False

        if finished_result is not None:
            self._last_status = "finished"
            self._last_progress_processed = int(finished_result.get("processed", self._last_progress_processed))
            self._last_progress_total = int(finished_result.get("total", self._last_progress_total))
            self._last_finished_output = str(finished_result.get("output_path", ""))
            self._refresh_ui()
            self._view.show_info("抽出完了", self._build_completion_message())
            return

        if failure_result is not None:
            self._last_status = "error"
            self._last_error_message = str(failure_result.get("message", "PDF抽出中にエラーが発生しました。"))
            self._last_progress_processed = int(failure_result.get("processed", self._last_progress_processed))
            self._last_progress_total = int(failure_result.get("total", self._last_progress_total))
            self._refresh_ui()
            self._view.show_error("抽出エラー", self._last_error_message)
            return

        if cancelled_result is not None:
            self._last_status = "cancelled"
            self._last_progress_processed = int(cancelled_result.get("processed", self._last_progress_processed))
            self._last_progress_total = int(cancelled_result.get("total", self._last_progress_total))
            self._refresh_ui()
            if self._close_after_cancel:
                self._close_after_cancel = False
                self.on_closing()
                return
            self._view.show_info("キャンセル", str(cancelled_result.get("message", "PDF抽出をキャンセルしました。")))

    def _build_completion_message(self) -> str:
        lines = [
            "PDF抽出が完了しました。",
            f"ページ数: {self._last_progress_total}ページ",
            f"保存先: {self._last_finished_output or self._session.output_path or '-'}",
        ]
        return "\n".join(lines)

    # ── 内部: UI 更新 ────────────────────────────────────

    def _refresh_ui(self) -> None:
        self._view.update_extract_ui(self._build_ui_state())

    def _reset_runtime_feedback(self) -> None:
        if self._session.is_running:
            return
        self._last_progress_processed = 0
        self._last_progress_total = 0
        self._last_status = "idle"
        self._last_finished_output = None
        self._last_error_message = None

    def _build_ui_state(self) -> ExtractUiState:
        # Source セクション構築
        source_sections: list[SourceSectionItem] = []
        selected_set = set(self._session.selected_source_pages)

        for doc in self._session.source_documents:
            pages: list[SourcePageItem] = []
            for pi in range(doc.page_count):
                ref = SourcePageRef(doc_id=doc.id, page_index=pi)
                cached = self._thumbnail_loader.get_cached(doc.path, pi)
                thumb_bytes: bytes | None = None
                thumb_status = "idle"
                if cached is not None:
                    thumb_status = cached.status
                    if cached.status == "ready":
                        thumb_bytes = cached.image_bytes
                elif self._thumbnail_loader.is_pending(doc.path, pi):
                    thumb_status = "loading"

                pages.append(SourcePageItem(
                    doc_id=doc.id,
                    page_index=pi,
                    thumbnail_png_bytes=thumb_bytes,
                    thumbnail_status=thumb_status,
                    is_selected=ref in selected_set,
                ))
            source_sections.append(SourceSectionItem(
                doc_id=doc.id,
                filename=Path(doc.path).name,
                page_count=doc.page_count,
                pages=pages,
            ))

        # Target アイテム構築
        target_items: list[TargetItem] = []
        selected_target_set = set(self._session.selected_target_ids)
        for entry in self._session.target_entries:
            doc = self._session.get_source_document(entry.source_ref.doc_id)
            filename = Path(doc.path).name if doc else "?"
            path = doc.path if doc else ""
            cached = self._thumbnail_loader.get_cached(path, entry.source_ref.page_index) if path else None
            thumb_bytes = None
            thumb_status = "idle"
            if cached is not None:
                thumb_status = cached.status
                if cached.status == "ready":
                    thumb_bytes = cached.image_bytes
            elif path and self._thumbnail_loader.is_pending(path, entry.source_ref.page_index):
                thumb_status = "loading"

            target_items.append(TargetItem(
                entry_id=entry.id,
                doc_id=entry.source_ref.doc_id,
                page_index=entry.source_ref.page_index,
                source_filename=filename,
                thumbnail_png_bytes=thumb_bytes,
                thumbnail_status=thumb_status,
                is_selected=entry.id in selected_target_set,
            ))

        # ボタン状態
        has_source_selection = bool(self._session.selected_source_pages)
        has_target_selection = bool(self._session.selected_target_ids)
        is_running = self._session.is_running

        # 移動可否
        can_move_up = False
        can_move_down = False
        if has_target_selection and not is_running:
            selected_ids_set = set(self._session.selected_target_ids)
            entries = self._session.target_entries
            selected_indices = [i for i, e in enumerate(entries) if e.id in selected_ids_set]
            if selected_indices:
                can_move_up = min(selected_indices) > 0
                can_move_down = max(selected_indices) < len(entries) - 1

        # 進捗テキスト
        if self._last_status == "running":
            progress_text = f"抽出中: {self._last_progress_processed} / {self._last_progress_total} ページ"
        elif self._last_status == "cancelling":
            progress_text = f"キャンセル中: {self._last_progress_processed} / {self._last_progress_total} ページ"
        elif self._last_status == "finished":
            progress_text = f"完了: {self._last_progress_total} / {self._last_progress_total} ページ"
        elif self._last_status == "error":
            progress_text = f"エラー: {self._last_progress_processed} / {self._last_progress_total} ページ"
        elif self._last_status == "cancelled":
            progress_text = f"キャンセル済み: {self._last_progress_processed} / {self._last_progress_total} ページ"
        else:
            progress_text = "待機中"

        return ExtractUiState(
            source_sections=source_sections,
            target_items=target_items,
            source_zoom_percent=self._session.source_zoom_percent,
            target_zoom_percent=self._session.target_zoom_percent,
            output_path_text=self._session.output_path or "抽出後PDFの保存先を選択してください",
            progress_text=progress_text,
            can_add_pdf=not is_running,
            can_remove_pdf=not is_running and has_source_selection,
            can_extract=not is_running and has_source_selection,
            can_remove_target=not is_running and has_target_selection,
            can_clear_target=not is_running and bool(self._session.target_entries),
            can_move_up=can_move_up,
            can_move_down=can_move_down,
            can_choose_output=not is_running,
            can_execute=self._session.can_execute(),
            can_back_home=not is_running,
            is_running=is_running,
        )
