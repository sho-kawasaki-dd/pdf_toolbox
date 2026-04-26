from __future__ import annotations

import argparse
import tempfile
import shutil
from collections import Counter
from pathlib import Path

import fitz  # PyMuPDF


def count_items(items) -> int:
    if items is None:
        return 0
    return sum(1 for _ in items)


def font_label(font_tuple) -> str:
    """フォント情報のタプルから識別用のラベルを生成する"""
    xref = font_tuple[0] if len(font_tuple) > 0 else 0
    # basefont名があれば優先し、なければnameを使用
    basefont = str(font_tuple[3]) if len(font_tuple) > 3 and font_tuple[3] else ""
    name = str(font_tuple[4]) if len(font_tuple) > 4 and font_tuple[4] else ""
    return basefont or name or f"xref:{xref}"


def collect_summary(doc: fitz.Document) -> dict[str, object]:
    """PDFドキュメント内のオブジェクト統計を収集する"""
    page_stats: list[dict[str, object]] = []
    font_counter: Counter[str] = Counter()
    image_counter: Counter[int] = Counter()

    total_annots = 0
    total_widgets = 0
    total_font_entries = 0
    total_image_entries = 0

    for page_number, page in enumerate(doc, start=1):
        annots = count_items(page.annots())
        widgets = count_items(page.widgets())

        # page.get_fonts() は (xref, gen, type, basefont, name, ...) を返す
        fonts = [font_label(f) for f in page.get_fonts(full=True)]
        # page.get_images() は (xref, smask, width, height, ...) を返す
        images = [int(img[0]) for img in page.get_images(full=True)]

        font_counter.update(fonts)
        image_counter.update(images)

        total_annots += annots
        total_widgets += widgets
        total_font_entries += len(fonts)
        total_image_entries += len(images)

        page_stats.append({
            "page": page_number,
            "annots": annots,
            "widgets": widgets,
            "fonts": len(fonts),
            "images": len(images),
        })

    return {
        "page_count": doc.page_count,
        "xref_count": doc.xref_length(),
        "total_annots": total_annots,
        "total_widgets": total_widgets,
        "total_font_entries": total_font_entries,
        "total_image_entries": total_image_entries,
        "unique_fonts": sorted(font_counter.keys()),
        "unique_images": sorted(image_counter.keys()),
        "page_stats": page_stats,
    }


def flatten_copy(input_path: Path, output_path: Path) -> None:
    """bakeを実行し、最適化オプションを付けて保存する"""
    doc = fitz.open(input_path)
    try:
        doc.bake()
        doc.save(output_path, garbage=3, deflate=True)
        # doc.save(output_path, garbage=4, deflate=True, clean=True)
        # garbage (int) --
        # ガベージコレクションを実行します。正の値は「増分」を除外します。
        # 0 = なし
        # 1 = 未使用（参照されていない）オブジェクトを削除します。
        # 2 = 1に加えて、xref テーブルを最適化します。
        # 3 = 2に加えて、重複したオブジェクトを統合します。
        # 4 = 3に加えて、ストリームオブジェクトの重複をチェックします。これは、そのようなデータが通常大きいため、遅い場合があります。
    finally:
        doc.close()


def print_summary(title: str, path: Path, info: dict[str, object]) -> None:
    print(f"\n[{title.upper()}]")
    print(f"  Path: {path}")
    print(f"  Size: {path.stat().st_size:,} bytes")
    print(f"  Pages: {info['page_count']}")
    print(f"  Xref Count: {info['xref_count']}")
    print(f"  Annots: {info['total_annots']} / Widgets: {info['total_widgets']}")
    print(f"  Font Entries (Total): {info['total_font_entries']}")
    print(f"  Unique Fonts: {len(info['unique_fonts'])}")
    
    if info["unique_fonts"]:
        print("  Fonts (First 10):")
        for name in list(info["unique_fonts"])[:10]:
            print(f"    - {name}")


def print_delta(before: dict[str, object], after: dict[str, object]) -> None:
    b_size = int(before["file_size"])
    a_size = int(after["file_size"])
    
    print("\n[DELTA ANALYSIS]")
    print(f"  Size Change: {a_size - b_size:+,} bytes")
    if b_size > 0:
        print(f"  Size Ratio: {a_size / b_size:.3f}x")
    
    print(f"  Xref Change: {int(after['xref_count']) - int(before['xref_count']):+}")
    print(f"  Annots Change: {int(after['total_annots']) - int(before['total_annots'])}")
    
    # フォントの差分分析
    before_fonts = set(before["unique_fonts"])
    after_fonts = set(after["unique_fonts"])
    added_fonts = sorted(after_fonts - before_fonts)
    removed_fonts = sorted(before_fonts - after_fonts)

    if added_fonts:
        print(f"  Added Fonts ({len(added_fonts)}):")
        for name in added_fonts[:15]:
            print(f"    + {name}")
    
    if removed_fonts:
        print(f"  Removed Fonts ({len(removed_fonts)}):")
        for name in removed_fonts[:15]:
            print(f"    - {name}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze PDF before/after flattening.")
    parser.add_argument("input_pdf", type=Path, help="Input PDF file path")
    parser.add_argument("--output", type=Path, help="Output path (optional)")
    parser.add_argument("--keep", action="store_true", help="Keep temp files")
    args = parser.parse_args()

    input_path = args.input_pdf
    if not input_path.exists() or input_path.suffix.lower() != ".pdf":
        print("Error: Valid input PDF required.")
        return 1

    # 出力パスの設定
    temp_dir = None
    if args.output:
        output_path = args.output
        output_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        temp_dir = Path(tempfile.mkdtemp(prefix="flatten_dbg_"))
        output_path = temp_dir / f"{input_path.stem}_flattened.pdf"

    try:
        # Before解析
        with fitz.open(input_path) as doc:
            before_info = collect_summary(doc)
            before_info["file_size"] = input_path.stat().st_size

        # 処理実行
        flatten_copy(input_path, output_path)

        # After解析
        with fitz.open(output_path) as doc:
            after_info = collect_summary(doc)
            after_info["file_size"] = output_path.stat().st_size

        # レポート出力
        print_summary("Before Flattening", input_path, before_info)
        print_summary("After Flattening", output_path, after_info)
        print_delta(before_info, after_info)

        # 保持設定の確認
        if temp_dir and not args.keep:
            print(f"\n[Cleaning up] Removing temp file: {output_path}")
            shutil.rmtree(temp_dir)
        elif temp_dir:
            print(f"\n[Success] Temp file kept at: {output_path}")

    except Exception as e:
        print(f"Error during analysis: {e}")
        if temp_dir and not args.keep:
            shutil.rmtree(temp_dir)
        return 1

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
    # usage:
    # uv run --with pymupdf python fitz_bake-save_analysis.py your_file.pdf --keep