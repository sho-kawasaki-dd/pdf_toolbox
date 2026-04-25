"""テスト共通 fixture。

サンプル PDF の生成や一時ディレクトリなど、複数テストモジュールで共有するリソースを提供する。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast
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
    jpeg_pixels = cast(Any, jpeg_image.load())
    for x in range(1200):
        for y in range(800):
            # 単色画像では圧縮差が安定して出にくいため、擬似的な高周波パターンを作る。
            jpeg_pixels[x, y] = ((x * 17) % 255, (y * 13) % 255, ((x + y) * 7) % 255)
    jpeg_image.save(jpeg_path, format="JPEG", quality=95)

    png_image = Image.new("RGBA", (800, 800))
    png_pixels = cast(Any, png_image.load())
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
def cmyk_image_pdf(tmp_path: Path) -> Path:
    """CMYK JPEG を含むサンプル PDF を生成して返す。"""
    pdf_path = tmp_path / "cmyk-images.pdf"
    jpeg_path = tmp_path / "sample-cmyk.jpg"

    cmyk_image = Image.new("CMYK", (1200, 800))
    cmyk_pixels = cast(Any, cmyk_image.load())
    for x in range(1200):
        for y in range(800):
            cmyk_pixels[x, y] = (
                (x * 17) % 255,
                (y * 11) % 255,
                ((x + y) * 7) % 255,
                ((x * 3 + y * 5) % 180),
            )
    cmyk_image.save(jpeg_path, format="JPEG", quality=95)

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_image(fitz.Rect(72, 72, 523, 372), filename=str(jpeg_path))
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
def annotated_pdf(tmp_path: Path) -> Path:
    """注釈を含む 1 ページ PDF を生成して返す。"""
    pdf_path = tmp_path / "annotated.pdf"
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text(fitz.Point(72, 72), "Annotated Page", fontsize=24)
    annotation = page.add_highlight_annot(fitz.Rect(72, 56, 240, 86))
    annotation.update()
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


def _build_form_pdf(pdf_path: Path) -> Path:
    """テキストフィールドとチェックボックスを持つ PDF を生成する。"""
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text(fitz.Point(72, 48), "Form Fixture", fontsize=20)

    text_widget = fitz.Widget()
    text_widget.field_name = "user_name"
    text_widget.field_label = "User Name"
    text_widget.field_type = fitz.PDF_WIDGET_TYPE_TEXT
    text_widget.field_value = "Alice Example"
    text_widget.rect = fitz.Rect(72, 72, 280, 100)
    page.add_widget(text_widget)

    checkbox_widget = fitz.Widget()
    checkbox_widget.field_name = "agree_terms"
    checkbox_widget.field_label = "Agree Terms"
    checkbox_widget.field_type = fitz.PDF_WIDGET_TYPE_CHECKBOX
    checkbox_widget.field_value = True
    checkbox_widget.rect = fitz.Rect(72, 128, 92, 148)
    page.add_widget(checkbox_widget)

    page.insert_text(fitz.Point(100, 144), "I agree", fontsize=14)
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


@pytest.fixture()
def form_widget_pdf(tmp_path: Path) -> Path:
    """テキストフィールドとチェックボックスを持つ PDF を返す。"""
    return _build_form_pdf(tmp_path / "form-widget.pdf")


@pytest.fixture()
def broken_appearance_pdf(tmp_path: Path) -> Path:
    """壊れた Appearance 参照を持つ form PDF を返す。"""
    source_path = _build_form_pdf(tmp_path / "broken-appearance-source.pdf")
    broken_path = tmp_path / "broken-appearance.pdf"
    raw = source_path.read_bytes()
    broken_raw = raw.replace(b"/AP<</N 7 0 R>>>>", b"/AP<</N 999 0 R>>>>", 1)
    if broken_raw == raw:
        broken_raw = raw.replace(b"/AP << /N 7 0 R >>", b"/AP << /N 999 0 R >>", 1)
    broken_path.write_bytes(broken_raw)
    return broken_path


@pytest.fixture()
def encrypted_pdf(tmp_path: Path) -> Path:
    """パスワード付きの暗号化 PDF を生成して返す。"""
    pdf_path = tmp_path / "encrypted.pdf"
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text(fitz.Point(72, 72), "Encrypted Page", fontsize=24)
    doc.save(
        str(pdf_path),
        user_pw="user-pass",
        owner_pw="owner-pass",
        encryption=fitz.PDF_ENCRYPT_AES_256,
    )
    doc.close()
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
