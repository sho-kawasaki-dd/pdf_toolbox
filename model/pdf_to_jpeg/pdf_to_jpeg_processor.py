from __future__ import annotations

"""PDF を全ページ JPEG としてバックグラウンド書き出しする。"""

import queue
import threading
from pathlib import Path

import fitz
from PIL import Image

from model.pdf_to_jpeg.pdf_to_jpeg_session import PdfToJpegSession


DEFAULT_RENDER_DPI = 150


class PdfToJpegProcessor:
    """単一 PDF をページ単位で JPEG へ変換する。"""

    def __init__(self, render_dpi: int = DEFAULT_RENDER_DPI) -> None:
        if render_dpi <= 0:
            raise ValueError("Render DPI must be positive")

        self.is_converting = False
        self.result_queue: queue.Queue[dict[str, object]] = queue.Queue()
        self._render_dpi = render_dpi

    def start_conversion(self, session: PdfToJpegSession, overwrite: bool = False) -> None:
        """未実行時のみ新しい変換バッチを開始する。"""
        if self.is_converting:
            return

        self._drain_queue()
        self.is_converting = True
        worker = threading.Thread(
            target=self._conversion_worker,
            args=(session, overwrite),
            daemon=True,
        )
        worker.start()

    def poll_results(self) -> list[dict[str, object]]:
        """結果キューを読み切って返す。"""
        results: list[dict[str, object]] = []
        while True:
            try:
                results.append(self.result_queue.get_nowait())
            except queue.Empty:
                break
        return results

    def drain_queue(self) -> None:
        """古いキューメッセージを公開 API として破棄する。"""
        self._drain_queue()

    def _drain_queue(self) -> None:
        while True:
            try:
                self.result_queue.get_nowait()
            except queue.Empty:
                break

    def _conversion_worker(self, session: PdfToJpegSession, overwrite: bool) -> None:
        try:
            if not session.can_execute():
                raise ValueError("入力PDFと保存先フォルダを設定してください。")

            input_pdf_path = Path(session.input_pdf_path or "")
            if not input_pdf_path.exists() or not input_pdf_path.is_file():
                raise FileNotFoundError(f"入力ファイルが見つかりません: {input_pdf_path}")
            if input_pdf_path.suffix.lower() != ".pdf":
                raise ValueError(f"PDFではない入力が指定されています: {input_pdf_path}")

            try:
                with fitz.open(str(input_pdf_path)) as document:
                    self._export_document(document, session, overwrite)
            except (fitz.FileDataError, RuntimeError):
                raise ValueError(f"不正なPDFのため読み込めませんでした: {input_pdf_path}") from None
        except Exception as exc:
            self.result_queue.put({"type": "failure", "message": str(exc)})
        finally:
            self.is_converting = False

    def _export_document(
        self,
        document: fitz.Document,
        session: PdfToJpegSession,
        overwrite: bool,
    ) -> None:
        page_count = document.page_count
        if page_count <= 0:
            raise ValueError("ページを持たないPDFは変換できません。")

        conflicts = session.collect_conflicting_output_paths(page_count)
        if conflicts and not overwrite:
            raise FileExistsError("出力先に同名のJPEGが既に存在します。")

        output_dir = Path(session.output_subfolder_path or "")
        output_dir.mkdir(parents=True, exist_ok=True)

        session.begin_batch(page_count)
        render_scale = self._render_dpi / 72.0
        matrix = fitz.Matrix(render_scale, render_scale)

        for page_number in range(1, page_count + 1):
            session.mark_page_started(page_number)
            output_path = output_dir / session.build_output_filename(page_number)

            try:
                page = document.load_page(page_number - 1)
                image = self._render_page_to_rgb(page, matrix)
                image.save(
                    output_path,
                    format="JPEG",
                    quality=session.jpeg_quality,
                )
                session.record_success()
                self.result_queue.put({
                    "type": "success",
                    "page_number": page_number,
                    "output_path": str(output_path),
                })
            except Exception as exc:
                session.record_failure()
                self.result_queue.put({
                    "type": "failure",
                    "page_number": page_number,
                    "output_path": str(output_path),
                    "message": str(exc),
                })

            self.result_queue.put({"type": "progress", **session.progress_snapshot()})

        self.result_queue.put({
            "type": "finished",
            "output_dir": str(output_dir),
            **session.progress_snapshot(),
        })

    def _render_page_to_rgb(self, page: fitz.Page, matrix: fitz.Matrix) -> Image.Image:
        """ページをレンダリングし、必要なら白背景へ合成して RGB 化する。"""
        pixmap = page.get_pixmap(matrix=matrix, colorspace=fitz.csRGB, alpha=True)
        image = Image.frombytes("RGBA", (pixmap.width, pixmap.height), pixmap.samples)
        return self._flatten_rgba_to_rgb(image)

    @staticmethod
    def _flatten_rgba_to_rgb(image: Image.Image) -> Image.Image:
        """JPEG 保存用に RGBA を白背景 RGB へ変換する。"""
        if image.mode == "RGBA":
            background = Image.new("RGB", image.size, "white")
            background.paste(image, mask=image.getchannel("A"))
            return background
        return image.convert("RGB")