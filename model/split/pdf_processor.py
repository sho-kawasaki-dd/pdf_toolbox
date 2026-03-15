"""非同期でのPDF分割・保存処理。

UIに一切依存しない。スレッドとキューで非同期処理を管理し、
結果を ``result_queue`` 経由で呼び出し側に通知する。
"""

from __future__ import annotations

import queue
import threading
from pathlib import Path

import fitz  # PyMuPDF


class PdfProcessor:
    """バックグラウンドスレッドでPDFを分割・保存する。"""

    def __init__(self) -> None:
        self.is_splitting: bool = False
        self.result_queue: queue.Queue[dict] = queue.Queue()

    # ------------------------------------------------------------------
    # 公開API
    # ------------------------------------------------------------------

    def start_split(
        self,
        source_pdf_path: str,
        out_dir: str,
        jobs: list[dict],
    ) -> None:
        """PDF分割をバックグラウンドスレッドで開始する。

        結果は ``result_queue`` に ``{'type': 'success', 'file_count': N}``
        または ``{'type': 'error', 'message': '...'}`` として投入される。

        Args:
            source_pdf_path: 元PDFファイルのパス。
            out_dir: 出力先ディレクトリのパス。
            jobs: ``SplitSession.collect_split_jobs()`` が返すジョブ記述子のリスト。
        """
        if self.is_splitting:
            return

        # 滞留している古い結果を除去
        self._drain_queue()

        self.is_splitting = True
        worker = threading.Thread(
            target=self._split_worker,
            args=(source_pdf_path, out_dir, jobs),
            daemon=True,
        )
        worker.start()

    def poll_results(self) -> list[dict]:
        """キューに溜まっている結果をすべて取り出して返す。"""
        results: list[dict] = []
        while True:
            try:
                results.append(self.result_queue.get_nowait())
            except queue.Empty:
                break
        return results

    def drain_queue(self) -> None:
        """キューを空にする（公開版）。"""
        self._drain_queue()

    # ------------------------------------------------------------------
    # 内部メソッド
    # ------------------------------------------------------------------

    def _drain_queue(self) -> None:
        while True:
            try:
                self.result_queue.get_nowait()
            except queue.Empty:
                break

    def _split_worker(
        self,
        source_pdf_path: str,
        out_dir: str,
        jobs: list[dict],
    ) -> None:
        output_dir = Path(out_dir)
        current_job_desc = "(初期化中)"

        try:
            with fitz.open(source_pdf_path) as source_doc:
                for job in jobs:
                    current_job_desc = (
                        f"{job['index']}番目のセクション（{job['filename']}）"
                    )
                    out_path = self._ensure_unique_output_path(
                        output_dir, job["filename"]
                    )

                    with fitz.open() as new_doc:
                        new_doc.insert_pdf(
                            source_doc,
                            from_page=job["start"],
                            to_page=job["end"],
                        )
                        try:
                            new_doc.save(str(out_path))
                        except PermissionError as e:
                            self.result_queue.put(
                                {
                                    "type": "error",
                                    "message": (
                                        "保存先ファイルが他のアプリで使用中のため"
                                        "保存できませんでした。\n"
                                        f"対象ファイル: {out_path}\n"
                                        f"詳細: {e}"
                                    ),
                                }
                            )
                            return
        except Exception as e:
            self.result_queue.put(
                {
                    "type": "error",
                    "message": f"{current_job_desc}の保存中にエラーが発生しました:\n{e}",
                }
            )
            return
        finally:
            self.is_splitting = False

        self.result_queue.put({"type": "success", "file_count": len(jobs)})

    # ------------------------------------------------------------------
    # ユーティリティ
    # ------------------------------------------------------------------

    @staticmethod
    def _ensure_unique_output_path(output_dir: Path, filename: str) -> Path:
        """出力先パスが既存ファイルと衝突しないよう連番を付与する。"""
        target_path = output_dir / filename
        stem = target_path.stem
        suffix = target_path.suffix
        counter = 1

        while target_path.exists():
            target_path = output_dir / f"{stem} ({counter}){suffix}"
            counter += 1

        return target_path
