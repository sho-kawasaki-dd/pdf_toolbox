from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import fitz

from model.pdf_document import PdfDocument
from model.pdf_to_jpeg.pdf_to_jpeg_processor import PdfToJpegProcessor
from model.pdf_to_jpeg.pdf_to_jpeg_session import PdfToJpegSession
from view.pdf_to_jpeg.pdf_to_jpeg_view import PdfToJpegUiState


_PREVIEW_PLACEHOLDER = "PDFを選択すると\n先頭ページプレビューを表示します"
_WHITE_BACKGROUND_NOTE = "透明要素を含むページは白背景へ合成して JPEG 保存します。"
_SUPPORTED_SUFFIXES = frozenset({".pdf"})
_OVERWRITE_PREVIEW_LIMIT = 3
_DEFAULT_PREVIEW_SIZE = (320, 420)


class PdfToJpegPresenter:
    """Model と PDF→JPEG 画面 View を調停する Presenter。"""

    def __init__(self, view: Any) -> None:
        self._view = view
        self._session = PdfToJpegSession()
        self._processor = PdfToJpegProcessor()
        self._preview_document = PdfDocument(cache_limit=2)
        self._poll_job_id: str | None = None
        self._preview_png_bytes: bytes | None = None
        self._last_status = "idle"
        self._last_error_message: str | None = None
        self._recent_failures: list[dict[str, object]] = []

        if hasattr(self._view, "set_pdf_to_jpeg_presenter"):
            self._view.set_pdf_to_jpeg_presenter(self)
        self._refresh_ui()

    def has_active_session(self) -> bool:
        return bool(self._session.input_pdf_path or self._session.output_dir)

    def is_busy(self) -> bool:
        return self._processor.is_converting

    def choose_pdf_file(self) -> None:
        if self._processor.is_converting:
            self._view.show_info("実行中", "JPEG変換の実行中は入力PDFを変更できません。")
            return

        path = self._view.ask_open_file()
        if path:
            self._select_pdf(path)

    def handle_dropped_paths(self, paths: list[str]) -> None:
        if self._processor.is_converting:
            self._view.show_info("実行中", "JPEG変換の実行中は入力PDFを変更できません。")
            return

        valid_paths: list[str] = []
        ignored: list[str] = []

        for raw_path in paths:
            normalized = str(Path(raw_path))
            path = Path(normalized)
            if path.exists() and path.is_file() and path.suffix.lower() in _SUPPORTED_SUFFIXES:
                valid_paths.append(normalized)
            else:
                ignored.append(normalized)

        if not valid_paths:
            if ignored:
                preview = "\n".join(f"- {path}" for path in ignored[:5])
                suffix = "\n..." if len(ignored) > 5 else ""
                self._view.show_info(
                    "入力不可",
                    f"PDF 以外、または存在しないファイルは選択できません。\n{preview}{suffix}",
                )
            return

        self._select_pdf(valid_paths[0])

        if ignored or len(valid_paths) > 1:
            ignored_details = ignored[:]
            if len(valid_paths) > 1:
                ignored_details.extend(valid_paths[1:])
            preview = "\n".join(f"- {path}" for path in ignored_details[:5])
            suffix = "\n..." if len(ignored_details) > 5 else ""
            self._view.show_info(
                "単一PDFのみ対応",
                f"この機能では 1 件目の PDF のみ採用しました。\n{preview}{suffix}",
            )

    def choose_output_directory(self) -> None:
        if self._processor.is_converting:
            self._view.show_info("実行中", "JPEG変換の実行中は保存先を変更できません。")
            return

        path = self._view.ask_directory("保存先フォルダを選択")
        if path:
            self._session.set_output_dir(path)
            self._reset_runtime_feedback()
            self._refresh_ui()

    def set_jpeg_quality(self, quality: int) -> None:
        self._session.set_jpeg_quality(quality)
        self._refresh_ui()

    def execute_conversion(self) -> None:
        if self._processor.is_converting:
            return

        if self._session.input_pdf_path is None:
            self._view.show_error("入力不足", "変換対象のPDFを選択してください。")
            return

        if self._session.output_dir is None:
            self._view.show_error("保存先未選択", "保存先フォルダを選択してください。")
            return

        page_count = self._get_page_count()
        if page_count <= 0:
            self._view.show_error("変換不可", "ページを持たないPDFは変換できません。")
            return

        conflicts = self._session.collect_conflicting_output_paths(page_count)
        overwrite = False
        if conflicts:
            overwrite = self._view.ask_yes_no(
                "上書き確認",
                self._build_overwrite_confirmation_message(conflicts),
            )
            if not overwrite:
                return

        self._session.begin_batch(0)
        self._recent_failures.clear()
        self._last_error_message = None
        self._last_status = "running"
        self._processor.start_conversion(self._session, overwrite=overwrite)
        self._refresh_ui()

        if self._poll_job_id is None:
            self._poll_job_id = self._view.schedule(100, self._poll_results)

    def on_closing(self) -> None:
        if self._processor.is_converting:
            if not self._view.ask_ok_cancel(
                "確認",
                "現在PDF→JPEG変換処理中です。終了すると未完了ジョブが中断されます。本当に終了しますか？",
            ):
                return

        if self._poll_job_id is not None:
            self._view.cancel_schedule(self._poll_job_id)
            self._poll_job_id = None

        self._preview_document.close()
        self._view.destroy_window()

    def _select_pdf(self, raw_path: str) -> None:
        normalized = str(Path(raw_path))
        path = Path(normalized)
        if not path.exists() or not path.is_file() or path.suffix.lower() not in _SUPPORTED_SUFFIXES:
            self._view.show_error("入力不可", f"PDF ファイルを選択してください。\n{normalized}")
            return

        previous_path = self._session.input_pdf_path
        previous_preview = self._preview_png_bytes
        try:
            page_count = self._preview_document.open(normalized)
            if page_count <= 0:
                raise ValueError("ページを持たないPDFです。")

            frame_width, frame_height = self._get_preview_size()
            image, _, _ = self._preview_document.render_page_image(0, frame_width, frame_height, 1.0)
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")

            self._session.set_input_pdf(normalized)
            self._preview_png_bytes = buffer.getvalue()
            self._reset_runtime_feedback()
            self._refresh_ui()
        except Exception as exc:
            self._preview_document.close()
            self._preview_png_bytes = previous_preview
            self._session.set_input_pdf(previous_path)
            self._view.show_error("PDF読込エラー", str(exc))

    def _get_preview_size(self) -> tuple[int, int]:
        if hasattr(self._view, "get_pdf_to_jpeg_preview_size"):
            size = self._view.get_pdf_to_jpeg_preview_size()
            if isinstance(size, tuple) and len(size) == 2:
                width, height = size
                if width > 0 and height > 0:
                    return width, height
        return _DEFAULT_PREVIEW_SIZE

    def _get_page_count(self) -> int:
        input_path = self._session.input_pdf_path
        if input_path is None:
            return 0

        if self._preview_document.is_open and self._preview_document.source_path == input_path:
            return self._preview_document.page_count

        try:
            with fitz.open(input_path) as document:
                return document.page_count
        except Exception:
            return 0

    def _poll_results(self) -> None:
        finished_result: dict[str, object] | None = None
        top_level_failure: dict[str, object] | None = None

        for result in self._processor.poll_results():
            result_type = result.get("type")
            if result_type == "failure" and result.get("page_number") is not None:
                self._recent_failures.append(result)
            elif result_type == "failure":
                top_level_failure = result
            elif result_type == "finished":
                finished_result = result

        self._refresh_ui()

        if self._processor.is_converting:
            self._poll_job_id = self._view.schedule(100, self._poll_results)
            return

        self._poll_job_id = None

        if finished_result is not None:
            self._last_status = "finished"
            self._refresh_ui()
            self._view.show_info("変換完了", self._build_completion_message(finished_result))
            return

        if top_level_failure is not None:
            self._last_status = "error"
            self._last_error_message = str(top_level_failure.get("message", "JPEG変換中にエラーが発生しました。"))
            self._refresh_ui()
            self._view.show_error("変換エラー", self._last_error_message)

    def _build_overwrite_confirmation_message(self, conflicts: list[str]) -> str:
        lines = [
            f"出力先に同名の JPEG が {len(conflicts)} 件あります。",
            "承認すると対象を一括で上書きします。",
            "",
            "競合例:",
        ]
        for path in conflicts[:_OVERWRITE_PREVIEW_LIMIT]:
            lines.append(f"- {path}")
        if len(conflicts) > _OVERWRITE_PREVIEW_LIMIT:
            lines.append("- ...")
        return "\n".join(lines)

    def _build_completion_message(self, result: dict[str, object]) -> str:
        lines = [
            "PDF→JPEG変換が完了しました。",
            f"成功: {result.get('success_count', 0)}ページ",
            f"失敗: {result.get('failure_count', 0)}ページ",
            f"出力先: {result.get('output_dir', self._session.output_subfolder_path or '-')}",
        ]

        if self._recent_failures:
            lines.append("")
            lines.append("失敗例:")
            for failure in self._recent_failures[:3]:
                lines.append(
                    f"- {failure.get('page_number', '?')}ページ目: {failure.get('message', 'error')}",
                )

        return "\n".join(lines)

    def _reset_runtime_feedback(self) -> None:
        if self._processor.is_converting:
            return

        self._session.begin_batch(0)
        self._last_status = "idle"
        self._last_error_message = None
        self._recent_failures.clear()

    def _refresh_ui(self) -> None:
        self._view.update_pdf_to_jpeg_ui(self._build_ui_state())

    def _build_ui_state(self) -> PdfToJpegUiState:
        is_running = self._processor.is_converting
        total_pages = self._session.total_pages
        processed_pages = self._session.processed_pages
        progress_value = 0 if is_running and total_pages == 0 else self._session.progress_percent

        if is_running and total_pages == 0:
            progress_text = "変換ジョブを準備しています..."
        elif is_running and total_pages > 0:
            progress_text = (
                f"変換中: {processed_pages} / {total_pages} ページ "
                f"(現在: {self._session.current_page_number}ページ目)"
            )
        elif self._last_status == "finished" and total_pages > 0:
            progress_text = f"完了: {processed_pages} / {total_pages} ページ"
        elif self._last_status == "error" and self._last_error_message:
            progress_text = "エラー"
        else:
            progress_text = "待機中"

        output_subfolder = self._session.output_subfolder_path
        if output_subfolder:
            output_detail_text = f"出力先サブフォルダ: {output_subfolder}"
        elif self._session.output_dir:
            output_detail_text = "出力先サブフォルダ: 入力PDFを選択すると確定します"
        else:
            output_detail_text = "出力先サブフォルダ: 保存先フォルダを選択してください"

        return PdfToJpegUiState(
            selected_pdf_text=self._session.input_pdf_path or "変換対象の PDF を選択してください",
            output_dir_text=self._session.output_dir or "保存先フォルダを選択してください",
            output_detail_text=output_detail_text,
            note_text=_WHITE_BACKGROUND_NOTE,
            progress_text=progress_text,
            summary_text=(
                f"成功: {self._session.success_count}ページ / "
                f"失敗: {self._session.failure_count}ページ"
            ),
            progress_value=progress_value,
            jpeg_quality=self._session.jpeg_quality,
            current_page_number=self._session.current_page_number,
            preview_png_bytes=self._preview_png_bytes,
            preview_text=_PREVIEW_PLACEHOLDER if self._preview_png_bytes is None else "",
            has_input_pdf=self._session.input_pdf_path is not None,
            has_output_dir=self._session.output_dir is not None,
            has_preview=self._preview_png_bytes is not None,
            can_choose_pdf=not is_running,
            can_choose_output=not is_running,
            can_execute=self._session.can_execute() and not is_running,
            can_edit_quality=not is_running,
            can_back_home=not is_running,
            is_running=is_running,
        )