from __future__ import annotations

import time
from pathlib import Path

import fitz
from PIL import Image

from model.pdf_to_jpeg.pdf_to_jpeg_processor import PdfToJpegProcessor
from model.pdf_to_jpeg.pdf_to_jpeg_session import PdfToJpegSession


def _wait_for_completion(processor: PdfToJpegProcessor, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while processor.is_converting and time.monotonic() < deadline:
        time.sleep(0.05)


def _create_transparent_pdf(tmp_path: Path) -> Path:
    image_path = tmp_path / "transparent.png"
    pdf_path = tmp_path / "transparent.pdf"

    image = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
    for x in range(30, 70):
        for y in range(30, 70):
            image.putpixel((x, y), (220, 0, 0, 255))
    image.save(image_path, format="PNG")

    document = fitz.open()
    page = document.new_page(width=100, height=100)
    page.insert_image(fitz.Rect(0, 0, 100, 100), filename=str(image_path))
    document.save(str(pdf_path))
    document.close()
    return pdf_path


def test_export_creates_jpeg_files_and_queue_events(sample_pdf: Path, tmp_path: Path) -> None:
    session = PdfToJpegSession()
    session.set_input_pdf(str(sample_pdf))
    session.set_output_dir(str(tmp_path / "output"))
    session.set_jpeg_quality(88)

    processor = PdfToJpegProcessor()
    processor.start_conversion(session)
    _wait_for_completion(processor)

    results = processor.poll_results()
    success_events = [result for result in results if result["type"] == "success"]
    progress_events = [result for result in results if result["type"] == "progress"]
    finished_events = [result for result in results if result["type"] == "finished"]

    output_dir = tmp_path / "output" / "sample"
    assert output_dir.exists()
    assert len(list(output_dir.glob("*.jpg"))) == 10
    assert (output_dir / "sample_001.jpg").exists()
    assert (output_dir / "sample_010.jpg").exists()
    assert len(success_events) == 10
    assert len(progress_events) == 10
    assert finished_events[0]["success_count"] == 10
    assert finished_events[0]["failure_count"] == 0
    assert finished_events[0]["processed_pages"] == 10


def test_transparent_page_is_flattened_to_white_background(tmp_path: Path) -> None:
    transparent_pdf = _create_transparent_pdf(tmp_path)
    session = PdfToJpegSession()
    session.set_input_pdf(str(transparent_pdf))
    session.set_output_dir(str(tmp_path / "output"))

    processor = PdfToJpegProcessor(render_dpi=72)
    processor.start_conversion(session)
    _wait_for_completion(processor)
    processor.poll_results()

    output_path = tmp_path / "output" / "transparent" / "transparent_001.jpg"
    assert output_path.exists()

    with Image.open(output_path) as exported:
        assert exported.mode == "RGB"
        corner = exported.getpixel((5, 5))
        assert all(channel >= 240 for channel in corner)


def test_processor_reports_conflict_without_overwrite(sample_pdf: Path, tmp_path: Path) -> None:
    session = PdfToJpegSession()
    session.set_input_pdf(str(sample_pdf))
    session.set_output_dir(str(tmp_path / "output"))

    output_dir = tmp_path / "output" / "sample"
    output_dir.mkdir(parents=True)
    (output_dir / "sample_001.jpg").write_bytes(b"occupied")

    processor = PdfToJpegProcessor()
    processor.start_conversion(session)
    _wait_for_completion(processor)

    results = processor.poll_results()
    failures = [result for result in results if result["type"] == "failure"]
    assert failures
    assert "同名のJPEG" in failures[0]["message"]


def test_processor_can_overwrite_after_conflict_approval(sample_pdf: Path, tmp_path: Path) -> None:
    session = PdfToJpegSession()
    session.set_input_pdf(str(sample_pdf))
    session.set_output_dir(str(tmp_path / "output"))

    output_dir = tmp_path / "output" / "sample"
    output_dir.mkdir(parents=True)
    existing = output_dir / "sample_001.jpg"
    existing.write_bytes(b"occupied")

    processor = PdfToJpegProcessor()
    processor.start_conversion(session, overwrite=True)
    _wait_for_completion(processor)
    results = processor.poll_results()

    finished_events = [result for result in results if result["type"] == "finished"]
    assert finished_events[0]["success_count"] == 10
    assert existing.stat().st_size > len(b"occupied")