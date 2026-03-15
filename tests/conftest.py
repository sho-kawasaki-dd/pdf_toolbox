"""テスト共通 fixture。

サンプル PDF の生成や一時ディレクトリなど、複数テストモジュールで共有するリソースを提供する。
"""

from __future__ import annotations

from pathlib import Path
import zipfile

import fitz  # PyMuPDF
import pytest
from PIL import Image


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


@pytest.fixture()
def image_pdf(tmp_path: Path) -> Path:
    """JPEG と PNG を含むサンプル PDF を生成して返す。

    圧縮テストでは JPEG と PNG の両方を確実に通したいため、単純なテキスト PDF
    ではなくラスタ画像を埋め込んだ PDF を fixture として用意する。
    """
    pdf_path = tmp_path / "images.pdf"
    jpeg_path = tmp_path / "sample.jpg"
    png_path = tmp_path / "sample.png"

    jpeg_image = Image.new("RGB", (1200, 800))
    jpeg_pixels = jpeg_image.load()
    for x in range(1200):
        for y in range(800):
            # 単色画像では圧縮差が安定して出にくいため、擬似的な高周波パターンを作る。
            jpeg_pixels[x, y] = ((x * 17) % 255, (y * 13) % 255, ((x + y) * 7) % 255)
    jpeg_image.save(jpeg_path, format="JPEG", quality=95)

    png_image = Image.new("RGBA", (800, 800))
    png_pixels = png_image.load()
    for x in range(800):
        for y in range(800):
            # PNG 側は透明度も含めることで、JPEG と異なる分岐を確実に通す。
            alpha = 255 if (x + y) % 3 else 180
            png_pixels[x, y] = ((x * 11) % 255, (y * 19) % 255, ((x * y) * 3) % 255, alpha)
    png_image.save(png_path, format="PNG")

    doc = fitz.open()
    page1 = doc.new_page(width=595, height=842)
    page1.insert_image(fitz.Rect(72, 72, 523, 372), filename=str(jpeg_path))
    page2 = doc.new_page(width=595, height=842)
    page2.insert_image(fitz.Rect(72, 72, 523, 523), filename=str(png_path))
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


@pytest.fixture()
def broken_pdf(tmp_path: Path) -> Path:
    """壊れた PDF を模したバイト列を返す。"""
    pdf_path = tmp_path / "broken.pdf"
    pdf_path.write_bytes(b"not a valid pdf")
    return pdf_path


@pytest.fixture()
def mixed_input_folder(sample_pdf: Path, broken_pdf: Path, tmp_path: Path) -> Path:
    """正常 PDF・壊れた PDF・非 PDF を混在させたフォルダを返す。"""
    folder = tmp_path / "mixed-input"
    folder.mkdir()
    (folder / sample_pdf.name).write_bytes(sample_pdf.read_bytes())
    (folder / broken_pdf.name).write_bytes(broken_pdf.read_bytes())
    (folder / "notes.txt").write_text("not a pdf", encoding="utf-8")

    nested_dir = folder / "nested"
    nested_dir.mkdir()
    (nested_dir / "nested-sample.pdf").write_bytes(sample_pdf.read_bytes())
    (nested_dir / "readme.md").write_text("still not a pdf", encoding="utf-8")
    return folder


def _create_nested_zip_bytes(level: int, max_level: int, pdf_bytes: bytes) -> bytes:
    """再帰 ZIP テスト用のネスト ZIP をメモリ上で生成する。

    一時ファイルを何段も作らずに深さ制限だけをテストしたいため、ZIP はすべて
    メモリ上で組み立てて最後にファイルへ書き出す。
    """
    import io

    temp_buffer = io.BytesIO()
    with zipfile.ZipFile(temp_buffer, mode="w") as archive:
        archive.writestr(f"level{level}.pdf", pdf_bytes)
        if level < max_level:
            archive.writestr(
                f"nested{level + 1}.zip",
                _create_nested_zip_bytes(level + 1, max_level, pdf_bytes),
            )
    return temp_buffer.getvalue()


@pytest.fixture()
def nested_zip(sample_pdf: Path, tmp_path: Path) -> Path:
    """深さ制限検証用に 6 階層ぶんのネスト ZIP を返す。"""
    zip_path = tmp_path / "nested.zip"
    zip_path.write_bytes(_create_nested_zip_bytes(1, 6, sample_pdf.read_bytes()))
    return zip_path


@pytest.fixture()
def broken_zip(tmp_path: Path) -> Path:
    """壊れた ZIP を模したバイト列を返す。"""
    zip_path = tmp_path / "broken.zip"
    zip_path.write_bytes(b"not a valid zip")
    return zip_path


@pytest.fixture()
def mixed_zip(sample_pdf: Path, broken_pdf: Path, tmp_path: Path) -> Path:
    """正常 PDF・壊れた PDF・非 PDF・ネスト ZIP を含む ZIP を返す。"""
    import io

    zip_path = tmp_path / "mixed.zip"
    nested_buffer = io.BytesIO()
    with zipfile.ZipFile(nested_buffer, mode="w") as nested_archive:
        nested_archive.writestr("nested/inside.pdf", sample_pdf.read_bytes())
        nested_archive.writestr("nested/notes.txt", "ignore me")

    with zipfile.ZipFile(zip_path, mode="w") as archive:
        archive.writestr("root.pdf", sample_pdf.read_bytes())
        archive.writestr("broken.pdf", broken_pdf.read_bytes())
        archive.writestr("notes.txt", "ignore me")
        archive.writestr("nested.zip", nested_buffer.getvalue())

    return zip_path


@pytest.fixture()
def output_conflict_dir(tmp_path: Path) -> Path:
    """出力ファイル名衝突テスト用の既存ファイル入り出力フォルダを返す。"""
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    (output_dir / "sample.pdf").write_bytes(b"occupied")
    return output_dir
