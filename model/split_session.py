"""分割点・セクション・ページナビゲーション・ズームの状態管理。

UIに一切依存しない純粋なPythonクラス。
"""

from __future__ import annotations

import re


class SplitSession:
    """1つのPDFに対する分割セッションの状態をすべて保持する。"""

    ZOOM_MIN = 0.5
    ZOOM_MAX = 3.0
    ZOOM_STEP = 0.1
    ZOOM_DEFAULT = 1.0

    RESERVED_FILENAMES: frozenset[str] = frozenset({
        "con", "prn", "aux", "nul",
        "com1", "com2", "com3", "com4", "com5", "com6", "com7", "com8", "com9",
        "lpt1", "lpt2", "lpt3", "lpt4", "lpt5", "lpt6", "lpt7", "lpt8", "lpt9",
    })

    # ------------------------------------------------------------------
    # 初期化 / リセット
    # ------------------------------------------------------------------

    def __init__(self) -> None:
        self.total_pages: int = 0
        self.current_page_idx: int = 0
        self.split_points: list[int] = []
        self.sections_data: list[dict] = []
        self.preview_zoom: float = self.ZOOM_DEFAULT

    def reset(self, total_pages: int) -> None:
        """新しいドキュメント用にセッションを初期化する。"""
        self.total_pages = total_pages
        self.current_page_idx = 0
        self.split_points = []
        self.sections_data = []
        self.preview_zoom = self.ZOOM_DEFAULT
        self._rebuild_sections_data()

    # ------------------------------------------------------------------
    # セクションデータ管理
    # ------------------------------------------------------------------

    def _rebuild_sections_data(self) -> None:
        """分割点から sections_data を再構築する。

        開始ページをキーにして、ユーザーが手入力したカスタムファイル名を引き継ぐ。
        """
        if self.total_pages <= 0:
            self.sections_data = []
            return

        # 旧データを開始ページで索引化 (カスタム名の引き継ぎ用)
        old_by_start: dict[int, dict] = {}
        for sec in self.sections_data:
            old_by_start[sec["start"]] = sec

        points = [0] + sorted(self.split_points) + [self.total_pages]
        new_data: list[dict] = []
        for i in range(len(points) - 1):
            start = points[i]
            end = points[i + 1] - 1
            default_name = f"output_part{i + 1}.pdf"

            old = old_by_start.get(start)
            if old and old.get("is_custom_name"):
                filename = old["filename"]
                is_custom = True
            else:
                filename = default_name
                is_custom = False

            new_data.append(
                {
                    "start": start,
                    "end": end,
                    "filename": filename,
                    "is_custom_name": is_custom,
                }
            )

        self.sections_data = new_data

    def get_active_section_index(self) -> int:
        """現在表示中のページが属するセクションのインデックスを返す。"""
        for i, sec in enumerate(self.sections_data):
            if sec["start"] <= self.current_page_idx <= sec["end"]:
                return i
        return 0 if self.sections_data else -1

    def save_section_filename(self, section_idx: int, text: str) -> None:
        """テキスト入力をサニタイズしてセクションのファイル名に反映する。"""
        if section_idx < 0 or section_idx >= len(self.sections_data):
            return

        sec = self.sections_data[section_idx]
        default_name = f"output_part{section_idx + 1}.pdf"

        sanitized = re.sub(r'[\\/*?:"<>|]', "_", text.strip())
        sanitized = re.sub(r"\s+", " ", sanitized).strip()
        if sanitized.lower().endswith(".pdf"):
            sanitized = sanitized[:-4]
        sanitized = sanitized.strip(" ._")
        sanitized = re.sub(r"_+", "_", sanitized)

        is_invalid = (
            not sanitized
            or sanitized.lower() in self.RESERVED_FILENAMES
            or re.fullmatch(r"_+", sanitized) is not None
        )

        if is_invalid:
            sec["filename"] = default_name
            sec["is_custom_name"] = False
            return

        candidate = f"{sanitized}.pdf"
        if candidate == default_name:
            sec["filename"] = default_name
            sec["is_custom_name"] = False
        else:
            sec["filename"] = candidate
            sec["is_custom_name"] = True

    # ------------------------------------------------------------------
    # 分割点操作
    # ------------------------------------------------------------------

    def add_split_point(self) -> bool:
        """現在のページに分割点を追加する。追加できたら True を返す。"""
        if self.total_pages <= 0:
            return False
        if self.current_page_idx > 0 and self.current_page_idx not in self.split_points:
            self.split_points.append(self.current_page_idx)
            self.split_points.sort()
            self._rebuild_sections_data()
            return True
        return False

    def remove_split_point(self) -> bool:
        """現在のページの分割点を消去する。消去できたら True を返す。"""
        if self.total_pages <= 0:
            return False
        if self.current_page_idx in self.split_points:
            self.split_points.remove(self.current_page_idx)
            self._rebuild_sections_data()
            return True
        return False

    def remove_split_point_at(self, page_idx: int) -> bool:
        """指定ページの分割点を消去する。消去できたら True を返す。"""
        if page_idx in self.split_points:
            self.split_points.remove(page_idx)
            self._rebuild_sections_data()
            return True
        return False

    def clear_split_points(self) -> None:
        """すべての分割点をリセットする。"""
        self.split_points = []
        self._rebuild_sections_data()

    def split_every_page(self) -> None:
        """全ページに分割点を一括設定する。"""
        if self.total_pages <= 1:
            self.split_points = []
        else:
            self.split_points = list(range(1, self.total_pages))
        self._rebuild_sections_data()

    def remove_active_section_split_point(self) -> bool:
        """アクティブセクションの開始分割点を消去する。"""
        idx = self.get_active_section_index()
        if idx <= 0 or idx >= len(self.sections_data):
            return False
        split_point = self.sections_data[idx]["start"]
        return self.remove_split_point_at(split_point)

    # ------------------------------------------------------------------
    # ページナビゲーション
    # ------------------------------------------------------------------

    def go_to_page(self, page_idx: int) -> bool:
        """指定ページに移動する。移動できたら True を返す。"""
        if self.total_pages <= 0:
            return False
        if 0 <= page_idx < self.total_pages and page_idx != self.current_page_idx:
            self.current_page_idx = page_idx
            return True
        return False

    def prev_page(self) -> bool:
        if self.current_page_idx > 0:
            self.current_page_idx -= 1
            return True
        return False

    def next_page(self) -> bool:
        if self.current_page_idx < self.total_pages - 1:
            self.current_page_idx += 1
            return True
        return False

    def prev_10_pages(self) -> bool:
        if self.current_page_idx > 0:
            self.current_page_idx = max(0, self.current_page_idx - 10)
            return True
        return False

    def next_10_pages(self) -> bool:
        if self.current_page_idx < self.total_pages - 1:
            self.current_page_idx = min(self.total_pages - 1, self.current_page_idx + 10)
            return True
        return False

    # ------------------------------------------------------------------
    # セクション間ナビゲーション
    # ------------------------------------------------------------------

    def prev_section(self) -> bool:
        """前のセクションの先頭ページに移動する。"""
        idx = self.get_active_section_index()
        if idx > 0:
            self.current_page_idx = self.sections_data[idx - 1]["start"]
            return True
        return False

    def next_section(self) -> bool:
        """次のセクションの先頭ページに移動する。"""
        idx = self.get_active_section_index()
        if idx < len(self.sections_data) - 1:
            self.current_page_idx = self.sections_data[idx + 1]["start"]
            return True
        return False

    # ------------------------------------------------------------------
    # ズーム
    # ------------------------------------------------------------------

    def set_zoom(self, value: float) -> bool:
        """ズーム倍率を設定する。変化したら True を返す。"""
        clamped = max(self.ZOOM_MIN, min(self.ZOOM_MAX, value))
        snapped = round(clamped, 2)
        if snapped == self.preview_zoom:
            return False
        self.preview_zoom = snapped
        return True

    def zoom_in(self) -> bool:
        return self.set_zoom(self.preview_zoom + self.ZOOM_STEP)

    def zoom_out(self) -> bool:
        return self.set_zoom(self.preview_zoom - self.ZOOM_STEP)

    def reset_zoom(self) -> bool:
        return self.set_zoom(self.ZOOM_DEFAULT)

    @property
    def zoom_percent(self) -> int:
        return int(self.preview_zoom * 100)

    # ------------------------------------------------------------------
    # 分割ジョブ生成
    # ------------------------------------------------------------------

    def collect_split_jobs(self) -> list[dict]:
        """データモデル (sections_data) から分割ジョブ記述子を生成する。"""
        jobs: list[dict] = []
        for i, sec in enumerate(self.sections_data):
            filename = sec["filename"].strip()
            if not filename:
                filename = f"output_part{i + 1}.pdf"
            if not filename.lower().endswith(".pdf"):
                filename += ".pdf"
            jobs.append(
                {
                    "index": i + 1,
                    "start": sec["start"],
                    "end": sec["end"],
                    "filename": filename,
                }
            )
        return jobs
