"""テスト共通 fixture。

サンプル PDF の生成や一時ディレクトリなど、複数テストモジュールで共有するリソースを提供する。
"""

from __future__ import annotations

from pathlib import Path

import fitz  # PyMuPDF
import pytest


@pytest.fixture()
def sample_pdf(tmp_path: Path) -> Path:
    """10 ページのサンプル PDF を生成して返す。"""
    pdf_path = tmp_path / "sample.pdf"
    doc = fitz.open()
    for i in range(10):
        page = doc.new_page(width=595, height=842)  # A4 サイズ
        text_point = fitz.Point(72, 72)
        page.insert_text(text_point, f"Page {i + 1}", fontsize=36)
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


@pytest.fixture()
def single_page_pdf(tmp_path: Path) -> Path:
    """1 ページのサンプル PDF を生成して返す。"""
    pdf_path = tmp_path / "single.pdf"
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text(fitz.Point(72, 72), "Single Page", fontsize=36)
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path
