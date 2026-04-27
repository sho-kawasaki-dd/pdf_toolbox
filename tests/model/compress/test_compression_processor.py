from __future__ import annotations

import shutil
import time
from pathlib import Path

from model.compress.compression_processor import CompressionProcessor
from model.compress.compression_session import CompressionSession
from model.compress.compression_dispatch import CompressionRequest


def _wait_for_completion(processor: CompressionProcessor, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while processor.is_compressing and time.monotonic() < deadline:
        time.sleep(0.05)


def test_folder_scan_ignores_non_pdf_and_broken_pdf(
    mixed_input_folder: Path,
    tmp_path: Path,
    monkeypatch,
) -> None:
    """フォルダ入力では再帰的に PDF だけを拾い、無効入力はスキップする。"""
    def fake_compress(source: str | Path, output: str | Path, **_kwargs):
        shutil.copy2(source, output)
        return True, "ok"

    monkeypatch.setattr("model.compress.compression_processor.compress_pdf", fake_compress)

    session = CompressionSession()
    session.add_input(str(mixed_input_folder))
    session.set_output_dir(str(tmp_path / "out"))

    processor = CompressionProcessor(max_workers=2)
    processor.start_compression(session)
    _wait_for_completion(processor)

    results = processor.poll_results()
    assert any(result["type"] == "success" for result in results)
    assert any(result["type"] == "skipped" for result in results)

    finished = [result for result in results if result["type"] == "finished"]
    assert finished[0]["success_count"] == 2
    assert finished[0]["skip_count"] == 3


def test_nested_zip_scan_respects_depth_limit(
    nested_zip: Path,
    tmp_path: Path,
    monkeypatch,
) -> None:
    def fake_compress(source: str | Path, output: str | Path, **_kwargs):
        shutil.copy2(source, output)
        return True, "ok"

    monkeypatch.setattr("model.compress.compression_processor.compress_pdf", fake_compress)

    session = CompressionSession()
    session.add_input(str(nested_zip))
    session.set_output_dir(str(tmp_path / "out"))

    processor = CompressionProcessor(max_workers=2)
    processor.start_compression(session)
    _wait_for_completion(processor)

    results = processor.poll_results()
    finished = [result for result in results if result["type"] == "finished"]
    assert finished[0]["success_count"] == 5
    assert finished[0]["skip_count"] == 1
    assert any(result.get("reason") == "zip depth limit exceeded" for result in results if result["type"] == "skipped")


def test_output_collision_gets_numbered(
    sample_pdf: Path,
    output_conflict_dir: Path,
    monkeypatch,
) -> None:
    def fake_compress(source: str | Path, output: str | Path, **_kwargs):
        shutil.copy2(source, output)
        return True, "ok"

    monkeypatch.setattr("model.compress.compression_processor.compress_pdf", fake_compress)

    session = CompressionSession()
    session.add_input(str(sample_pdf))
    session.set_output_dir(str(output_conflict_dir))

    processor = CompressionProcessor(max_workers=1)
    processor.start_compression(session)
    _wait_for_completion(processor)
    processor.poll_results()

    assert (output_conflict_dir / "sample.pdf").exists()
    assert (output_conflict_dir / "sample (1).pdf").exists()


def test_broken_zip_is_skipped(broken_zip: Path, tmp_path: Path) -> None:
    session = CompressionSession()
    session.add_input(str(broken_zip))
    session.set_output_dir(str(tmp_path / "out"))

    processor = CompressionProcessor(max_workers=1)
    processor.start_compression(session)
    _wait_for_completion(processor)

    results = processor.poll_results()
    assert any(result["type"] == "skipped" and result["reason"] == "invalid zip" for result in results)
    finished = [result for result in results if result["type"] == "finished"]
    assert finished[0]["skip_count"] == 1


def test_zip_scan_ignores_invalid_members_and_processes_valid_pdfs(
    mixed_zip: Path,
    tmp_path: Path,
    monkeypatch,
) -> None:
    """ZIP 入力では正常 PDF を処理し、壊れた PDF と非 PDF を無視する。"""
    def fake_compress(source: str | Path, output: str | Path, **_kwargs):
        shutil.copy2(source, output)
        return True, "ok"

    monkeypatch.setattr("model.compress.compression_processor.compress_pdf", fake_compress)

    session = CompressionSession()
    session.add_input(str(mixed_zip))
    session.set_output_dir(str(tmp_path / "out"))

    processor = CompressionProcessor(max_workers=2)
    processor.start_compression(session)
    _wait_for_completion(processor)

    results = processor.poll_results()
    finished = [result for result in results if result["type"] == "finished"]

    assert finished[0]["success_count"] == 2
    assert finished[0]["skip_count"] == 3
    assert any(result.get("reason") == "invalid pdf" for result in results if result["type"] == "skipped")
    assert any(result.get("reason") == "non-pdf input" for result in results if result["type"] == "skipped")


def test_progress_messages_are_emitted_for_each_completed_item(
    sample_pdf: Path,
    tmp_path: Path,
    monkeypatch,
) -> None:
    """各結果のたびに進捗イベントが流れ、Presenter が段階表示できるようにする。"""
    def fake_compress(source: str | Path, output: str | Path, **_kwargs):
        shutil.copy2(source, output)
        return True, "ok"

    monkeypatch.setattr("model.compress.compression_processor.compress_pdf", fake_compress)

    session = CompressionSession()
    session.add_inputs([str(sample_pdf), str(sample_pdf)])
    session.set_output_dir(str(tmp_path / "out"))

    processor = CompressionProcessor(max_workers=2)
    processor.start_compression(session)
    _wait_for_completion(processor)

    results = processor.poll_results()
    progress_events = [result for result in results if result["type"] == "progress"]
    finished = [result for result in results if result["type"] == "finished"]

    assert len(progress_events) == 2
    assert progress_events[-1]["processed_items"] == 2
    assert finished[0]["success_count"] == 2


def test_success_results_include_size_metrics(
    sample_pdf: Path,
    tmp_path: Path,
    monkeypatch,
) -> None:
    def fake_compress(source: str | Path, output: str | Path, **_kwargs):
        shutil.copy2(source, output)
        return True, "ok"

    monkeypatch.setattr("model.compress.compression_processor.compress_pdf", fake_compress)

    session = CompressionSession()
    session.add_input(str(sample_pdf))
    session.set_output_dir(str(tmp_path / "out"))

    processor = CompressionProcessor(max_workers=1)
    processor.start_compression(session)
    _wait_for_completion(processor)

    results = processor.poll_results()
    success = next(result for result in results if result["type"] == "success")

    assert success["input_bytes"] == sample_pdf.stat().st_size
    assert success["lossy_output_bytes"] == sample_pdf.stat().st_size
    assert success["final_output_bytes"] == sample_pdf.stat().st_size


def test_processor_passes_engine_request_for_file_inputs(
    sample_pdf: Path,
    tmp_path: Path,
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_compress(source: str | Path, output: str | Path, **kwargs: object):
        captured["source"] = Path(source)
        captured["output"] = Path(output)
        captured.update(kwargs)
        shutil.copy2(source, output)
        return True, "ok"

    monkeypatch.setattr("model.compress.compression_processor.compress_pdf", fake_compress)

    session = CompressionSession()
    session.set_engine("ghostscript")
    session.set_ghostscript_preset("printer")
    session.set_ghostscript_custom_dpi(180)
    session.set_ghostscript_postprocess_enabled(True)
    session.add_input(str(sample_pdf))
    session.set_output_dir(str(tmp_path / "out"))

    processor = CompressionProcessor(max_workers=1)
    processor.start_compression(session)
    _wait_for_completion(processor)

    request = captured["request"]
    assert isinstance(request, CompressionRequest)
    assert request.engine == "ghostscript"
    assert request.ghostscript_preset == "printer"
    assert request.ghostscript_custom_dpi == 180
    assert request.ghostscript_use_pikepdf_postprocess is True


def test_processor_passes_engine_request_for_zip_inputs(
    mixed_zip: Path,
    tmp_path: Path,
    monkeypatch,
) -> None:
    captured_requests: list[CompressionRequest] = []

    def fake_compress(source: str | Path, output: str | Path, **kwargs: object):
        request = kwargs.get("request")
        if isinstance(request, CompressionRequest):
            captured_requests.append(request)
        shutil.copy2(source, output)
        return True, "ok"

    monkeypatch.setattr("model.compress.compression_processor.compress_pdf", fake_compress)

    session = CompressionSession()
    session.set_engine("ghostscript")
    session.set_ghostscript_preset("screen")
    session.add_input(str(mixed_zip))
    session.set_output_dir(str(tmp_path / "out"))

    processor = CompressionProcessor(max_workers=1)
    processor.start_compression(session)
    _wait_for_completion(processor)

    assert captured_requests
    assert all(request.engine == "ghostscript" for request in captured_requests)
    assert all(request.ghostscript_preset == "screen" for request in captured_requests)