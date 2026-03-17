from __future__ import annotations

import time
from pathlib import Path

from model.merge.thumbnail_loader import ThumbnailLoader


def _wait_for_loader(loader: ThumbnailLoader, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while loader.is_loading and time.monotonic() < deadline:
        time.sleep(0.05)


def test_generates_thumbnail_for_valid_pdf(sample_pdf: Path) -> None:
    loader = ThumbnailLoader()

    requested = loader.request_thumbnails([str(sample_pdf)])
    _wait_for_loader(loader)
    results = loader.poll_results()

    assert requested == [str(sample_pdf)]
    assert len(results) == 1
    assert results[0].status == "ready"
    assert results[0].image_bytes is not None
    assert loader.get_cached_result(str(sample_pdf)) is not None


def test_returns_error_result_for_broken_pdf(broken_pdf: Path) -> None:
    loader = ThumbnailLoader()

    loader.request_thumbnails([str(broken_pdf)])
    _wait_for_loader(loader)
    results = loader.poll_results()

    assert len(results) == 1
    assert results[0].status == "error"
    assert results[0].image_bytes is None
    assert loader.get_cached_result(str(broken_pdf)).status == "error"


def test_skips_duplicate_requests_while_pending(sample_pdf: Path) -> None:
    loader = ThumbnailLoader()

    first = loader.request_thumbnails([str(sample_pdf)])
    second = loader.request_thumbnails([str(sample_pdf)])
    _wait_for_loader(loader)

    assert first == [str(sample_pdf)]
    assert second == []