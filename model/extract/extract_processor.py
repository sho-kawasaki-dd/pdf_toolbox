"""PDF 抽出処理を別スレッドで実行するプロセッサ。"""

from __future__ import annotations

import os
import queue
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path

import pikepdf

from model.extract.extract_session import SourcePageRef


@dataclass(slots=True, frozen=True)
class ExtractPageSpec:
    """抽出対象 1 ページの仕様。"""

    source_path: str
    page_index: int


class ExtractCancelledError(Exception):
    """抽出処理がキャンセルされたことを表す内部例外。"""


class ExtractProcessor:
    """PDF 抽出をバックグラウンドスレッドで実行する。"""

    def __init__(self) -> None:
        self.is_running = False
        self.result_queue: queue.Queue[dict[str, object]] = queue.Queue()
        self._cancel_event = threading.Event()

    @property
    def is_cancelling(self) -> bool:
        return self.is_running and self._cancel_event.is_set()

    def start_extract(self, pages: list[ExtractPageSpec], output_path: str) -> None:
        """未実行時のみ新しい抽出バッチを開始する。"""
        if self.is_running:
            return

        self._drain_queue()
        self._cancel_event.clear()
        self.is_running = True
        worker = threading.Thread(
            target=self._extract_worker,
            args=(pages[:], output_path),
            daemon=True,
        )
        worker.start()

    def request_cancel(self) -> None:
        """進行中の抽出処理にキャンセル要求を出す。"""
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

    def _extract_worker(self, pages: list[ExtractPageSpec], output_path: str) -> None:
        total = len(pages)
        processed = 0
        output = Path(output_path)
        temp_output = output.with_name(f".{output.stem}.extracting-{uuid.uuid4().hex}.pdf")

        try:
            if total == 0:
                raise ValueError("抽出対象のページがありません。")

            output.parent.mkdir(parents=True, exist_ok=True)
            dest_pdf = pikepdf.new()

            # ソース PDF をキャッシュして同一ファイルの再オープンを避ける
            opened: dict[str, pikepdf.Pdf] = {}
            try:
                for spec in pages:
                    self._raise_if_cancelled()
                    src = self._get_source_pdf(spec.source_path, opened)
                    self._append_page(dest_pdf, src, spec)
                    processed += 1
                    self.result_queue.put({
                        "type": "progress",
                        "processed": processed,
                        "total": total,
                    })

                self._raise_if_cancelled()
                dest_pdf.save(str(temp_output))
            finally:
                dest_pdf.close()
                for pdf in opened.values():
                    pdf.close()

            self._raise_if_cancelled()
            os.replace(temp_output, output)
            self.result_queue.put({
                "type": "finished",
                "processed": processed,
                "total": total,
                "output_path": str(output),
            })
        except ExtractCancelledError:
            self._cleanup_temp(temp_output)
            self.result_queue.put({
                "type": "cancelled",
                "processed": processed,
                "total": total,
                "message": "PDF抽出をキャンセルしました。",
            })
        except Exception as exc:
            self._cleanup_temp(temp_output)
            self.result_queue.put({
                "type": "failure",
                "processed": processed,
                "total": total,
                "message": str(exc),
            })
        finally:
            self.is_running = False
            self._cancel_event.clear()

    def _get_source_pdf(self, path: str, cache: dict[str, pikepdf.Pdf]) -> pikepdf.Pdf:
        if path in cache:
            return cache[path]
        p = Path(path)
        if not p.exists() or not p.is_file():
            raise FileNotFoundError(f"入力ファイルが見つかりません: {path}")
        try:
            pdf = pikepdf.open(path)
        except Exception:
            raise ValueError(f"不正なPDFのため読み込めませんでした: {path}") from None
        cache[path] = pdf
        return pdf

    def _append_page(
        self, dest: pikepdf.Pdf, src: pikepdf.Pdf, spec: ExtractPageSpec,
    ) -> None:
        if spec.page_index < 0 or spec.page_index >= len(src.pages):
            raise IndexError(
                f"ページ {spec.page_index} は範囲外です "
                f"(0..{len(src.pages) - 1}): {spec.source_path}"
            )
        dest.pages.append(src.pages[spec.page_index])

    def _raise_if_cancelled(self) -> None:
        if self._cancel_event.is_set():
            raise ExtractCancelledError()

    def _cleanup_temp(self, temp_output: Path) -> None:
        try:
            if temp_output.exists():
                temp_output.unlink()
        except OSError:
            pass
