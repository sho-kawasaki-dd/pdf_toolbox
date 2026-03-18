from __future__ import annotations

import time
from pathlib import Path

import pikepdf

from model.extract.extract_processor import ExtractPageSpec, ExtractProcessor


def _wait_for_completion(processor: ExtractProcessor, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while processor.is_running and time.monotonic() < deadline:
        time.sleep(0.05)


def test_extract_single_page(sample_pdf: Path, tmp_path: Path) -> None:
    output = tmp_path / "extracted.pdf"
    processor = ExtractProcessor()

    pages = [ExtractPageSpec(source_path=str(sample_pdf), page_index=0)]
    processor.start_extract(pages, str(output))
    _wait_for_completion(processor)
    results = processor.poll_results()

    finished = [r for r in results if r["type"] == "finished"]
    assert len(finished) == 1
    assert finished[0]["output_path"] == str(output)
    assert output.exists()

    with pikepdf.open(str(output)) as pdf:
        assert len(pdf.pages) == 1


def test_extract_multiple_pages_preserves_order(sample_pdf: Path, tmp_path: Path) -> None:
    output = tmp_path / "extracted.pdf"
    processor = ExtractProcessor()

    # Extract pages in reverse: page 9, 4, 0
    pages = [
        ExtractPageSpec(source_path=str(sample_pdf), page_index=9),
        ExtractPageSpec(source_path=str(sample_pdf), page_index=4),
        ExtractPageSpec(source_path=str(sample_pdf), page_index=0),
    ]
    processor.start_extract(pages, str(output))
    _wait_for_completion(processor)
    results = processor.poll_results()

    finished = [r for r in results if r["type"] == "finished"]
    assert len(finished) == 1
    assert output.exists()

    with pikepdf.open(str(output)) as pdf:
        assert len(pdf.pages) == 3


def test_extract_from_multiple_sources(sample_pdf: Path, single_page_pdf: Path, tmp_path: Path) -> None:
    output = tmp_path / "extracted.pdf"
    processor = ExtractProcessor()

    pages = [
        ExtractPageSpec(source_path=str(sample_pdf), page_index=0),
        ExtractPageSpec(source_path=str(single_page_pdf), page_index=0),
        ExtractPageSpec(source_path=str(sample_pdf), page_index=5),
    ]
    processor.start_extract(pages, str(output))
    _wait_for_completion(processor)
    results = processor.poll_results()

    finished = [r for r in results if r["type"] == "finished"]
    assert len(finished) == 1

    with pikepdf.open(str(output)) as pdf:
        assert len(pdf.pages) == 3


def test_extract_duplicate_page(sample_pdf: Path, tmp_path: Path) -> None:
    output = tmp_path / "extracted.pdf"
    processor = ExtractProcessor()

    pages = [
        ExtractPageSpec(source_path=str(sample_pdf), page_index=0),
        ExtractPageSpec(source_path=str(sample_pdf), page_index=0),
    ]
    processor.start_extract(pages, str(output))
    _wait_for_completion(processor)
    results = processor.poll_results()

    finished = [r for r in results if r["type"] == "finished"]
    assert len(finished) == 1

    with pikepdf.open(str(output)) as pdf:
        assert len(pdf.pages) == 2


def test_extract_reports_progress(sample_pdf: Path, tmp_path: Path) -> None:
    output = tmp_path / "extracted.pdf"
    processor = ExtractProcessor()

    pages = [ExtractPageSpec(source_path=str(sample_pdf), page_index=i) for i in range(3)]
    processor.start_extract(pages, str(output))
    _wait_for_completion(processor)
    results = processor.poll_results()

    progress = [r for r in results if r["type"] == "progress"]
    assert len(progress) == 3
    assert progress[0]["processed"] == 1
    assert progress[2]["processed"] == 3
    assert all(r["total"] == 3 for r in progress)


def test_extract_empty_pages_fails(tmp_path: Path) -> None:
    output = tmp_path / "extracted.pdf"
    processor = ExtractProcessor()

    processor.start_extract([], str(output))
    _wait_for_completion(processor)
    results = processor.poll_results()

    failure = [r for r in results if r["type"] == "failure"]
    assert len(failure) == 1
    assert "ページがありません" in failure[0]["message"]
    assert not output.exists()


def test_extract_missing_source(tmp_path: Path) -> None:
    output = tmp_path / "extracted.pdf"
    processor = ExtractProcessor()

    pages = [ExtractPageSpec(source_path=str(tmp_path / "missing.pdf"), page_index=0)]
    processor.start_extract(pages, str(output))
    _wait_for_completion(processor)
    results = processor.poll_results()

    failure = [r for r in results if r["type"] == "failure"]
    assert len(failure) == 1
    assert "見つかりません" in failure[0]["message"]
    assert not output.exists()


def test_extract_broken_pdf(broken_pdf: Path, tmp_path: Path) -> None:
    output = tmp_path / "extracted.pdf"
    processor = ExtractProcessor()

    pages = [ExtractPageSpec(source_path=str(broken_pdf), page_index=0)]
    processor.start_extract(pages, str(output))
    _wait_for_completion(processor)
    results = processor.poll_results()

    failure = [r for r in results if r["type"] == "failure"]
    assert len(failure) == 1
    assert "不正なPDF" in failure[0]["message"]
    assert not output.exists()


def test_extract_out_of_range_page(sample_pdf: Path, tmp_path: Path) -> None:
    output = tmp_path / "extracted.pdf"
    processor = ExtractProcessor()

    pages = [ExtractPageSpec(source_path=str(sample_pdf), page_index=999)]
    processor.start_extract(pages, str(output))
    _wait_for_completion(processor)
    results = processor.poll_results()

    failure = [r for r in results if r["type"] == "failure"]
    assert len(failure) == 1
    assert "範囲外" in failure[0]["message"]
    assert not output.exists()


def test_cancelled_extract_leaves_no_output(sample_pdf: Path, tmp_path: Path, monkeypatch) -> None:
    output = tmp_path / "extracted.pdf"
    processor = ExtractProcessor()
    original_append = processor._append_page
    call_count = {"value": 0}

    def cancelling_append(dest, src, spec):
        original_append(dest, src, spec)
        call_count["value"] += 1
        if call_count["value"] == 1:
            processor.request_cancel()

    monkeypatch.setattr(processor, "_append_page", cancelling_append)

    pages = [ExtractPageSpec(source_path=str(sample_pdf), page_index=i) for i in range(5)]
    processor.start_extract(pages, str(output))
    _wait_for_completion(processor)
    results = processor.poll_results()

    cancelled = [r for r in results if r["type"] == "cancelled"]
    assert len(cancelled) == 1
    assert not output.exists()


def test_start_extract_ignores_reentry(sample_pdf: Path, tmp_path: Path, monkeypatch) -> None:
    output = tmp_path / "extracted.pdf"
    processor = ExtractProcessor()
    started = []

    def blocking_worker(*_args):
        started.append(True)
        time.sleep(0.3)
        processor.is_running = False

    monkeypatch.setattr(processor, "_extract_worker", blocking_worker)

    processor.start_extract(
        [ExtractPageSpec(source_path=str(sample_pdf), page_index=0)],
        str(output),
    )
    time.sleep(0.05)
    processor.start_extract(
        [ExtractPageSpec(source_path=str(sample_pdf), page_index=0)],
        str(output),
    )
    _wait_for_completion(processor)

    assert started == [True]
