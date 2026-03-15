from __future__ import annotations

from pathlib import Path

from model.compress.compression_processor import CompressionProcessor
from model.compress.compression_session import CompressionSession
from view.compress.compress_view import CompressionInputItem, CompressionUiState
from view.main_window import MainWindow


_SUPPORTED_FILE_SUFFIXES = frozenset({".pdf", ".zip"})


class CompressionPresenter:
    """Model と圧縮画面 View を調停する Presenter。"""

    def __init__(self, view: MainWindow) -> None:
        self._view = view
        self._session = CompressionSession()
        self._processor = CompressionProcessor()
        self._poll_job_id: str | None = None
        self._recent_failures: list[dict[str, object]] = []
        self._recent_skips: list[dict[str, object]] = []
        # 進捗更新のたびにフォルダや ZIP を再帰走査すると UI が重くなるため、
        # 一覧表示用ラベルは入力変更時だけ作り直してキャッシュする。
        self._input_items_cache: list[CompressionInputItem] = []

        self._view.set_compress_presenter(self)
        self._refresh_ui()

    def has_active_session(self) -> bool:
        return bool(self._session.input_paths)

    def is_busy(self) -> bool:
        return self._processor.is_compressing

    def add_pdf_files(self) -> None:
        """PDF 選択ダイアログから入力候補を追加する。"""
        paths = self._view.ask_open_files("PDFファイルを選択", "PDF Files (*.pdf)")
        self._append_inputs(paths)

    def add_folder(self) -> None:
        """フォルダ選択ダイアログから入力候補を追加する。"""
        path = self._view.ask_directory("入力フォルダを選択")
        if path:
            self._append_inputs([path])

    def add_zip_files(self) -> None:
        """ZIP 選択ダイアログから入力候補を追加する。"""
        paths = self._view.ask_open_files("ZIPファイルを選択", "ZIP Files (*.zip)")
        self._append_inputs(paths)

    def handle_dropped_paths(self, paths: list[str]) -> None:
        """DnD で渡されたローカルパス群を入力候補へ流す。"""
        self._append_inputs(paths)

    def remove_selected_inputs(self) -> None:
        if self._processor.is_compressing:
            self._view.show_info("実行中", "圧縮処理の実行中は入力を変更できません。")
            return

        for path in self._view.get_selected_compression_inputs():
            self._session.remove_input(path)
        self._rebuild_input_items_cache()
        self._refresh_ui()

    def clear_inputs(self) -> None:
        if self._processor.is_compressing:
            self._view.show_info("実行中", "圧縮処理の実行中は入力を変更できません。")
            return

        self._session.clear_inputs()
        self._input_items_cache = []
        self._refresh_ui()

    def choose_output_directory(self) -> None:
        if self._processor.is_compressing:
            self._view.show_info("実行中", "圧縮処理の実行中は保存先を変更できません。")
            return

        output_dir = self._view.ask_directory("保存先フォルダを選択")
        if output_dir:
            self._session.set_output_dir(output_dir)
            self._refresh_ui()

    def set_mode(self, mode: str) -> None:
        """圧縮モード変更後に、関連 UI の有効/無効も含めて再描画する。"""
        self._session.set_mode(mode)
        self._refresh_ui()

    def set_jpeg_quality(self, quality: int) -> None:
        """JPEG 品質だけを即座に Session へ反映する。"""
        self._session.set_jpeg_quality(quality)

    def set_png_quality(self, quality: int) -> None:
        """PNG 品質だけを即座に Session へ反映する。"""
        self._session.set_png_quality(quality)

    def set_dpi(self, dpi: int) -> None:
        """非可逆圧縮時の目標 DPI を Session へ反映する。"""
        self._session.set_lossy_dpi(dpi)

    def set_lossless_option(self, key: str, value: bool) -> None:
        """可逆最適化オプションの単一項目を更新する。"""
        self._session.update_lossless_options(**{key: value})

    def execute_compression(self) -> None:
        """入力検証後に圧縮を開始し、結果ポーリングを起動する。"""
        if self._processor.is_compressing:
            return

        if not self._session.input_paths:
            self._view.show_error("入力不足", "圧縮対象のPDF / フォルダ / ZIPを追加してください。")
            return

        if self._session.output_dir is None:
            self._view.show_error("保存先未選択", "保存先フォルダを選択してください。")
            return

        self._session.begin_batch(0)
        self._recent_failures.clear()
        self._recent_skips.clear()
        self._processor.start_compression(self._session)
        self._refresh_ui()

        if self._poll_job_id is None:
            # Processor はバックグラウンドスレッドで結果を積むだけなので、
            # UI 側はタイマーで定期取得してメインスレッド上で反映する。
            self._poll_job_id = self._view.schedule(100, self._poll_compression_results)

    def on_closing(self) -> None:
        """圧縮中の終了確認とタイマー後始末を行う。"""
        if self._processor.is_compressing:
            if not self._view.ask_ok_cancel(
                "確認",
                "現在PDFの圧縮処理中です。終了すると未完了ジョブが中断されます。本当に終了しますか？",
            ):
                return

        if self._poll_job_id is not None:
            self._view.cancel_schedule(self._poll_job_id)
            self._poll_job_id = None

        self._view.destroy_window()

    def _append_inputs(self, paths: list[str]) -> None:
        """対応形式だけを重複なく入力一覧へ追加する。"""
        if self._processor.is_compressing:
            self._view.show_info("実行中", "圧縮処理の実行中は入力を変更できません。")
            return

        existing = {str(Path(path)).casefold() for path in self._session.input_paths}
        accepted: list[str] = []
        ignored: list[str] = []

        for raw_path in paths:
            # Path で正規化しておくと、ダイアログ起点と DnD 起点で表記が揺れても
            # 同じ入力として重複除去しやすい。
            normalized = str(Path(raw_path))
            lowered = normalized.casefold()
            if lowered in existing:
                continue

            path = Path(normalized)
            if self._is_supported_input(path):
                accepted.append(normalized)
                existing.add(lowered)
            else:
                ignored.append(normalized)

        if accepted:
            self._session.add_inputs(accepted)
            # 表示ラベルは入力変更時だけ作り直し、進捗ポーリング時は再利用する。
            self._rebuild_input_items_cache()
            self._refresh_ui()

        if ignored:
            preview = "\n".join(f"- {path}" for path in ignored[:5])
            suffix = "\n..." if len(ignored) > 5 else ""
            self._view.show_info(
                "一部入力を無視",
                f"PDF / フォルダ / ZIP 以外の入力は追加しませんでした。\n{preview}{suffix}",
            )

    def _is_supported_input(self, path: Path) -> bool:
        """存在する PDF / ZIP / フォルダのみを受け付ける。"""
        if not path.exists():
            return False
        if path.is_dir():
            return True
        return path.suffix.lower() in _SUPPORTED_FILE_SUFFIXES

    def _poll_compression_results(self) -> None:
        """Processor の結果キューを読み、完了まで再スケジュールする。"""
        finished_result: dict[str, object] | None = None
        for result in self._processor.poll_results():
            result_type = result.get("type")
            if result_type == "failure":
                self._recent_failures.append(result)
            elif result_type == "skipped":
                self._recent_skips.append(result)
            elif result_type == "finished":
                finished_result = result

        self._refresh_ui()

        if self._processor.is_compressing:
            # 1 回限りのタイマーを都度張り直すことで、画面破棄時に確実に停止できる。
            self._poll_job_id = self._view.schedule(100, self._poll_compression_results)
            return

        self._poll_job_id = None
        if finished_result is not None:
            self._view.show_info("圧縮完了", self._build_completion_message(finished_result))
        elif self._recent_failures:
            first_failure = self._recent_failures[0]
            self._view.show_error(
                "圧縮エラー",
                str(first_failure.get("message", "圧縮処理中にエラーが発生しました。")),
            )

    def _build_completion_message(self, result: dict[str, object]) -> str:
        """完了ダイアログ用に集計結果と代表的な失敗理由を整形する。"""
        lines = [
            "PDF圧縮が完了しました。",
            f"成功: {result.get('success_count', 0)}件",
            f"失敗: {result.get('failure_count', 0)}件",
            f"スキップ: {result.get('skip_count', 0)}件",
        ]

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

    def _refresh_ui(self) -> None:
        """現在の Session/Processor 状態から View 全体を再描画する。"""
        self._view.update_compression_ui(self._build_ui_state())

    def _build_ui_state(self) -> CompressionUiState:
        """Session と Processor の状態から View 用の 1 つの状態オブジェクトを作る。"""
        is_running = self._processor.is_compressing
        total_items = self._session.total_items
        processed_items = self._session.processed_items
        progress_value = 0 if is_running and total_items == 0 else self._session.progress_percent

        if is_running and total_items == 0:
            # 入力解決中は総件数が未確定なので、進捗バーだけ 0% に固定し文言で補う。
            progress_text = "圧縮ジョブを準備しています..."
        elif total_items > 0:
            progress_text = (
                f"進捗: {processed_items} / {total_items} "
                f"({progress_value}%)"
            )
        else:
            progress_text = "待機中"

        output_dir_text = self._session.output_dir or "保存先フォルダを選択してください"
        summary_text = (
            f"成功: {self._session.success_count}件 / "
            f"失敗: {self._session.failure_count}件 / "
            f"スキップ: {self._session.skip_count}件"
        )

        # View には個別値ではなく状態スナップショットを渡し、
        # 画面更新の判断を 1 箇所へ閉じ込める。
        return CompressionUiState(
            input_items=list(self._input_items_cache),
            output_dir_text=output_dir_text,
            progress_text=progress_text,
            summary_text=summary_text,
            progress_value=progress_value,
            mode=self._session.mode,
            jpeg_quality=self._session.jpeg_quality,
            png_quality=self._session.png_quality,
            dpi=self._session.lossy_dpi,
            linearize=self._session.lossless_options["linearize"],
            object_streams=self._session.lossless_options["object_streams"],
            recompress_streams=self._session.lossless_options["recompress_streams"],
            remove_unreferenced=self._session.lossless_options["remove_unreferenced"],
            clean_metadata=self._session.lossless_options["clean_metadata"],
            can_add_inputs=not is_running,
            can_remove_selected=bool(self._session.input_paths) and not is_running,
            can_clear_inputs=bool(self._session.input_paths) and not is_running,
            can_choose_output=not is_running,
            can_execute=bool(self._session.input_paths) and self._session.output_dir is not None and not is_running,
            can_edit_settings=not is_running,
            can_back_home=True,
            is_running=is_running,
        )

    def _rebuild_input_items_cache(self) -> None:
        """入力一覧が変わった時だけ表示用ラベルを再構築する。"""
        items: list[CompressionInputItem] = []
        for raw_path in self._session.input_paths:
            path = Path(raw_path)
            # フォルダや ZIP の再帰走査は重いため、入力変更時にだけ要約を作る。
            candidates, skipped = self._processor._resolve_inputs([raw_path])
            label = self._format_input_label(path, len(candidates), len(skipped))
            items.append(CompressionInputItem(path=raw_path, label=label))
        self._input_items_cache = items

    def _format_input_label(self, path: Path, candidate_count: int, skipped_count: int) -> str:
        """入力種別と探索結果を一覧向けの短い説明文へ変換する。"""
        if path.is_dir():
            prefix = "Folder"
        elif path.suffix.lower() == ".zip":
            prefix = "ZIP"
        else:
            prefix = "PDF"

        summary_parts: list[str] = []
        if path.is_dir() or path.suffix.lower() == ".zip":
            summary_parts.append(f"PDF {candidate_count}件")
        elif candidate_count == 0:
            summary_parts.append("無効なPDF")

        if skipped_count:
            summary_parts.append(f"無視 {skipped_count}件")

        suffix = f" ({' / '.join(summary_parts)})" if summary_parts else ""
        return f"[{prefix}] {path}{suffix}"
