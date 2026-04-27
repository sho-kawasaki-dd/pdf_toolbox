from __future__ import annotations

from model.flatten.flatten_session import FlattenSession


def test_input_management_and_clear(tmp_path) -> None:
    first = tmp_path / "first.pdf"
    second = tmp_path / "second.pdf"

    session = FlattenSession()
    session.add_input(str(first))
    session.add_inputs([str(second)])

    assert session.input_paths == [str(first), str(second)]
    assert session.remove_input(str(first)) is True
    assert session.remove_input(str(first)) is False

    session.clear_inputs()
    assert session.input_paths == []


def test_build_output_and_temp_paths(sample_pdf) -> None:
    session = FlattenSession()

    output_path = session.build_output_path(str(sample_pdf))
    temp_path = session.build_temp_output_path(output_path, "abcd1234")

    assert output_path.endswith("sample_flattened.pdf")
    assert temp_path.endswith(".sample_flattened.flattening-abcd1234.pdf")


def test_progress_snapshot_tracks_counts() -> None:
    session = FlattenSession()
    session.begin_batch(4)
    session.record_success()
    session.record_warning()
    session.record_failure()
    session.record_skip()

    assert session.progress_snapshot() == {
        "total_items": 4,
        "processed_items": 4,
        "success_count": 1,
        "warning_count": 1,
        "failure_count": 1,
        "skip_count": 1,
        "progress_percent": 100,
    }


def test_validate_windows_path_limit_rejects_260_chars() -> None:
    session = FlattenSession()

    too_long_path = f"C:\\{'a' * 257}"

    try:
        session.validate_windows_path_limit(too_long_path)
    except ValueError as exc:
        assert "MAX_PATH" in str(exc)
    else:
        raise AssertionError("ValueError was not raised")


def test_begin_batch_resets_existing_counters() -> None:
    session = FlattenSession()
    session.begin_batch(5)
    session.record_success()
    session.record_warning()
    session.record_failure()
    session.record_skip()

    session.begin_batch(2)

    assert session.progress_snapshot() == {
        "total_items": 2,
        "processed_items": 0,
        "success_count": 0,
        "warning_count": 0,
        "failure_count": 0,
        "skip_count": 0,
        "progress_percent": 0,
    }


def test_post_compression_settings_and_temp_paths(monkeypatch, sample_pdf) -> None:
    monkeypatch.setattr("model.flatten.flatten_session.is_ghostscript_available", lambda: True)
    session = FlattenSession()

    session.set_post_compression_enabled(True)
    session.set_ghostscript_preset("printer")
    session.set_post_compression_use_pikepdf(True)

    output_path = session.build_output_path(str(sample_pdf))
    compressed_temp_path = session.build_post_compression_temp_output_path(output_path, "efgh5678")

    assert session.post_compression_enabled is True
    assert session.ghostscript_preset == "printer"
    assert session.post_compression_use_pikepdf is True
    assert compressed_temp_path.endswith(".sample_flattened.flatten-compress-efgh5678.pdf")
    assert session.build_post_compression_lossless_options()["linearize"] is True


def test_refresh_external_tool_state_disables_post_compression_when_ghostscript_missing(monkeypatch) -> None:
    monkeypatch.setattr("model.flatten.flatten_session.is_ghostscript_available", lambda: True)
    session = FlattenSession()
    session.set_post_compression_enabled(True)

    monkeypatch.setattr("model.flatten.flatten_session.is_ghostscript_available", lambda: False)
    session.refresh_external_tool_state()

    assert session.ghostscript_available is False
    assert session.post_compression_enabled is False