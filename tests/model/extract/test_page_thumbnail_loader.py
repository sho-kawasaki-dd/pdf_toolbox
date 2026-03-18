from __future__ import annotations

import time
from pathlib import Path

from model.extract.page_thumbnail_loader import PageThumbnailLoader


def _wait_for_loader(loader: PageThumbnailLoader, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while loader.is_loading and time.monotonic() < deadline:
        time.sleep(0.05)


def test_generates_thumbnail_for_valid_page(sample_pdf: Path) -> None:
    loader = PageThumbnailLoader()

    requested = loader.request_thumbnails([(str(sample_pdf), 0)])
    _wait_for_loader(loader)
    results = loader.poll_results()

    assert requested == [(str(sample_pdf), 0)]
    assert len(results) == 1
    assert results[0].status == "ready"
    assert results[0].page_index == 0
    assert results[0].image_bytes is not None
    assert loader.get_cached(str(sample_pdf), 0) is not None


def test_generates_thumbnails_for_multiple_pages(sample_pdf: Path) -> None:
    loader = PageThumbnailLoader()

    pages = [(str(sample_pdf), i) for i in range(3)]
    requested = loader.request_thumbnails(pages)
    _wait_for_loader(loader)
    results = loader.poll_results()

    assert len(requested) == 3
    assert len(results) == 3
    assert all(r.status == "ready" for r in results)


def test_returns_error_for_broken_pdf(broken_pdf: Path) -> None:
    loader = PageThumbnailLoader()

    loader.request_thumbnails([(str(broken_pdf), 0)])
    _wait_for_loader(loader)
    results = loader.poll_results()

    assert len(results) == 1
    assert results[0].status == "error"
    assert results[0].image_bytes is None
    assert loader.get_cached(str(broken_pdf), 0) is not None
    assert loader.get_cached(str(broken_pdf), 0).status == "error"


def test_returns_error_for_out_of_range_page(sample_pdf: Path) -> None:
    loader = PageThumbnailLoader()

    loader.request_thumbnails([(str(sample_pdf), 999)])
    _wait_for_loader(loader)
    results = loader.poll_results()

    assert len(results) == 1
    assert results[0].status == "error"


def test_skips_duplicate_requests_while_pending(sample_pdf: Path) -> None:
    loader = PageThumbnailLoader()

    first = loader.request_thumbnails([(str(sample_pdf), 0)])
    second = loader.request_thumbnails([(str(sample_pdf), 0)])
    _wait_for_loader(loader)

    assert first == [(str(sample_pdf), 0)]
    assert second == []


def test_skips_already_cached(sample_pdf: Path) -> None:
    loader = PageThumbnailLoader()

    loader.request_thumbnails([(str(sample_pdf), 0)])
    _wait_for_loader(loader)
    loader.poll_results()

    # second request should skip because it's cached
    second = loader.request_thumbnails([(str(sample_pdf), 0)])
    assert second == []


def test_is_pending(sample_pdf: Path) -> None:
    loader = PageThumbnailLoader()

    # not pending before request
    assert not loader.is_pending(str(sample_pdf), 0)

    loader.request_thumbnails([(str(sample_pdf), 0)])
    _wait_for_loader(loader)
    loader.poll_results()

    # not pending after completion
    assert not loader.is_pending(str(sample_pdf), 0)


def test_invalidate_removes_cache(sample_pdf: Path) -> None:
    loader = PageThumbnailLoader()

    loader.request_thumbnails([(str(sample_pdf), 0), (str(sample_pdf), 1)])
    _wait_for_loader(loader)
    loader.poll_results()

    assert loader.get_cached(str(sample_pdf), 0) is not None
    assert loader.get_cached(str(sample_pdf), 1) is not None

    loader.invalidate(str(sample_pdf))
    assert loader.get_cached(str(sample_pdf), 0) is None
    assert loader.get_cached(str(sample_pdf), 1) is None


def test_cache_lru_eviction(sample_pdf: Path) -> None:
    loader = PageThumbnailLoader(cache_limit=3)

    # Load 4 pages into a cache that holds 3
    loader.request_thumbnails([(str(sample_pdf), i) for i in range(4)])
    _wait_for_loader(loader)
    loader.poll_results()

    # The first entry (page 0) should have been evicted
    assert loader.get_cached(str(sample_pdf), 0) is None
    assert loader.get_cached(str(sample_pdf), 1) is not None
    assert loader.get_cached(str(sample_pdf), 2) is not None
    assert loader.get_cached(str(sample_pdf), 3) is not None
