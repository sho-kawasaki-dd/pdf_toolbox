"""PdfDocument の回帰テスト。

PDF 読み込み・ページ画像生成・LRU キャッシュの挙動を検証する。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from model.pdf_document import PdfDocument


class TestOpenAndClose:

    def test_open_returns_page_count(self, sample_pdf: Path):
        doc = PdfDocument()
        count = doc.open(str(sample_pdf))
        assert count == 10
        doc.close()

    def test_is_open(self, sample_pdf: Path):
        doc = PdfDocument()
        assert doc.is_open is False
        doc.open(str(sample_pdf))
        assert doc.is_open is True
        doc.close()
        assert doc.is_open is False

    def test_page_count(self, sample_pdf: Path):
        doc = PdfDocument()
        assert doc.page_count == 0
        doc.open(str(sample_pdf))
        assert doc.page_count == 10
        doc.close()

    def test_source_path(self, sample_pdf: Path):
        doc = PdfDocument()
        assert doc.source_path is None
        doc.open(str(sample_pdf))
        assert doc.source_path == str(sample_pdf)
        doc.close()
        assert doc.source_path is None

    def test_close_resets_state(self, sample_pdf: Path):
        doc = PdfDocument()
        doc.open(str(sample_pdf))
        doc.close()
        assert doc.is_open is False
        assert doc.page_count == 0
        assert doc.source_path is None

    def test_open_replaces_previous(self, sample_pdf: Path, single_page_pdf: Path):
        doc = PdfDocument()
        doc.open(str(sample_pdf))
        assert doc.page_count == 10
        doc.open(str(single_page_pdf))
        assert doc.page_count == 1
        doc.close()


class TestRenderPageImage:

    def test_returns_pil_image(self, sample_pdf: Path):
        doc = PdfDocument()
        doc.open(str(sample_pdf))
        img, w, h = doc.render_page_image(0, 500, 600, 1.0)
        assert isinstance(img, Image.Image)
        assert w > 0
        assert h > 0
        doc.close()

    def test_render_different_pages(self, sample_pdf: Path):
        doc = PdfDocument()
        doc.open(str(sample_pdf))
        img0, _, _ = doc.render_page_image(0, 500, 600, 1.0)
        img9, _, _ = doc.render_page_image(9, 500, 600, 1.0)
        assert isinstance(img0, Image.Image)
        assert isinstance(img9, Image.Image)
        doc.close()

    def test_zoom_affects_size(self, sample_pdf: Path):
        doc = PdfDocument()
        doc.open(str(sample_pdf))
        _, w1, h1 = doc.render_page_image(0, 500, 600, 1.0)
        _, w2, h2 = doc.render_page_image(0, 500, 600, 2.0)
        assert w2 > w1
        assert h2 > h1
        doc.close()

    def test_render_uses_oversampled_source(self, sample_pdf: Path):
        doc = PdfDocument()
        doc.open(str(sample_pdf))
        img, w, h = doc.render_page_image(0, 500, 600, 1.0)
        assert img.width >= w
        assert img.height >= h
        doc.close()

    def test_render_without_open_raises(self):
        doc = PdfDocument()
        with pytest.raises(RuntimeError):
            doc.render_page_image(0, 500, 600, 1.0)


class TestCache:

    def test_cache_hit(self, sample_pdf: Path):
        doc = PdfDocument(cache_limit=10)
        doc.open(str(sample_pdf))
        img1, _, _ = doc.render_page_image(0, 500, 600, 1.0)
        img2, _, _ = doc.render_page_image(0, 500, 600, 1.0)
        # キャッシュヒット時は同じオブジェクトが返される
        assert img1 is img2
        doc.close()

    def test_lru_eviction(self, sample_pdf: Path):
        """cache_limit=10 で 11 種類のキーをレンダリングすると最初のキャッシュが消える。"""
        doc = PdfDocument(cache_limit=10)
        doc.open(str(sample_pdf))

        # 異なるズーム値で 11 回レンダリング（キーが異なる）
        for i in range(11):
            zoom = 1.0 + i * 0.01
            doc.render_page_image(0, 500, 600, zoom)

        assert len(doc._render_cache) == 10
        # 最初のキー (zoom=1.0) がキャッシュから追い出されている
        first_key = (0, round(1.0 * min(500 / 595, 600 / 842), 4))
        # キャッシュキーは (page_idx, round(final_scale, 4)) なので直接確認
        first_zoom_key = (0, round(min(500 / 595, 600 / 842) * 1.0, 4))
        assert first_zoom_key not in doc._render_cache
        doc.close()

    def test_clear_cache(self, sample_pdf: Path):
        doc = PdfDocument(cache_limit=10)
        doc.open(str(sample_pdf))
        doc.render_page_image(0, 500, 600, 1.0)
        assert len(doc._render_cache) > 0
        doc.clear_cache()
        assert len(doc._render_cache) == 0
        doc.close()
