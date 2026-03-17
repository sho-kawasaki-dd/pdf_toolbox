from __future__ import annotations

from pathlib import Path

import pytest

from model.pdf_to_jpeg.pdf_to_jpeg_session import DEFAULT_JPEG_QUALITY, PdfToJpegSession


def test_session_defaults() -> None:
    session = PdfToJpegSession()

    assert session.input_pdf_path is None
    assert session.output_dir is None
    assert session.output_subfolder_name is None
    assert session.jpeg_quality == DEFAULT_JPEG_QUALITY
    assert session.can_execute() is False


def test_output_subfolder_and_fixed_filename_rule(sample_pdf: Path, tmp_path: Path) -> None:
    session = PdfToJpegSession()
    session.set_input_pdf(str(sample_pdf))
    session.set_output_dir(str(tmp_path / "export-root"))

    assert session.output_subfolder_name == "sample"
    assert session.output_subfolder_path == str(tmp_path / "export-root" / "sample")
    assert session.build_output_filename(1) == "sample_001.jpg"
    assert session.build_output_filename(12) == "sample_012.jpg"


def test_collect_export_jobs_targets_pdf_named_subfolder(sample_pdf: Path, tmp_path: Path) -> None:
    session = PdfToJpegSession()
    session.set_input_pdf(str(sample_pdf))
    session.set_output_dir(str(tmp_path / "output"))

    jobs = session.collect_export_jobs(3)

    assert [job.page_number for job in jobs] == [1, 2, 3]
    assert jobs[0].output_path.endswith("sample\\sample_001.jpg")
    assert jobs[2].output_path.endswith("sample\\sample_003.jpg")


def test_collect_conflicting_output_paths(sample_pdf: Path, tmp_path: Path) -> None:
    session = PdfToJpegSession()
    session.set_input_pdf(str(sample_pdf))
    session.set_output_dir(str(tmp_path / "output"))

    subfolder = tmp_path / "output" / "sample"
    subfolder.mkdir(parents=True)
    first = subfolder / "sample_001.jpg"
    third = subfolder / "sample_003.jpg"
    first.write_bytes(b"occupied")
    third.write_bytes(b"occupied")

    conflicts = session.collect_conflicting_output_paths(3)

    assert conflicts == [str(first), str(third)]


def test_can_execute_and_quality_validation(sample_pdf: Path, tmp_path: Path) -> None:
    session = PdfToJpegSession()
    session.set_input_pdf(str(sample_pdf))
    assert session.can_execute() is False

    session.set_output_dir(str(tmp_path / "output"))
    session.set_jpeg_quality(77)

    assert session.can_execute() is True
    assert session.jpeg_quality == 77

    with pytest.raises(ValueError):
        session.set_jpeg_quality(101)


def test_progress_snapshot_tracks_current_page() -> None:
    session = PdfToJpegSession()
    session.begin_batch(4)
    session.mark_page_started(2)
    session.record_success()
    session.record_failure()

    snapshot = session.progress_snapshot()
    assert snapshot["total_pages"] == 4
    assert snapshot["processed_pages"] == 2
    assert snapshot["success_count"] == 1
    assert snapshot["failure_count"] == 1
    assert snapshot["current_page_number"] == 2
    assert snapshot["progress_percent"] == 50


def test_collect_export_jobs_requires_input_and_output() -> None:
    session = PdfToJpegSession()

    with pytest.raises(ValueError):
        session.collect_export_jobs(1)