from __future__ import annotations

import time
from pathlib import Path

import fitz

from model.merge.merge_processor import MergeProcessor


def _wait_for_completion(processor: MergeProcessor, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while processor.is_merging and time.monotonic() < deadline:
        time.sleep(0.05)


def test_merge_success_creates_output_in_input_order(sample_pdf: Path, single_page_pdf: Path, tmp_path: Path) -> None:
    output_path = tmp_path / "merged.pdf"
    processor = MergeProcessor()

    processor.start_merge([str(sample_pdf), str(single_page_pdf)], str(output_path))
    _wait_for_completion(processor)
    results = processor.poll_results()

    finished = [result for result in results if result["type"] == "finished"]
    assert finished[0]["output_path"] == str(output_path)
    assert output_path.exists()

    with fitz.open(str(output_path)) as merged:
        assert merged.page_count == 11
        assert "Page 1" in merged.load_page(0).get_text()
        assert "Single Page" in merged.load_page(10).get_text()


def test_merge_reports_missing_input(tmp_path: Path) -> None:
    output_path = tmp_path / "merged.pdf"
    missing_path = tmp_path / "missing.pdf"
    processor = MergeProcessor()

    processor.start_merge([str(missing_path)], str(output_path))
    _wait_for_completion(processor)
    results = processor.poll_results()

    failure = [result for result in results if result["type"] == "failure"]
    assert "見つかりません" in failure[0]["message"]
    assert output_path.exists() is False


def test_merge_reports_invalid_pdf(broken_pdf: Path, tmp_path: Path) -> None:
    output_path = tmp_path / "merged.pdf"
    processor = MergeProcessor()

    processor.start_merge([str(broken_pdf)], str(output_path))
    _wait_for_completion(processor)
    results = processor.poll_results()

    failure = [result for result in results if result["type"] == "failure"]
    assert "不正なPDF" in failure[0]["message"]
    assert output_path.exists() is False


def test_cancelled_merge_leaves_no_partial_output(sample_pdf: Path, tmp_path: Path, monkeypatch) -> None:
    output_path = tmp_path / "merged.pdf"
    processor = MergeProcessor()
    original_append = processor._append_input_pdf
    call_count = {"value": 0}

    def cancelling_append(merged_doc, input_path) -> None:
        original_append(merged_doc, input_path)
        call_count["value"] += 1
        if call_count["value"] == 1:
            processor.request_cancel()

    monkeypatch.setattr(processor, "_append_input_pdf", cancelling_append)

    processor.start_merge([str(sample_pdf), str(sample_pdf)], str(output_path))
    _wait_for_completion(processor)
    results = processor.poll_results()

    cancelled = [result for result in results if result["type"] == "cancelled"]
    progress = [result for result in results if result["type"] == "progress"]
    assert cancelled
    assert progress[0]["processed_items"] == 1
    assert output_path.exists() is False


def test_start_merge_ignores_reentry_while_running(sample_pdf: Path, tmp_path: Path, monkeypatch) -> None:
    output_path = tmp_path / "merged.pdf"
    processor = MergeProcessor()
    started = []

    def blocking_worker(*_args) -> None:
        started.append(True)
        time.sleep(0.3)
        processor.is_merging = False

    monkeypatch.setattr(processor, "_merge_worker", blocking_worker)

    processor.start_merge([str(sample_pdf)], str(output_path))
    time.sleep(0.05)
    processor.start_merge([str(sample_pdf)], str(output_path))
    _wait_for_completion(processor)

    assert started == [True]