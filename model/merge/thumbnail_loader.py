"""PDF1ページ目サムネイルの非同期読み込みを担当する。"""

from __future__ import annotations

import io
import queue
import threading
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

import fitz
from PIL import Image


THUMBNAIL_MAX_WIDTH = 72
THUMBNAIL_MAX_HEIGHT = 96


@dataclass(slots=True)
class ThumbnailResult:
    """1 つの PDF に対するサムネイル読み込み結果。"""

    path: str
    status: str
    image_bytes: bytes | None = None
    error_message: str | None = None


class ThumbnailLoader:
    """PyMuPDF を用いた PDF サムネイル生成をバックグラウンドで行う。"""

    def __init__(self, cache_limit: int = 64) -> None:
        self.result_queue: queue.Queue[ThumbnailResult] = queue.Queue()
        self._cache: OrderedDict[str, ThumbnailResult] = OrderedDict()
        self._pending_paths: set[str] = set()
        self._active_workers = 0
        self._lock = threading.Lock()
        self._cache_limit = max(1, cache_limit)

    @property
    def is_loading(self) -> bool:
        with self._lock:
            return self._active_workers > 0

    def request_thumbnails(self, paths: list[str]) -> list[str]:
        """未キャッシュの PDF に対してサムネイル読み込みを開始する。"""
        requested: list[str] = []

        with self._lock:
            for raw_path in paths:
                normalized = str(Path(raw_path))
                if normalized in self._cache or normalized in self._pending_paths:
                    continue
                self._pending_paths.add(normalized)
                requested.append(normalized)

            if requested:
                self._active_workers += 1

        if requested:
            worker = threading.Thread(
                target=self._load_batch,
                args=(requested,),
                daemon=True,
            )
            worker.start()

        return requested

    def poll_results(self) -> list[ThumbnailResult]:
        """読み込み完了済みの結果をまとめて返す。"""
        results: list[ThumbnailResult] = []
        while True:
            try:
                results.append(self.result_queue.get_nowait())
            except queue.Empty:
                break
        return results

    def get_cached_result(self, path: str) -> ThumbnailResult | None:
        """キャッシュ済み結果を返す。"""
        normalized = str(Path(path))
        with self._lock:
            result = self._cache.get(normalized)
            if result is None:
                return None
            self._cache.move_to_end(normalized)
            return result

    def is_pending(self, path: str) -> bool:
        """指定パスの読み込みが未完了かどうかを返す。"""
        normalized = str(Path(path))
        with self._lock:
            return normalized in self._pending_paths

    def _load_batch(self, paths: list[str]) -> None:
        try:
            for path in paths:
                result = self._build_thumbnail(path)
                with self._lock:
                    self._pending_paths.discard(path)
                    self._store_in_cache(result)
                self.result_queue.put(result)
        finally:
            with self._lock:
                self._active_workers = max(0, self._active_workers - 1)

    def _store_in_cache(self, result: ThumbnailResult) -> None:
        self._cache[result.path] = result
        self._cache.move_to_end(result.path)
        while len(self._cache) > self._cache_limit:
            self._cache.popitem(last=False)

    def _build_thumbnail(self, path: str) -> ThumbnailResult:
        try:
            with fitz.open(path) as document:
                if document.page_count <= 0:
                    raise ValueError("empty pdf")

                page = document.load_page(0)
                rect = page.rect
                zoom = min(
                    THUMBNAIL_MAX_WIDTH / max(1.0, rect.width),
                    THUMBNAIL_MAX_HEIGHT / max(1.0, rect.height),
                )
                zoom = max(0.2, zoom)
                pixmap = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)

            image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
            image.thumbnail((THUMBNAIL_MAX_WIDTH, THUMBNAIL_MAX_HEIGHT), Image.Resampling.LANCZOS)

            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            return ThumbnailResult(path=path, status="ready", image_bytes=buffer.getvalue())
        except Exception as exc:
            return ThumbnailResult(path=path, status="error", error_message=str(exc))