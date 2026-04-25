import fitz
import random
from pathlib import Path


def make_random_rect(width, height, margin=50, min_size=20):
    x0 = random.uniform(margin, width - margin)
    x1 = random.uniform(margin, width - margin)
    y0 = random.uniform(margin, height - margin)
    y1 = random.uniform(margin, height - margin)

    left, right = sorted((x0, x1))
    top, bottom = sorted((y0, y1))

    if right - left < min_size:
        right = min(width - margin, left + min_size)
    if bottom - top < min_size:
        bottom = min(height - margin, top + min_size)

    return fitz.Rect(left, top, right, bottom)

def create_debug_pdfs(output_dir="test_data", num_files=50, pages_per_file=10):
    # Pathオブジェクトの生成
    output_path = Path(output_dir)
    
    # ディレクトリ作成 (exist_ok=True で存在チェックと作成を一行で)
    output_path.mkdir(parents=True, exist_ok=True)

    print(f"Generating {num_files} PDFs in '{output_path.absolute()}'...")

    for f_idx in range(num_files):
        doc = fitz.open()
        file_name = f"debug_test_{f_idx+1:03d}.pdf"
        
        for p_idx in range(pages_per_file):
            page = doc.new_page()
            width, height = page.rect.width, page.rect.height
            
            # 1. アノテーションの追加
            for i in range(10):
                rect = make_random_rect(width, height)
                if i % 2 == 0:
                    annot = page.add_rect_annot(rect)
                    annot.set_colors(stroke=(random.random(), 0, 0), fill=(0, random.random(), 0))
                    annot.update()
                else:
                    annot = page.add_freetext_annot(rect, f"Annot {i} Page {p_idx}")
                    annot.update(text_color=(0, 0, random.random()))

            # 2. ウィジェット（フォーム）の追加
            for i in range(10):
                rect = make_random_rect(width, height)
                widget = fitz.Widget()
                widget.rect = rect
                widget.field_name = f"field_{p_idx}_{i}"
                widget.field_value = f"Value {i}"
                widget.field_type = fitz.PDF_WIDGET_TYPE_TEXT if i % 2 == 0 else fitz.PDF_WIDGET_TYPE_CHECKBOX
                page.add_widget(widget)

        # パスの結合は / 演算子を使用
        save_path = output_path / file_name
        
        # PyMuPDFのsaveはPathオブジェクトをそのまま受け取れます
        doc.save(save_path)
        doc.close()
        
        if (f_idx + 1) % 10 == 0:
            print(f"Created {f_idx + 1}/{num_files} files...")

    print("Generation complete.")

if __name__ == "__main__":
    create_debug_pdfs()