"""ページ単位のサムネイル遅延読み込みローダー。"""

from __future__ import annotations

import io
import queue
import threading
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

import fitz
from PIL import Image


THUMBNAIL_BASE_SIZE = 128


@dataclass(slots=True, frozen=True)
class PageThumbnailKey:
    """キャッシュキー: パス + ページ番号。"""

    path: str
    page_index: int


@dataclass(slots=True)
class PageThumbnailResult:
    """1 ページ分のサムネイル読み込み結果。"""

    path: str
    page_index: int
    status: str
    image_bytes: bytes | None = None
    error_message: str | None = None

    @property
    def key(self) -> PageThumbnailKey:
        return PageThumbnailKey(path=self.path, page_index=self.page_index)


class PageThumbnailLoader:
    """ページ単位でサムネイルを非同期読み込みしキャッシュする。"""

    def __init__(self, cache_limit: int = 256) -> None:
        self.result_queue: queue.Queue[PageThumbnailResult] = queue.Queue()
        self._cache: OrderedDict[PageThumbnailKey, PageThumbnailResult] = OrderedDict()
        self._pending: set[PageThumbnailKey] = set()
        self._active_workers = 0
        self._lock = threading.Lock()
        self._cache_limit = max(1, cache_limit)

    @property
    def is_loading(self) -> bool:
        with self._lock:
            return self._active_workers > 0

    def request_thumbnails(self, requests: list[tuple[str, int]]) -> list[tuple[str, int]]:
        """未キャッシュ・未リクエストのページに対してサムネイル読み込みを開始する。

        Args:
            requests: (path, page_index) のリスト

        Returns:
            実際にリクエストを発行した (path, page_index) のリスト
        """
        to_load: list[tuple[str, int]] = []

        with self._lock:
            for raw_path, page_index in requests:
                normalized = str(Path(raw_path))
                key = PageThumbnailKey(path=normalized, page_index=page_index)
                if key in self._cache or key in self._pending:
                    continue
                self._pending.add(key)
                to_load.append((normalized, page_index))

            if to_load:
                self._active_workers += 1

        if to_load:
            worker = threading.Thread(
                target=self._load_batch,
                args=(to_load,),
                daemon=True,
            )
            worker.start()

        return to_load

    def poll_results(self) -> list[PageThumbnailResult]:
        """読み込み完了済みの結果をまとめて返す。"""
        results: list[PageThumbnailResult] = []
        while True:
            try:
                results.append(self.result_queue.get_nowait())
            except queue.Empty:
                break
        return results

    def get_cached(self, path: str, page_index: int) -> PageThumbnailResult | None:
        """キャッシュ済み結果を返す。"""
        normalized = str(Path(path))
        key = PageThumbnailKey(path=normalized, page_index=page_index)
        with self._lock:
            result = self._cache.get(key)
            if result is None:
                return None
            self._cache.move_to_end(key)
            return result

    def is_pending(self, path: str, page_index: int) -> bool:
        """指定ページの読み込みが未完了かどうかを返す。"""
        normalized = str(Path(path))
        key = PageThumbnailKey(path=normalized, page_index=page_index)
        with self._lock:
            return key in self._pending

    def invalidate(self, path: str) -> None:
        """指定パスの全ページキャッシュを無効化する。"""
        normalized = str(Path(path))
        with self._lock:
            keys_to_remove = [k for k in self._cache if k.path == normalized]
            for key in keys_to_remove:
                del self._cache[key]
            self._pending = {k for k in self._pending if k.path != normalized}

    def _store_in_cache(self, result: PageThumbnailResult) -> None:
        """結果をキャッシュに格納し、上限超過分を LRU 順に削除する。"""
        key = result.key
        self._cache[key] = result
        self._cache.move_to_end(key)
        while len(self._cache) > self._cache_limit:
            self._cache.popitem(last=False)

    def _load_batch(self, pages: list[tuple[str, int]]) -> None:
        try:
            # パスごとにグループ化して PDF を開く回数を最小化する
            by_path: dict[str, list[int]] = {}
            for path, page_index in pages:
                by_path.setdefault(path, []).append(page_index)

            for path, indices in by_path.items():
                self._load_pages_from_file(path, indices)
        finally:
            with self._lock:
                self._active_workers = max(0, self._active_workers - 1)

    def _load_pages_from_file(self, path: str, indices: list[int]) -> None:
        try:
            doc = fitz.open(path)
        except Exception as exc:
            for page_index in indices:
                result = PageThumbnailResult(
                    path=path, page_index=page_index, status="error",
                    error_message=str(exc),
                )
                key = result.key
                with self._lock:
                    self._pending.discard(key)
                    self._store_in_cache(result)
                self.result_queue.put(result)
            return

        try:
            for page_index in indices:
                result = self._render_page(doc, path, page_index)
                key = result.key
                with self._lock:
                    self._pending.discard(key)
                    self._store_in_cache(result)
                self.result_queue.put(result)
        finally:
            doc.close()

    def _render_page(self, doc: fitz.Document, path: str, page_index: int) -> PageThumbnailResult:
        try:
            if page_index < 0 or page_index >= doc.page_count:
                raise IndexError(f"page_index {page_index} out of range (0..{doc.page_count - 1})")

            page = doc.load_page(page_index)
            rect = page.rect
            zoom = min(
                THUMBNAIL_BASE_SIZE / max(1.0, rect.width),
                THUMBNAIL_BASE_SIZE / max(1.0, rect.height),
            )
            zoom = max(0.2, zoom)
            pixmap = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)

            image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
            image.thumbnail(
                (THUMBNAIL_BASE_SIZE, THUMBNAIL_BASE_SIZE), Image.Resampling.LANCZOS,
            )

            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            return PageThumbnailResult(
                path=path, page_index=page_index, status="ready",
                image_bytes=buffer.getvalue(),
            )
        except Exception as exc:
            return PageThumbnailResult(
                path=path, page_index=page_index, status="error",
                error_message=str(exc),
            )
