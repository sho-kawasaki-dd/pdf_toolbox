"""PDF 結合画面の一覧操作と基本状態を管理する。"""

from __future__ import annotations

from pathlib import Path


class MergeSession:
    """PDF 結合機能の UI 非依存状態を保持する。"""

    def __init__(self) -> None:
        self.input_paths: list[str] = []
        self.selected_paths: list[str] = []
        self.output_path: str | None = None
        self.is_running: bool = False
        self.cancel_requested: bool = False

    def add_inputs(self, paths: list[str]) -> list[str]:
        """重複を除いた入力を末尾へ追加し、追加できたパスだけを返す。"""
        existing = {Path(path).as_posix().casefold() for path in self.input_paths}
        accepted: list[str] = []

        for raw_path in paths:
            normalized = str(Path(raw_path))
            key = Path(normalized).as_posix().casefold()
            if key in existing:
                continue
            self.input_paths.append(normalized)
            accepted.append(normalized)
            existing.add(key)

        return accepted

    def set_selected_paths(self, paths: list[str]) -> None:
        """現在一覧に存在する選択だけを保持する。"""
        selected = {Path(path).as_posix().casefold() for path in paths}
        self.selected_paths = [
            path for path in self.input_paths if Path(path).as_posix().casefold() in selected
        ]

    def remove_selected_inputs(self) -> list[str]:
        """選択中入力を削除し、削除したパスを返す。"""
        removed = self.selected_paths[:]
        if not removed:
            return []

        selected = {Path(path).as_posix().casefold() for path in self.selected_paths}
        self.input_paths = [
            path for path in self.input_paths if Path(path).as_posix().casefold() not in selected
        ]
        self.selected_paths = []
        return removed

    def reorder_inputs(self, ordered_paths: list[str]) -> bool:
        """一覧全体の順序を外部指定順へ置き換える。"""
        current_keys = [Path(path).as_posix().casefold() for path in self.input_paths]
        ordered_keys = [Path(path).as_posix().casefold() for path in ordered_paths]
        if len(ordered_keys) != len(current_keys):
            return False
        if sorted(ordered_keys) != sorted(current_keys):
            return False

        self.input_paths = [str(Path(path)) for path in ordered_paths]
        self.set_selected_paths(self.selected_paths)
        return True

    def move_selected_up(self) -> bool:
        """選択ブロックを相対順序を保ったまま 1 つ上へ移動する。"""
        if not self.selected_paths:
            return False

        selected = {Path(path).as_posix().casefold() for path in self.selected_paths}
        moved = False
        for index in range(1, len(self.input_paths)):
            current_key = Path(self.input_paths[index]).as_posix().casefold()
            prev_key = Path(self.input_paths[index - 1]).as_posix().casefold()
            if current_key in selected and prev_key not in selected:
                self.input_paths[index - 1], self.input_paths[index] = (
                    self.input_paths[index],
                    self.input_paths[index - 1],
                )
                moved = True

        if moved:
            self.set_selected_paths(self.selected_paths)
        return moved

    def move_selected_down(self) -> bool:
        """選択ブロックを相対順序を保ったまま 1 つ下へ移動する。"""
        if not self.selected_paths:
            return False

        selected = {Path(path).as_posix().casefold() for path in self.selected_paths}
        moved = False
        for index in range(len(self.input_paths) - 2, -1, -1):
            current_key = Path(self.input_paths[index]).as_posix().casefold()
            next_key = Path(self.input_paths[index + 1]).as_posix().casefold()
            if current_key in selected and next_key not in selected:
                self.input_paths[index], self.input_paths[index + 1] = (
                    self.input_paths[index + 1],
                    self.input_paths[index],
                )
                moved = True

        if moved:
            self.set_selected_paths(self.selected_paths)
        return moved

    def set_output_path(self, path: str | None) -> None:
        """出力先ファイルを設定する。"""
        self.output_path = str(Path(path)) if path else None

    def has_active_session(self) -> bool:
        """入力または保存先が設定されていれば作業中セッションとみなす。"""
        return bool(self.input_paths or self.output_path)

    def begin_execution(self) -> None:
        """将来の Processor 実装向けに実行中状態へ遷移する。"""
        self.is_running = True
        self.cancel_requested = False

    def finish_execution(self) -> None:
        """実行中状態を解除する。"""
        self.is_running = False

    def request_cancel(self) -> None:
        """将来の Processor 実装向けにキャンセル要求を記録する。"""
        self.cancel_requested = True