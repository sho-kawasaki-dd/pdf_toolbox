from __future__ import annotations

from pathlib import Path

from model.compress.compression_session import CompressionCandidate, CompressionSession
from model.compress.settings import (
    PDF_LOSSLESS_OPTIONS_DEFAULT,
    PDF_LOSSY_JPEG_QUALITY_DEFAULT,
    PDF_LOSSY_PNG_QUALITY_DEFAULT,
)


def test_session_defaults() -> None:
    session = CompressionSession()

    assert session.mode == "both"
    assert session.jpeg_quality == PDF_LOSSY_JPEG_QUALITY_DEFAULT
    assert session.png_quality == PDF_LOSSY_PNG_QUALITY_DEFAULT
    assert session.lossless_options == PDF_LOSSLESS_OPTIONS_DEFAULT
    assert session.lossless_options["clean_metadata"] is False


def test_add_remove_and_clear_inputs(tmp_path: Path) -> None:
    session = CompressionSession()
    first = tmp_path / "first.pdf"
    second = tmp_path / "second.pdf"

    session.add_inputs([str(first), str(second)])
    assert session.input_paths == [str(first), str(second)]

    assert session.remove_input(str(first)) is True
    assert session.remove_input(str(first)) is False
    assert session.input_paths == [str(second)]

    session.clear_inputs()
    assert session.input_paths == []


def test_collect_batch_jobs_numbers_conflicts(output_conflict_dir: Path) -> None:
    session = CompressionSession()
    session.set_output_dir(str(output_conflict_dir))

    jobs = session.collect_batch_jobs([
        CompressionCandidate(
            preferred_filename="sample.pdf",
            source_type="file",
            source_label="source-a",
            source_path="C:/input/sample.pdf",
        ),
        CompressionCandidate(
            preferred_filename="sample.pdf",
            source_type="file",
            source_label="source-b",
            source_path="C:/input/sample-copy.pdf",
        ),
    ])

    assert jobs[0].output_path.endswith("sample (1).pdf")
    assert jobs[1].output_path.endswith("sample (2).pdf")


def test_progress_snapshot_tracks_counts() -> None:
    session = CompressionSession()
    session.begin_batch(4)
    session.record_success()
    session.record_failure()
    session.record_skip()

    snapshot = session.progress_snapshot()
    assert snapshot["total_items"] == 4
    assert snapshot["processed_items"] == 3
    assert snapshot["success_count"] == 1
    assert snapshot["failure_count"] == 1
    assert snapshot["skip_count"] == 1
    assert snapshot["progress_percent"] == 75


def test_update_lossless_options() -> None:
    session = CompressionSession()
    session.update_lossless_options(clean_metadata=True, linearize=False)

    assert session.lossless_options["clean_metadata"] is True
    assert session.lossless_options["linearize"] is False


def test_setting_validation_rejects_out_of_range_values() -> None:
    """Session 層で異常値を拒否し、Presenter 側へ不正状態を漏らさない。"""
    session = CompressionSession()

    import pytest

    with pytest.raises(ValueError):
        session.set_mode("unsupported")

    with pytest.raises(ValueError):
        session.set_lossy_dpi(0)

    with pytest.raises(ValueError):
        session.set_jpeg_quality(101)

    with pytest.raises(ValueError):
        session.set_png_quality(-1)

    with pytest.raises(ValueError):
        session.set_pngquant_speed(12)

    with pytest.raises(KeyError):
        session.update_lossless_options(unknown_option=True)


def test_sanitize_filename_handles_reserved_names_and_invalid_characters() -> None:
    """ZIP 内の名前や Windows 予約名でも安全な出力名へ正規化できる。"""
    sanitized = CompressionSession._sanitize_filename('  bad:name*?.PDF  ')
    reserved = CompressionSession._sanitize_filename("CON.pdf")

    assert sanitized == "bad_name.pdf"
    assert reserved == "CON_file.pdf"


def test_collect_batch_jobs_raises_without_output_dir() -> None:
    """出力先未設定のままジョブ化しないことを保証する。"""
    import pytest

    session = CompressionSession()
    candidate = CompressionCandidate(
        preferred_filename="sample.pdf",
        source_type="file",
        source_label="source",
        source_path="C:/input/sample.pdf",
    )

    with pytest.raises(ValueError):
        session.collect_batch_jobs([candidate])