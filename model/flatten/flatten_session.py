from __future__ import annotations

"""PDF フラット化の純粋な状態コンテナ。"""

from dataclasses import dataclass, field
from pathlib import Path

from model.compress.settings import (
    PDF_GHOSTSCRIPT_POSTPROCESS_DEFAULT,
    PDF_GHOSTSCRIPT_PRESETS,
    PDF_GHOSTSCRIPT_PRESET_DEFAULT,
    PDF_LOSSLESS_OPTIONS_DEFAULT,
)
from model.external_tools import is_ghostscript_available


WINDOWS_MAX_PATH = 260
PREVIEW_TEMP_TOKEN = "0" * 32


@dataclass(frozen=True, slots=True)
class FlattenCandidate:
    """探索で見つかった 1 件の元 PDF。"""

    source_path: str
    source_label: str


@dataclass(frozen=True, slots=True)
class FlattenJob:
    """実行対象 PDF と確定済み出力先の組。"""

    candidate: FlattenCandidate
    output_path: str
    allow_overwrite: bool = False


@dataclass(frozen=True, slots=True)
class FlattenConflict:
    """既存出力ファイルとの衝突情報。"""

    source_path: str
    output_path: str


@dataclass(slots=True)
class FlattenBatchPlan:
    """実行前に確定したジョブと事前検出結果。"""

    jobs: list[FlattenJob] = field(default_factory=list)
    conflicts: list[FlattenConflict] = field(default_factory=list)
    preflight_issues: list[dict[str, object]] = field(default_factory=list)


class FlattenSession:
    """入力一覧、進捗、命名規則を保持する。"""

    def __init__(self) -> None:
        self.input_paths: list[str] = []
        self.post_compression_enabled = False
        self.ghostscript_preset = PDF_GHOSTSCRIPT_PRESET_DEFAULT
        self.post_compression_use_pikepdf = PDF_GHOSTSCRIPT_POSTPROCESS_DEFAULT
        self.ghostscript_available = is_ghostscript_available()

        self.total_items = 0
        self.processed_items = 0
        self.success_count = 0
        self.warning_count = 0
        self.failure_count = 0
        self.skip_count = 0

    def add_input(self, path: str) -> None:
        self.input_paths.append(str(Path(path)))

    def add_inputs(self, paths: list[str]) -> None:
        for path in paths:
            self.add_input(path)

    def remove_input(self, path: str) -> bool:
        normalized = str(Path(path))
        if normalized not in self.input_paths:
            return False
        self.input_paths.remove(normalized)
        return True

    def clear_inputs(self) -> None:
        self.input_paths = []

    def begin_batch(self, total_items: int) -> None:
        self.total_items = max(0, total_items)
        self.processed_items = 0
        self.success_count = 0
        self.warning_count = 0
        self.failure_count = 0
        self.skip_count = 0

    def set_post_compression_enabled(self, enabled: bool) -> None:
        self.post_compression_enabled = bool(enabled) and self.ghostscript_available

    def set_ghostscript_preset(self, preset: str) -> None:
        if preset not in PDF_GHOSTSCRIPT_PRESETS:
            raise ValueError(f"Unsupported Ghostscript preset: {preset}")
        self.ghostscript_preset = preset

    def set_post_compression_use_pikepdf(self, enabled: bool) -> None:
        self.post_compression_use_pikepdf = bool(enabled)

    def refresh_external_tool_state(self) -> None:
        self.ghostscript_available = is_ghostscript_available()
        if not self.ghostscript_available:
            self.post_compression_enabled = False

    def build_post_compression_lossless_options(self) -> dict[str, bool]:
        return dict(PDF_LOSSLESS_OPTIONS_DEFAULT)

    def record_success(self) -> None:
        self.processed_items += 1
        self.success_count += 1

    def record_warning(self) -> None:
        self.processed_items += 1
        self.warning_count += 1

    def record_failure(self) -> None:
        self.processed_items += 1
        self.failure_count += 1

    def record_skip(self) -> None:
        self.processed_items += 1
        self.skip_count += 1

    @property
    def progress_percent(self) -> int:
        if self.total_items <= 0:
            return 100
        return int((self.processed_items / self.total_items) * 100)

    def progress_snapshot(self) -> dict[str, int]:
        return {
            "total_items": self.total_items,
            "processed_items": self.processed_items,
            "success_count": self.success_count,
            "warning_count": self.warning_count,
            "failure_count": self.failure_count,
            "skip_count": self.skip_count,
            "progress_percent": self.progress_percent,
        }

    def build_output_path(self, source_path: str) -> str:
        source = Path(source_path)
        return str(source.with_name(f"{source.stem}_flattened.pdf"))

    def build_temp_output_path(self, output_path: str, token: str) -> str:
        output = Path(output_path)
        return str(output.with_name(f".{output.stem}.flattening-{token}.pdf"))

    def build_post_compression_temp_output_path(self, output_path: str, token: str) -> str:
        output = Path(output_path)
        return str(output.with_name(f".{output.stem}.flatten-compress-{token}.pdf"))

    def validate_windows_path_limit(self, path: str) -> None:
        normalized = str(Path(path))
        if len(normalized) >= WINDOWS_MAX_PATH:
            raise ValueError(f"Windows path exceeds MAX_PATH: {normalized}")