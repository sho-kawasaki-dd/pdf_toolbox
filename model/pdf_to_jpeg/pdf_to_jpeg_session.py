from __future__ import annotations

"""PDF から JPEG への書き出し状態を保持するセッション。"""

import re
from dataclasses import dataclass
from pathlib import Path


DEFAULT_JPEG_QUALITY = 90


@dataclass(frozen=True, slots=True)
class PdfToJpegExportJob:
    """1 ページ分の書き出しジョブ定義。"""

    page_index: int
    page_number: int
    output_path: str


class PdfToJpegSession:
    """PDF→JPEG 変換に必要な設定と進捗を保持する。"""

    RESERVED_FILENAMES: frozenset[str] = frozenset({
        "con", "prn", "aux", "nul",
        "com1", "com2", "com3", "com4", "com5", "com6", "com7", "com8", "com9",
        "lpt1", "lpt2", "lpt3", "lpt4", "lpt5", "lpt6", "lpt7", "lpt8", "lpt9",
    })

    def __init__(self) -> None:
        self.input_pdf_path: str | None = None
        self.output_dir: str | None = None
        self.jpeg_quality = DEFAULT_JPEG_QUALITY

        self.total_pages = 0
        self.processed_pages = 0
        self.success_count = 0
        self.failure_count = 0
        self.current_page_number = 0

    def set_input_pdf(self, path: str | None) -> None:
        """変換対象の単一 PDF を設定する。"""
        self.input_pdf_path = str(Path(path)) if path else None

    def set_output_dir(self, path: str | None) -> None:
        """ユーザー指定の出力ルートフォルダを設定する。"""
        self.output_dir = str(Path(path)) if path else None

    def set_jpeg_quality(self, quality: int) -> None:
        """JPEG 品質を 0-100 の共通スケールで設定する。"""
        if not 0 <= quality <= 100:
            raise ValueError("JPEG quality must be between 0 and 100")
        self.jpeg_quality = quality

    @property
    def output_subfolder_name(self) -> str | None:
        """出力を格納する PDF 名サブフォルダ名を返す。"""
        if self.input_pdf_path is None:
            return None
        return self._sanitize_path_segment(Path(self.input_pdf_path).stem)

    @property
    def output_subfolder_path(self) -> str | None:
        """最終的な JPEG 出力先サブフォルダのパスを返す。"""
        if self.output_dir is None or self.output_subfolder_name is None:
            return None
        return str(Path(self.output_dir) / self.output_subfolder_name)

    def can_execute(self) -> bool:
        """入力 PDF と保存先が揃っていれば実行可能とみなす。"""
        return bool(self.input_pdf_path and self.output_dir)

    def begin_batch(self, total_pages: int) -> None:
        """新しい書き出しバッチ向けに進捗状態を初期化する。"""
        if total_pages < 0:
            raise ValueError("Total pages cannot be negative")

        self.total_pages = total_pages
        self.processed_pages = 0
        self.success_count = 0
        self.failure_count = 0
        self.current_page_number = 0

    def mark_page_started(self, page_number: int) -> None:
        """現在処理中のページ番号を記録する。"""
        if page_number <= 0:
            raise ValueError("Page number must be positive")
        self.current_page_number = page_number

    def record_success(self) -> None:
        """成功 1 ページを記録する。"""
        self.processed_pages += 1
        self.success_count += 1

    def record_failure(self) -> None:
        """失敗 1 ページを記録する。"""
        self.processed_pages += 1
        self.failure_count += 1

    @property
    def progress_percent(self) -> int:
        """現在バッチの整数パーセント進捗を返す。"""
        if self.total_pages <= 0:
            return 100
        return int((self.processed_pages / self.total_pages) * 100)

    def progress_snapshot(self) -> dict[str, int]:
        """キューへ流す進捗情報を辞書で返す。"""
        return {
            "total_pages": self.total_pages,
            "processed_pages": self.processed_pages,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "current_page_number": self.current_page_number,
            "progress_percent": self.progress_percent,
        }

    def build_output_filename(self, page_number: int) -> str:
        """固定命名規則 `PDF名_001.jpg` でファイル名を返す。"""
        if page_number <= 0:
            raise ValueError("Page number must be positive")

        base_name = self.output_subfolder_name
        if base_name is None:
            raise ValueError("Input PDF is not set")
        return f"{base_name}_{page_number:03d}.jpg"

    def collect_export_jobs(self, page_count: int) -> list[PdfToJpegExportJob]:
        """出力先サブフォルダ配下のページ別 JPEG ジョブ一覧を返す。"""
        if not self.can_execute():
            raise ValueError("Input PDF and output directory must be set")
        if page_count < 0:
            raise ValueError("Page count cannot be negative")

        output_subfolder = Path(self.output_subfolder_path or "")
        return [
            PdfToJpegExportJob(
                page_index=page_number - 1,
                page_number=page_number,
                output_path=str(output_subfolder / self.build_output_filename(page_number)),
            )
            for page_number in range(1, page_count + 1)
        ]

    def collect_conflicting_output_paths(self, page_count: int) -> list[str]:
        """既存ファイルと衝突する予定出力パスだけを返す。"""
        conflicts: list[str] = []
        for job in self.collect_export_jobs(page_count):
            if Path(job.output_path).exists():
                conflicts.append(job.output_path)
        return conflicts

    @classmethod
    def _sanitize_path_segment(cls, name: str) -> str:
        """Windows 上でも安全な出力フォルダ名・接頭辞へ正規化する。"""
        trimmed = name.strip() or "output"
        safe_name = re.sub(r'[\\/*?:"<>|]', "_", trimmed)
        safe_name = safe_name.strip(" ._") or "output"
        if safe_name.lower() in cls.RESERVED_FILENAMES:
            safe_name = f"{safe_name}_file"
        return safe_name