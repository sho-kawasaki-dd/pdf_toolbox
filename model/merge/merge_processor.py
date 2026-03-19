"""PDF 結合のバックグラウンド処理。"""

from __future__ import annotations

import os
import queue
import threading
import uuid
from pathlib import Path

import fitz


class MergeCancelledError(Exception):
    """結合処理がキャンセルされたことを表す内部例外。"""


class MergeProcessor:
    """PDF 結合をバックグラウンドスレッドで実行する。"""

    def __init__(self) -> None:
        self.is_merging = False
        self.result_queue: queue.Queue[dict[str, object]] = queue.Queue()
        self._cancel_event = threading.Event()

    @property
    def is_cancelling(self) -> bool:
        return self.is_merging and self._cancel_event.is_set()

    def start_merge(self, input_paths: list[str], output_path: str) -> None:
        """未実行時のみ新しい結合バッチを開始する。"""
        if self.is_merging:
            return

        self._drain_queue()
        self._cancel_event.clear()
        self.is_merging = True
        worker = threading.Thread(
            target=self._merge_worker,
            args=(input_paths[:], output_path),
            daemon=True,
        )
        worker.start()

    def request_cancel(self) -> None:
        """進行中の結合処理にキャンセル要求を出す。"""
        self._cancel_event.set()

    def poll_results(self) -> list[dict[str, object]]:
        """結果キューを読み切り、保留中メッセージをすべて返す。"""
        results: list[dict[str, object]] = []
        while True:
            try:
                results.append(self.result_queue.get_nowait())
            except queue.Empty:
                break
        return results

    def _drain_queue(self) -> None:
        while True:
            try:
                self.result_queue.get_nowait()
            except queue.Empty:
                break

    def _merge_worker(self, input_paths: list[str], output_path: str) -> None:
        total_items = len(input_paths)
        processed_items = 0
        total_pages = 0
        processed_pages = 0
        output = Path(output_path)
        temp_output = output.with_name(f".{output.stem}.merging-{uuid.uuid4().hex}.pdf")

        try:
            if total_items == 0:
                raise ValueError("結合対象のPDFがありません。")

            total_pages = self._count_total_pages(input_paths)
            self.result_queue.put({
                "type": "progress",
                "processed_items": processed_items,
                "total_items": total_items,
                "processed_pages": processed_pages,
                "total_pages": total_pages,
            })

            output.parent.mkdir(parents=True, exist_ok=True)
            merged_doc = fitz.open()
            try:
                for input_path in input_paths:
                    self._raise_if_cancelled()
                    appended_pages = self._append_input_pdf(
                        merged_doc,
                        Path(input_path),
                        total_items,
                        processed_items,
                        total_pages,
                        processed_pages,
                    )
                    processed_pages += appended_pages
                    processed_items += 1

                self._raise_if_cancelled()
                merged_doc.save(str(temp_output))
            finally:
                merged_doc.close()

            self._raise_if_cancelled()
            os.replace(temp_output, output)
            self.result_queue.put({
                "type": "finished",
                "processed_items": processed_items,
                "total_items": total_items,
                "processed_pages": processed_pages,
                "total_pages": total_pages,
                "output_path": str(output),
            })
        except MergeCancelledError:
            self._cleanup_temp_output(temp_output)
            self.result_queue.put({
                "type": "cancelled",
                "processed_items": processed_items,
                "total_items": total_items,
                "processed_pages": processed_pages,
                "total_pages": total_pages,
                "message": "PDF結合をキャンセルしました。",
            })
        except Exception as exc:
            self._cleanup_temp_output(temp_output)
            self.result_queue.put({
                "type": "failure",
                "processed_items": processed_items,
                "total_items": total_items,
                "processed_pages": processed_pages,
                "total_pages": total_pages,
                "message": str(exc),
            })
        finally:
            self.is_merging = False
            self._cancel_event.clear()

    def _count_total_pages(self, input_paths: list[str]) -> int:
        total_pages = 0
        for input_path in input_paths:
            with self._open_source_pdf(Path(input_path)) as source_doc:
                total_pages += source_doc.page_count
        return total_pages

    def _append_input_pdf(
        self,
        merged_doc: fitz.Document,
        input_path: Path,
        total_items: int,
        processed_items: int,
        total_pages: int,
        processed_pages: int,
    ) -> int:
        appended_pages = 0
        with self._open_source_pdf(input_path) as source_doc:
            for page_index in range(source_doc.page_count):
                self._raise_if_cancelled()
                merged_doc.insert_pdf(source_doc, from_page=page_index, to_page=page_index)
                appended_pages += 1
                self.result_queue.put({
                    "type": "progress",
                    "processed_items": processed_items,
                    "total_items": total_items,
                    "processed_pages": processed_pages + appended_pages,
                    "total_pages": total_pages,
                })

        return appended_pages

    def _open_source_pdf(self, input_path: Path) -> fitz.Document:
        if not input_path.exists() or not input_path.is_file():
            raise FileNotFoundError(f"入力ファイルが見つかりません: {input_path}")

        if input_path.suffix.lower() != ".pdf":
            raise ValueError(f"PDFではない入力が含まれています: {input_path}")

        try:
            source_doc = fitz.open(str(input_path))
        except fitz.FileDataError:
            raise ValueError(f"不正なPDFのため読み込めませんでした: {input_path}") from None
        except RuntimeError:
            raise ValueError(f"PDFを開けませんでした: {input_path}") from None

        if source_doc.page_count <= 0:
            source_doc.close()
            raise ValueError(f"ページを持たないPDFです: {input_path}")

        return source_doc

    def _raise_if_cancelled(self) -> None:
        if self._cancel_event.is_set():
            raise MergeCancelledError()

    def _cleanup_temp_output(self, temp_output: Path) -> None:
        try:
            if temp_output.exists():
                temp_output.unlink()
        except OSError:
            pass