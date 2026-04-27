from __future__ import annotations

import shutil
import threading
import time
from pathlib import Path

import fitz

from model.compress.settings import PDF_GHOSTSCRIPT_PRESET_SCREEN
from model.flatten.flatten_processor import FlattenProcessor
from model.flatten.flatten_session import FlattenBatchPlan, FlattenJob, FlattenSession


def _wait_for_completion(processor: FlattenProcessor, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while processor.is_running and time.monotonic() < deadline:
        time.sleep(0.05)


def test_prepare_batch_recurses_folder_and_marks_skipped_inputs(
    mixed_input_folder: Path,
    tmp_path: Path,
) -> None:
    session = FlattenSession()
    session.add_inputs([
        str(mixed_input_folder),
        str(tmp_path / "missing.pdf"),
    ])

    processor = FlattenProcessor()
    plan = processor.prepare_batch(session)

    assert len(plan.jobs) == 3
    assert [issue["reason"] for issue in plan.preflight_issues if issue["type"] == "skipped"] == [
        "non-pdf input",
        "non-pdf input",
        "missing input",
    ]


def test_prepare_batch_separates_existing_conflicts(sample_pdf: Path) -> None:
    session = FlattenSession()
    session.add_input(str(sample_pdf))

    expected_output = Path(session.build_output_path(str(sample_pdf)))
    expected_output.write_bytes(b"occupied")

    processor = FlattenProcessor()
    plan = processor.prepare_batch(session)

    assert plan.jobs == []
    assert len(plan.conflicts) == 1
    assert plan.conflicts[0].output_path == str(expected_output)


def test_prepare_batch_reports_output_path_too_long(sample_pdf: Path, monkeypatch) -> None:
    session = FlattenSession()
    session.add_input(str(sample_pdf))
    processor = FlattenProcessor()

    monkeypatch.setattr(
        session,
        "build_output_path",
        lambda _source_path: f"C:\\{'a' * 257}",
    )

    plan = processor.prepare_batch(session)

    assert plan.jobs == []
    assert len(plan.preflight_issues) == 1
    assert "出力パスが長すぎる" in str(plan.preflight_issues[0]["message"])


def test_prepare_batch_reports_temp_path_too_long(sample_pdf: Path, monkeypatch) -> None:
    session = FlattenSession()
    session.add_input(str(sample_pdf))
    processor = FlattenProcessor()
    output_path = f"C:\\{'a' * 240}.pdf"

    monkeypatch.setattr(session, "build_output_path", lambda _source_path: output_path)

    plan = processor.prepare_batch(session)

    assert plan.jobs == []
    assert len(plan.preflight_issues) == 1
    assert "一時出力パスが長すぎる" in str(plan.preflight_issues[0]["message"])


def test_start_flatten_creates_output_and_queue_events(annotated_pdf: Path) -> None:
    session = FlattenSession()
    session.add_input(str(annotated_pdf))

    processor = FlattenProcessor()
    plan = processor.prepare_batch(session)
    processor.start_flatten(session, plan)
    _wait_for_completion(processor)

    results = processor.poll_results()
    successes = [result for result in results if result["type"] == "success"]
    progress_events = [result for result in results if result["type"] == "progress"]
    finished = [result for result in results if result["type"] == "finished"]

    output_path = Path(plan.jobs[0].output_path)
    assert output_path.exists()
    assert len(successes) == 1
    assert len(progress_events) == 1
    assert finished[0]["success_count"] == 1

    with fitz.open(str(output_path)) as flattened:
        assert flattened.page_count == 1


def test_start_flatten_flattens_form_widgets(form_widget_pdf: Path) -> None:
    session = FlattenSession()
    session.add_input(str(form_widget_pdf))

    processor = FlattenProcessor()
    plan = processor.prepare_batch(session)

    with fitz.open(str(form_widget_pdf)) as source_doc:
        source_widgets = list(source_doc[0].widgets())
        assert len(source_widgets) == 2

    processor.start_flatten(session, plan)
    _wait_for_completion(processor)
    results = processor.poll_results()

    successes = [result for result in results if result["type"] == "success"]
    finished = [result for result in results if result["type"] == "finished"]

    assert len(successes) == 1
    assert finished[0]["success_count"] == 1

    output_path = Path(plan.jobs[0].output_path)
    with fitz.open(str(output_path)) as flattened:
        assert list(flattened[0].widgets()) == []
        assert flattened[0].first_annot is None


def test_start_flatten_finishes_with_broken_appearance_pdf(broken_appearance_pdf: Path) -> None:
    session = FlattenSession()
    session.add_input(str(broken_appearance_pdf))

    processor = FlattenProcessor()
    plan = processor.prepare_batch(session)
    processor.start_flatten(session, plan)
    _wait_for_completion(processor)
    results = processor.poll_results()

    failures = [result for result in results if result["type"] == "failure"]
    finished = [result for result in results if result["type"] == "finished"]

    assert failures == []
    assert len(finished) == 1
    assert finished[0]["success_count"] == 1

    output_path = Path(plan.jobs[0].output_path)
    with fitz.open(str(output_path)) as flattened:
        assert list(flattened[0].widgets()) == []


def test_start_flatten_reports_broken_pdf_failure(broken_pdf: Path) -> None:
    session = FlattenSession()
    session.add_input(str(broken_pdf))

    processor = FlattenProcessor()
    plan = processor.prepare_batch(session)
    processor.start_flatten(session, plan)
    _wait_for_completion(processor)

    results = processor.poll_results()
    failures = [result for result in results if result["type"] == "failure"]

    assert len(failures) == 1
    assert "不正なPDF" in str(failures[0]["message"])


def test_start_flatten_reports_encrypted_pdf_failure(encrypted_pdf: Path) -> None:
    session = FlattenSession()
    session.add_input(str(encrypted_pdf))

    processor = FlattenProcessor()
    plan = processor.prepare_batch(session)
    processor.start_flatten(session, plan)
    _wait_for_completion(processor)

    results = processor.poll_results()
    failures = [result for result in results if result["type"] == "failure"]

    assert len(failures) == 1
    assert "暗号化されたPDF" in str(failures[0]["message"])


def test_start_flatten_reports_permission_error(sample_pdf: Path, monkeypatch) -> None:
    session = FlattenSession()
    session.add_input(str(sample_pdf))

    processor = FlattenProcessor()
    plan = processor.prepare_batch(session)

    def fake_save(_document, _temp_output: Path) -> None:
        raise PermissionError("in use")

    monkeypatch.setattr(processor, "_save_flattened_pdf", fake_save)

    processor.start_flatten(session, plan)
    _wait_for_completion(processor)
    results = processor.poll_results()
    failures = [result for result in results if result["type"] == "failure"]

    assert len(failures) == 1
    assert "他のアプリ" in str(failures[0]["message"])


def test_cancel_stops_before_replace_and_cleans_temp(sample_pdf: Path, tmp_path: Path, monkeypatch) -> None:
    second_pdf = tmp_path / "second.pdf"
    shutil.copy2(sample_pdf, second_pdf)

    session = FlattenSession()
    session.add_inputs([str(sample_pdf), str(second_pdf)])

    processor = FlattenProcessor()
    plan = processor.prepare_batch(session)

    def fake_save(document: fitz.Document, temp_output: Path) -> None:
        document.save(str(temp_output), garbage=3, deflate=True)
        processor.request_cancel()

    monkeypatch.setattr(processor, "_save_flattened_pdf", fake_save)

    processor.start_flatten(session, plan)
    _wait_for_completion(processor)
    results = processor.poll_results()

    cancelled = [result for result in results if result["type"] == "cancelled"]
    assert len(cancelled) == 1
    assert session.processed_items == 0
    assert not Path(plan.jobs[0].output_path).exists()
    assert not list(sample_pdf.parent.glob("*.flattening-*.pdf"))


def test_reentry_is_ignored(sample_pdf: Path, monkeypatch) -> None:
    session = FlattenSession()
    session.add_input(str(sample_pdf))

    processor = FlattenProcessor()
    plan = processor.prepare_batch(session)
    allow_finish = threading.Event()

    original_flatten_job = processor._flatten_job

    def slow_flatten(current_session: FlattenSession, job: FlattenJob) -> dict[str, object]:
        allow_finish.wait(timeout=2.0)
        return original_flatten_job(current_session, job)

    monkeypatch.setattr(processor, "_flatten_job", slow_flatten)

    processor.start_flatten(session, plan)
    processor.start_flatten(session, plan)
    allow_finish.set()
    _wait_for_completion(processor)
    results = processor.poll_results()

    assert len([result for result in results if result["type"] == "success"]) == 1
    assert len([result for result in results if result["type"] == "finished"]) == 1


def test_progress_events_follow_processed_items(sample_pdf: Path, broken_pdf: Path) -> None:
    session = FlattenSession()
    session.add_inputs([str(sample_pdf), str(broken_pdf)])

    processor = FlattenProcessor()
    plan = processor.prepare_batch(session)
    processor.start_flatten(session, plan)
    _wait_for_completion(processor)
    results = processor.poll_results()

    progress_events = [result for result in results if result["type"] == "progress"]
    finished = [result for result in results if result["type"] == "finished"]

    assert len(progress_events) == 2
    assert progress_events[-1]["processed_items"] == 2
    assert finished[0]["success_count"] == 1
    assert finished[0]["failure_count"] == 1


def test_temp_file_is_cleaned_when_save_fails(sample_pdf: Path, monkeypatch) -> None:
    session = FlattenSession()
    session.add_input(str(sample_pdf))

    processor = FlattenProcessor()
    plan = processor.prepare_batch(session)

    def failing_save(document: fitz.Document, temp_output: Path) -> None:
        document.save(str(temp_output), garbage=3, deflate=True)
        raise OSError("disk full")

    monkeypatch.setattr(processor, "_save_flattened_pdf", failing_save)

    processor.start_flatten(session, plan)
    _wait_for_completion(processor)
    results = processor.poll_results()
    failures = [result for result in results if result["type"] == "failure"]

    assert len(failures) == 1
    assert "保存に失敗しました" in str(failures[0]["message"])
    assert not list(sample_pdf.parent.glob("*.flattening-*.pdf"))


def test_start_flatten_runs_post_compression_and_publishes_compressed_output(sample_pdf: Path, monkeypatch) -> None:
    session = FlattenSession()
    session.add_input(str(sample_pdf))
    session.set_post_compression_enabled(True)
    session.set_ghostscript_preset(PDF_GHOSTSCRIPT_PRESET_SCREEN)
    session.set_post_compression_use_pikepdf(True)

    processor = FlattenProcessor()
    plan = processor.prepare_batch(session)

    captured_calls: list[tuple[Path, Path, str, bool, dict[str, bool]]] = []

    def fake_compress(
        input_path,
        output_path,
        *,
        preset,
        custom_dpi,
        run_lossless_postprocess,
        lossless_options,
    ):
        captured_calls.append(
            (
                Path(input_path),
                Path(output_path),
                preset,
                run_lossless_postprocess,
                dict(lossless_options or {}),
            ),
        )
        Path(output_path).write_bytes(b"compressed")
        return True, "compressed", None

    monkeypatch.setattr("model.flatten.flatten_processor.compress_pdf_with_ghostscript", fake_compress)

    processor.start_flatten(session, plan)
    _wait_for_completion(processor)
    results = processor.poll_results()

    successes = [result for result in results if result["type"] == "success"]
    finished = [result for result in results if result["type"] == "finished"]

    assert len(successes) == 1
    assert finished[0]["success_count"] == 1
    assert finished[0]["warning_count"] == 0
    assert captured_calls[0][0].name.endswith(".pdf")
    assert ".flattening-" in captured_calls[0][0].name
    assert ".flatten-compress-" in captured_calls[0][1].name
    assert captured_calls[0][2] == PDF_GHOSTSCRIPT_PRESET_SCREEN
    assert captured_calls[0][3] is True
    assert captured_calls[0][4]["linearize"] is True

    output_path = Path(plan.jobs[0].output_path)
    assert output_path.read_bytes() == b"compressed"
    assert not list(sample_pdf.parent.glob("*.flattening-*.pdf"))
    assert not list(sample_pdf.parent.glob("*.flatten-compress-*.pdf"))


def test_start_flatten_publishes_flattened_output_when_post_compression_fails(sample_pdf: Path, monkeypatch) -> None:
    session = FlattenSession()
    session.add_input(str(sample_pdf))
    session.set_post_compression_enabled(True)

    processor = FlattenProcessor()
    plan = processor.prepare_batch(session)

    def fake_compress(
        _input_path,
        output_path,
        *,
        preset,
        custom_dpi,
        run_lossless_postprocess,
        lossless_options,
    ):
        Path(output_path).write_bytes(b"partial-compressed")
        return False, "Ghostscript compression failed: missing executable", None

    monkeypatch.setattr("model.flatten.flatten_processor.compress_pdf_with_ghostscript", fake_compress)

    processor.start_flatten(session, plan)
    _wait_for_completion(processor)
    results = processor.poll_results()

    warnings = [result for result in results if result["type"] == "warning"]
    finished = [result for result in results if result["type"] == "finished"]

    assert len(warnings) == 1
    assert "圧縮はスキップされました" in str(warnings[0]["message"])
    assert finished[0]["success_count"] == 0
    assert finished[0]["warning_count"] == 1

    output_path = Path(plan.jobs[0].output_path)
    with fitz.open(str(sample_pdf)) as source_doc:
        expected_page_count = source_doc.page_count
    with fitz.open(str(output_path)) as flattened:
        assert flattened.page_count == expected_page_count
    assert not list(sample_pdf.parent.glob("*.flattening-*.pdf"))
    assert not list(sample_pdf.parent.glob("*.flatten-compress-*.pdf"))


def test_cancel_after_post_compression_cleans_temp_and_does_not_publish_output(sample_pdf: Path, monkeypatch) -> None:
    session = FlattenSession()
    session.add_input(str(sample_pdf))
    session.set_post_compression_enabled(True)

    processor = FlattenProcessor()
    plan = processor.prepare_batch(session)

    def fake_compress(
        _input_path,
        output_path,
        *,
        preset,
        custom_dpi,
        run_lossless_postprocess,
        lossless_options,
    ):
        Path(output_path).write_bytes(b"compressed")
        processor.request_cancel()
        return True, "compressed", None

    monkeypatch.setattr("model.flatten.flatten_processor.compress_pdf_with_ghostscript", fake_compress)

    processor.start_flatten(session, plan)
    _wait_for_completion(processor)
    results = processor.poll_results()

    cancelled = [result for result in results if result["type"] == "cancelled"]
    assert len(cancelled) == 1
    assert not Path(plan.jobs[0].output_path).exists()
    assert not list(sample_pdf.parent.glob("*.flattening-*.pdf"))
    assert not list(sample_pdf.parent.glob("*.flatten-compress-*.pdf"))