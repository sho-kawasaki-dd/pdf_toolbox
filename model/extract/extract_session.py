"""PDF 抽出機能のセッション状態を管理する。"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path

# ズーム設定
ZOOM_MIN = 50
ZOOM_MAX = 200
ZOOM_STEP = 25
ZOOM_DEFAULT = 100


@dataclass(slots=True)
class SourceDocument:
    """Source に追加された PDF 1 ファイルの情報。"""

    id: str
    path: str
    page_count: int


@dataclass(slots=True, frozen=True)
class SourcePageRef:
    """Source 側の特定ページへの参照。"""

    doc_id: str
    page_index: int


@dataclass(slots=True)
class TargetPageEntry:
    """Target リストの 1 エントリ。"""

    id: str
    source_ref: SourcePageRef


def _normalize_path(raw: str) -> str:
    return str(Path(raw))


def _path_key(raw: str) -> str:
    return Path(raw).as_posix().casefold()


class ExtractSession:
    """PDF 抽出のソース・ターゲット状態を保持するセッション。"""

    def __init__(self) -> None:
        self.source_documents: list[SourceDocument] = []
        self.selected_source_pages: list[SourcePageRef] = []
        self.target_entries: list[TargetPageEntry] = []
        self.selected_target_ids: list[str] = []
        self.output_path: str | None = None
        self.is_running: bool = False
        self.cancel_requested: bool = False
        self.source_zoom_percent: int = ZOOM_DEFAULT
        self.target_zoom_percent: int = ZOOM_DEFAULT

    # ── Source 操作 ──────────────────────────────────────

    def add_source(self, path: str, page_count: int) -> SourceDocument | None:
        """Source に PDF を追加する。重複パスは無視して None を返す。"""
        normalized = _normalize_path(path)
        key = _path_key(normalized)
        for doc in self.source_documents:
            if _path_key(doc.path) == key:
                return None
        doc = SourceDocument(id=uuid.uuid4().hex, path=normalized, page_count=page_count)
        self.source_documents.append(doc)
        return doc

    def remove_source(self, doc_id: str) -> bool:
        """指定 doc_id の Source PDF を削除し、Target からも該当ページを連動削除する。"""
        before = len(self.source_documents)
        self.source_documents = [d for d in self.source_documents if d.id != doc_id]
        if len(self.source_documents) == before:
            return False

        # Source 選択からも除去
        self.selected_source_pages = [
            ref for ref in self.selected_source_pages if ref.doc_id != doc_id
        ]
        # Target からも連動削除
        self.target_entries = [
            e for e in self.target_entries if e.source_ref.doc_id != doc_id
        ]
        # Target 選択の整合
        remaining_ids = {e.id for e in self.target_entries}
        self.selected_target_ids = [
            tid for tid in self.selected_target_ids if tid in remaining_ids
        ]
        return True

    def get_source_document(self, doc_id: str) -> SourceDocument | None:
        for doc in self.source_documents:
            if doc.id == doc_id:
                return doc
        return None

    def set_selected_source_pages(self, refs: list[SourcePageRef]) -> None:
        """Source の選択ページを設定する。存在する doc_id/page_index のみ保持。"""
        valid_ranges: dict[str, int] = {
            doc.id: doc.page_count for doc in self.source_documents
        }
        self.selected_source_pages = [
            ref
            for ref in refs
            if ref.doc_id in valid_ranges and 0 <= ref.page_index < valid_ranges[ref.doc_id]
        ]

    # ── Target 操作 ──────────────────────────────────────

    def add_to_target(self, refs: list[SourcePageRef]) -> list[TargetPageEntry]:
        """Source ページ参照群を Target 末尾に追加する（重複許可）。"""
        added: list[TargetPageEntry] = []
        valid_ranges: dict[str, int] = {
            doc.id: doc.page_count for doc in self.source_documents
        }
        for ref in refs:
            if ref.doc_id not in valid_ranges:
                continue
            if not (0 <= ref.page_index < valid_ranges[ref.doc_id]):
                continue
            entry = TargetPageEntry(id=uuid.uuid4().hex, source_ref=ref)
            self.target_entries.append(entry)
            added.append(entry)
        return added

    def set_selected_target_ids(self, ids: list[str]) -> None:
        """Target の選択を設定する。存在する ID のみ保持。"""
        existing = {e.id for e in self.target_entries}
        self.selected_target_ids = [tid for tid in ids if tid in existing]

    def remove_selected_targets(self) -> list[str]:
        """選択中の Target エントリを削除し、削除した ID を返す。"""
        if not self.selected_target_ids:
            return []
        removed_set = set(self.selected_target_ids)
        removed = self.selected_target_ids[:]
        self.target_entries = [
            e for e in self.target_entries if e.id not in removed_set
        ]
        self.selected_target_ids = []
        return removed

    def clear_target(self) -> int:
        """Target を全クリアし、削除件数を返す。"""
        count = len(self.target_entries)
        self.target_entries = []
        self.selected_target_ids = []
        return count

    def move_selected_target_up(self) -> bool:
        """選択 Target エントリ群を 1 つ上へ移動する。"""
        if not self.selected_target_ids:
            return False
        selected = set(self.selected_target_ids)
        entries = self.target_entries
        moved = False
        for i in range(1, len(entries)):
            if entries[i].id in selected and entries[i - 1].id not in selected:
                entries[i - 1], entries[i] = entries[i], entries[i - 1]
                moved = True
        return moved

    def move_selected_target_down(self) -> bool:
        """選択 Target エントリ群を 1 つ下へ移動する。"""
        if not self.selected_target_ids:
            return False
        selected = set(self.selected_target_ids)
        entries = self.target_entries
        moved = False
        for i in range(len(entries) - 2, -1, -1):
            if entries[i].id in selected and entries[i + 1].id not in selected:
                entries[i], entries[i + 1] = entries[i + 1], entries[i]
                moved = True
        return moved

    def reorder_target(self, ordered_ids: list[str]) -> bool:
        """Target の並び順を外部指定の ID 順に置き換える。"""
        if len(ordered_ids) != len(self.target_entries):
            return False
        current_ids = {e.id for e in self.target_entries}
        if set(ordered_ids) != current_ids:
            return False
        id_to_entry = {e.id: e for e in self.target_entries}
        self.target_entries = [id_to_entry[tid] for tid in ordered_ids]
        # 選択の存在整合を保つ
        self.set_selected_target_ids(self.selected_target_ids)
        return True

    # ── ズーム ───────────────────────────────────────────

    def zoom_in_source(self) -> int:
        self.source_zoom_percent = min(ZOOM_MAX, self.source_zoom_percent + ZOOM_STEP)
        return self.source_zoom_percent

    def zoom_out_source(self) -> int:
        self.source_zoom_percent = max(ZOOM_MIN, self.source_zoom_percent - ZOOM_STEP)
        return self.source_zoom_percent

    def reset_source_zoom(self) -> int:
        self.source_zoom_percent = ZOOM_DEFAULT
        return self.source_zoom_percent

    def zoom_in_target(self) -> int:
        self.target_zoom_percent = min(ZOOM_MAX, self.target_zoom_percent + ZOOM_STEP)
        return self.target_zoom_percent

    def zoom_out_target(self) -> int:
        self.target_zoom_percent = max(ZOOM_MIN, self.target_zoom_percent - ZOOM_STEP)
        return self.target_zoom_percent

    def reset_target_zoom(self) -> int:
        self.target_zoom_percent = ZOOM_DEFAULT
        return self.target_zoom_percent

    # ── 出力 / 実行制御 ─────────────────────────────────

    def set_output_path(self, path: str | None) -> None:
        self.output_path = _normalize_path(path) if path else None

    def has_active_session(self) -> bool:
        return bool(self.source_documents or self.target_entries or self.output_path)

    def can_execute(self) -> bool:
        return bool(self.target_entries) and bool(self.output_path) and not self.is_running

    def begin_execution(self) -> None:
        self.is_running = True
        self.cancel_requested = False

    def finish_execution(self) -> None:
        self.is_running = False

    def request_cancel(self) -> None:
        self.cancel_requested = True
