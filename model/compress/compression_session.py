from __future__ import annotations

"""バッチ PDF 圧縮の純粋な状態コンテナ。

このクラスにはスレッド処理、ファイル探索、UI ロジックを持ち込まない。状態モデルを
純粋に保つことでテストしやすくなり、将来 Presenter 側がオーケストレーションを担う際も
同じ検証ルールを重複実装せずに済む。
"""

import re
from dataclasses import dataclass
from pathlib import Path

from model.compress.settings import (
    PDF_ALLOWED_ENGINES,
    PDF_ALLOWED_MODES,
    PDF_COMPRESSION_ENGINE_NATIVE,
    PDF_GHOSTSCRIPT_CUSTOM_DPI_DEFAULT,
    PDF_GHOSTSCRIPT_POSTPROCESS_DEFAULT,
    PDF_GHOSTSCRIPT_PRESETS,
    PDF_GHOSTSCRIPT_PRESET_CUSTOM,
    PDF_GHOSTSCRIPT_PRESET_DEFAULT,
    PDF_LOSSLESS_OPTIONS_DEFAULT,
    PDF_LOSSY_DPI_DEFAULT,
    PDF_LOSSY_JPEG_QUALITY_DEFAULT,
    PDF_LOSSY_PNG_QUALITY_DEFAULT,
    PNGQUANT_DEFAULT_SPEED,
)
from model.external_tools import is_ghostscript_available


@dataclass(frozen=True, slots=True)
class CompressionCandidate:
    """探索過程で見つかった 1 件の圧縮対象。

    ディスク上の PDF と ZIP 内 PDF を同じ後段パイプラインへ流せるように、
    必要最小限の出自情報だけを保持する。
    """
    preferred_filename: str
    source_type: str
    source_label: str
    source_path: str | None = None
    source_bytes: bytes | None = None
    archive_path: str | None = None
    archive_member: str | None = None


@dataclass(frozen=True, slots=True)
class CompressionJob:
    """候補と、その候補に対して確定した出力先パスの組。

    探索結果と最終ジョブ生成を分けるのは、出力名衝突を正しく解決するには全候補が
    出揃ってから判断する必要があるためである。
    """
    candidate: CompressionCandidate
    output_path: str


class CompressionSession:
    """バッチ入力、圧縮設定、進捗カウンタを保持する。

    セッションをバッチ状態の単一の真実源にすることで、Presenter やバックグラウンド
    ワーカー側のコードを薄く保ち、設定が層ごとに分裂するのを防ぐ。
    """
    RESERVED_FILENAMES: frozenset[str] = frozenset({
        "con", "prn", "aux", "nul",
        "com1", "com2", "com3", "com4", "com5", "com6", "com7", "com8", "com9",
        "lpt1", "lpt2", "lpt3", "lpt4", "lpt5", "lpt6", "lpt7", "lpt8", "lpt9",
    })

    def __init__(self) -> None:
        # 入力は Path ではなく正規化済み文字列で保持する。将来的に Qt モデルや
        # ワーカーメッセージへ流す際、Path より扱いやすいためである。
        self.input_paths: list[str] = []
        self.output_dir: str | None = None
        self.engine = PDF_COMPRESSION_ENGINE_NATIVE
        self.mode = "both"
        self.lossy_dpi = PDF_LOSSY_DPI_DEFAULT
        self.jpeg_quality = PDF_LOSSY_JPEG_QUALITY_DEFAULT
        self.png_quality = PDF_LOSSY_PNG_QUALITY_DEFAULT
        self.pngquant_speed = PNGQUANT_DEFAULT_SPEED
        self.lossless_options: dict[str, bool] = dict(PDF_LOSSLESS_OPTIONS_DEFAULT)
        self.ghostscript_preset = PDF_GHOSTSCRIPT_PRESET_DEFAULT
        self.ghostscript_custom_dpi = PDF_GHOSTSCRIPT_CUSTOM_DPI_DEFAULT
        self.ghostscript_use_pikepdf_postprocess = PDF_GHOSTSCRIPT_POSTPROCESS_DEFAULT
        self.ghostscript_available = is_ghostscript_available()
        self.collision_policy = "numbering"

        self.total_items = 0
        self.processed_items = 0
        self.success_count = 0
        self.failure_count = 0
        self.skip_count = 0

    def add_input(self, path: str) -> None:
        """ユーザーが選択した入力パスを 1 件登録する。"""
        self.input_paths.append(str(Path(path)))

    def add_inputs(self, paths: list[str]) -> None:
        """複数入力を順序を保ったまま登録する。

        順序を保つのは、生成される出力一覧や処理対象の見え方をユーザーにとって予測可能に
        するためである。
        """
        for path in paths:
            self.add_input(path)

    def remove_input(self, path: str) -> bool:
        """登録済み入力があれば削除する。"""
        normalized = str(Path(path))
        if normalized not in self.input_paths:
            return False
        self.input_paths.remove(normalized)
        return True

    def clear_inputs(self) -> None:
        """選択済み入力をすべてクリアする。"""
        self.input_paths = []

    def set_output_dir(self, output_dir: str) -> None:
        """選択された出力先フォルダを正規化済み文字列として保持する。"""
        self.output_dir = str(Path(output_dir))

    def set_mode(self, mode: str) -> None:
        """対応済みモードかを検証したうえで圧縮モードを設定する。"""
        if mode not in PDF_ALLOWED_MODES:
            raise ValueError(f"Unsupported mode: {mode}")
        self.mode = mode

    def set_engine(self, engine: str) -> None:
        """圧縮エンジンを設定する。"""
        if engine not in PDF_ALLOWED_ENGINES:
            raise ValueError(f"Unsupported compression engine: {engine}")
        self.engine = engine

    def set_lossy_dpi(self, dpi: int) -> None:
        """非可逆圧縮時の目標 DPI を設定する。

        0 以下の DPI はリサンプリング条件として意味を持たないため、状態層で早めに弾く。
        """
        if dpi <= 0:
            raise ValueError("DPI must be positive")
        self.lossy_dpi = dpi

    def set_jpeg_quality(self, quality: int) -> None:
        """JPEG 品質を 0-100 の共通スケールで設定する。"""
        if not 0 <= quality <= 100:
            raise ValueError("JPEG quality must be between 0 and 100")
        self.jpeg_quality = quality

    def set_png_quality(self, quality: int) -> None:
        """PNG 品質を UI と同じ 0-100 スケールで設定する。"""
        if not 0 <= quality <= 100:
            raise ValueError("PNG quality must be between 0 and 100")
        self.png_quality = quality

    def set_pngquant_speed(self, speed: int) -> None:
        """pngquant の speed を本来の 1-11 範囲で設定する。"""
        if not 1 <= speed <= 11:
            raise ValueError("pngquant speed must be between 1 and 11")
        self.pngquant_speed = speed

    def set_ghostscript_preset(self, preset: str) -> None:
        """Ghostscript プリセットを設定する。"""
        if preset not in PDF_GHOSTSCRIPT_PRESETS:
            raise ValueError(f"Unsupported Ghostscript preset: {preset}")
        self.ghostscript_preset = preset

    def set_ghostscript_custom_dpi(self, dpi: int) -> None:
        """Ghostscript カスタム DPI を設定する。"""
        if dpi <= 0:
            raise ValueError("Ghostscript DPI must be positive")
        self.ghostscript_custom_dpi = dpi

    def set_ghostscript_postprocess_enabled(self, enabled: bool) -> None:
        """Ghostscript 後段の pikepdf 実行有無を設定する。"""
        self.ghostscript_use_pikepdf_postprocess = bool(enabled)

    def refresh_external_tool_state(self) -> None:
        """外部ツール利用可否を再取得する。"""
        self.ghostscript_available = is_ghostscript_available()

    @property
    def ghostscript_uses_custom_dpi(self) -> bool:
        """現在の Ghostscript 設定がカスタム DPI 入力を使うかを返す。"""
        return self.ghostscript_preset == PDF_GHOSTSCRIPT_PRESET_CUSTOM

    def update_lossless_options(self, **options: bool) -> None:
        """pikepdf に対応するブール設定を更新する。

        未知のキーをここで拒否するのは、Presenter 側が効かない設定を静かに作ってしまうのを
        防ぐためである。
        """
        for key, value in options.items():
            if key not in self.lossless_options:
                raise KeyError(key)
            self.lossless_options[key] = bool(value)

    def begin_batch(self, total_items: int) -> None:
        """新しいバッチ開始に向けて進捗カウンタを初期化する。"""
        self.total_items = max(0, total_items)
        self.processed_items = 0
        self.success_count = 0
        self.failure_count = 0
        self.skip_count = 0

    def record_success(self) -> None:
        """成功 1 件を記録する。"""
        self.processed_items += 1
        self.success_count += 1

    def record_failure(self) -> None:
        """失敗 1 件を記録する。"""
        self.processed_items += 1
        self.failure_count += 1

    def record_skip(self) -> None:
        """スキップ 1 件を記録する。

        スキップもユーザーに見える進捗へ含めないと、無効入力に遭遇したとき進捗表示が
        止まって見えてしまうため、処理済み件数へ加算する。
        """
        self.processed_items += 1
        self.skip_count += 1

    @property
    def progress_percent(self) -> int:
        """現在バッチの整数パーセント進捗を返す。"""
        if self.total_items <= 0:
            return 100
        return int((self.processed_items / self.total_items) * 100)

    def progress_snapshot(self) -> dict[str, int]:
        """キューメッセージに載せやすい進捗スナップショットを返す。"""
        return {
            "total_items": self.total_items,
            "processed_items": self.processed_items,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "skip_count": self.skip_count,
            "progress_percent": self.progress_percent,
        }

    def collect_batch_jobs(self, candidates: list[CompressionCandidate]) -> list[CompressionJob]:
        """候補一覧を、衝突回避済みの出力ジョブへ変換する。

        出力パス解決を状態層に置くのは、ワーカーと将来の Presenter の両方が同じ命名規則に
        依存できるようにするためである。
        """
        if self.output_dir is None:
            raise ValueError("Output directory is not set")

        output_dir = Path(self.output_dir)
        reserved_paths: set[str] = set()
        jobs: list[CompressionJob] = []
        for candidate in candidates:
            output_path = self._ensure_unique_output_path(
                output_dir,
                candidate.preferred_filename,
                reserved_paths,
            )
            reserved_paths.add(str(output_path).lower())
            jobs.append(CompressionJob(candidate=candidate, output_path=str(output_path)))
        return jobs

    @classmethod
    def _sanitize_filename(cls, filename: str) -> str:
        """ユーザー向けファイル名を安全な出力ファイル名へ正規化する。

        Windows の予約名や禁止文字をここで処理するのは、ZIP 内ファイル名やユーザー入力名が
        別文脈では有効でも、出力先ファイルシステムでは無効な場合があるためである。
        """
        trimmed = filename.strip() or "compressed.pdf"
        safe_name = re.sub(r'[\\/*?:"<>|]', "_", trimmed)
        base_name = Path(safe_name).name
        stem = Path(base_name).stem.strip(" ._") or "compressed"
        suffix = Path(base_name).suffix.lower() or ".pdf"

        if stem.lower() in cls.RESERVED_FILENAMES:
            stem = f"{stem}_file"

        return f"{stem}{suffix}"

    @classmethod
    def _ensure_unique_output_path(
        cls,
        output_dir: Path,
        preferred_filename: str,
        reserved_paths: set[str],
    ) -> Path:
        """連番サフィックスで衝突しない出力パスを返す。

        実ファイルだけでなくメモリ上の予約済みパスも見るのは、1 回のバッチ内でまだ保存前の
        ジョブ同士が衝突する可能性があるためである。
        """
        safe_filename = cls._sanitize_filename(preferred_filename)
        target_path = output_dir / safe_filename
        stem = target_path.stem
        suffix = target_path.suffix
        counter = 1

        while str(target_path).lower() in reserved_paths or target_path.exists():
            target_path = output_dir / f"{stem} ({counter}){suffix}"
            counter += 1

        return target_path