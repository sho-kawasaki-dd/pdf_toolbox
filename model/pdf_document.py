"""PyMuPDFのラッパー。PDF読み込み・ページ画像生成・レンダリングキャッシュ。

UIに一切依存しない。PIL Image を返し、ImageTk への変換は呼び出し側で行う。
"""

from __future__ import annotations

from collections import OrderedDict

import fitz  # PyMuPDF
from PIL import Image


class PdfDocument:
    """1つのPDFファイルを管理し、ページ画像の生成とキャッシュを行う。"""

    def __init__(self, cache_limit: int = 10) -> None:
        self._doc: fitz.Document | None = None
        self._source_path: str | None = None
        self._render_cache: OrderedDict[tuple, tuple[Image.Image, int, int]] = OrderedDict()
        self._cache_limit = cache_limit

    # ------------------------------------------------------------------
    # プロパティ
    # ------------------------------------------------------------------

    @property
    def is_open(self) -> bool:
        return self._doc is not None

    @property
    def page_count(self) -> int:
        return len(self._doc) if self._doc else 0

    @property
    def source_path(self) -> str | None:
        return self._source_path

    # ------------------------------------------------------------------
    # ドキュメント操作
    # ------------------------------------------------------------------

    def open(self, file_path: str) -> int:
        """PDFファイルを開く。ページ数を返す。"""
        self.close()
        self._doc = fitz.open(file_path)
        self._source_path = file_path
        self._render_cache.clear()
        return len(self._doc)

    def close(self) -> None:
        """ドキュメントを閉じてキャッシュをクリアする。"""
        if self._doc:
            self._doc.close()
            self._doc = None
        self._source_path = None
        self._render_cache.clear()

    def clear_cache(self) -> None:
        """レンダリングキャッシュのみをクリアする。"""
        self._render_cache.clear()

    # ------------------------------------------------------------------
    # ページ画像レンダリング
    # ------------------------------------------------------------------

    def render_page_image(
        self,
        page_idx: int,
        frame_width: int,
        frame_height: int,
        zoom: float,
    ) -> tuple[Image.Image, int, int]:
        """指定ページをPIL Imageとしてレンダリングする。

        Args:
            page_idx: 0始まりのページ番号。
            frame_width: 表示領域の幅（ピクセル）。
            frame_height: 表示領域の高さ（ピクセル）。
            zoom: ズーム倍率（1.0 = フィット）。

        Returns:
            (PIL Image, 画像幅, 画像高さ) のタプル。
        """
        if not self._doc:
            raise RuntimeError("No document is open.")

        page = self._doc.load_page(page_idx)
        page_rect = page.rect

        fit_ratio = min(frame_width / page_rect.width, frame_height / page_rect.height)
        final_scale = max(0.01, fit_ratio * zoom)

        cache_key = (page_idx, round(final_scale, 4))
        cached = self._render_cache.get(cache_key)
        if cached is not None:
            self._render_cache.move_to_end(cache_key)
            return cached

        pix = page.get_pixmap(matrix=fitz.Matrix(final_scale, final_scale))
        mode = "RGBA" if pix.alpha else "RGB"
        img = Image.frombytes(mode, (pix.width, pix.height), pix.samples)

        result = (img, img.width, img.height)
        self._render_cache[cache_key] = result
        self._render_cache.move_to_end(cache_key)

        while len(self._render_cache) > self._cache_limit:
            self._render_cache.popitem(last=False)

        return result
