from __future__ import annotations

"""PDF 圧縮のバックグラウンド・バッチ処理。

このクラスは探索と並行実行を担当し、状態はセッションが持つ。役割を分けることで、
このクラスは I/O と並行処理に集中でき、可変な進捗状態も 1 か所にまとまってテストしやすい。
"""

import io
import os
import queue
import threading
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import cast

from model.compress.compression_session import (
    CompressionCandidate,
    CompressionJob,
    CompressionSession,
)
from model.compress.native_compressor import CompressionMetrics, compress_pdf, validate_pdf_bytes, validate_pdf_file
from model.compress.settings import ZIP_SCAN_MAX_DEPTH


class CompressionProcessor:
    """圧縮対象の発見、ジョブ化、並行実行をバックグラウンドで行う。"""

    def __init__(self, max_workers: int | None = None) -> None:
        self.is_compressing = False
        self.result_queue: queue.Queue[dict[str, object]] = queue.Queue()
        # ワーカー数を上限付きにするのは、特にデスクトップ環境で CPU を使い切って
        # 逆に操作感を悪化させないためである。圧縮は CPU だけでなくディスクやライブラリ
        # 呼び出しも混ざるため、常に全コア使用が最適とは限らない。
        self._max_workers = max_workers or max(1, min(4, os.cpu_count() or 1))

    def start_compression(self, session: CompressionSession) -> None:
        """未実行時のみ新しい圧縮バッチを開始する。

        二重起動を許すと同じセッション状態を競合更新し、重複出力も生みやすい。
        そのため再入はキューせず無視する。
        """
        if self.is_compressing:
            return

        self._drain_queue()
        self.is_compressing = True
        worker = threading.Thread(
            target=self._compression_worker,
            args=(session,),
            daemon=True,
        )
        worker.start()

    def poll_results(self) -> list[dict[str, object]]:
        """結果キューを読み切り、保留中メッセージをすべて返す。"""
        results: list[dict[str, object]] = []
        while True:
            try:
                results.append(self.result_queue.get_nowait())
            except queue.Empty:
                break
        return results

    def drain_queue(self) -> None:
        """古いメッセージを捨てる公開ヘルパー。"""
        self._drain_queue()

    def _drain_queue(self) -> None:
        """新規処理開始前に使う内部キュー破棄処理。"""
        while True:
            try:
                self.result_queue.get_nowait()
            except queue.Empty:
                break

    def _compression_worker(self, session: CompressionSession) -> None:
        """入力を解決し、ジョブを並行実行し、進捗と結果を通知する。

        探索や圧縮のようなブロッキングし得る処理をワーカースレッドへ寄せることで、
        将来の UI スレッドの応答性を保てるようにしている。
        """
        try:
            candidates, skipped = self._resolve_inputs(session.input_paths)
            jobs = session.collect_batch_jobs(candidates)
            session.begin_batch(len(jobs) + len(skipped))

            for skipped_item in skipped:
                # スキップを個別通知するのは、後で Presenter が「なぜ無視されたか」を
                # ユーザーへ説明できるようにするためである。
                session.record_skip()
                self.result_queue.put(skipped_item)
                self.result_queue.put({"type": "progress", **session.progress_snapshot()})

            if jobs:
                with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
                    futures = {
                        executor.submit(self._compress_job, job, session): job
                        for job in jobs
                    }
                    for future in as_completed(futures):
                        # 長いバッチでは入力順を守ることより、終わったものから進捗が見える方が
                        # 重要なので、完了順で結果を流す。
                        result = future.result()
                        result_type = result.get("type")
                        if result_type == "success":
                            session.record_success()
                        elif result_type == "failure":
                            session.record_failure()
                        else:
                            session.record_skip()

                        self.result_queue.put(result)
                        self.result_queue.put({"type": "progress", **session.progress_snapshot()})

            self.result_queue.put({"type": "finished", **session.progress_snapshot()})
        except Exception as exc:
            self.result_queue.put({"type": "failure", "message": str(exc)})
        finally:
            self.is_compressing = False

    def _resolve_inputs(
        self,
        input_paths: list[str],
    ) -> tuple[list[CompressionCandidate], list[dict[str, object]]]:
        """ユーザー選択入力を具体的な候補一覧とスキップ情報へ展開する。"""
        candidates: list[CompressionCandidate] = []
        skipped: list[dict[str, object]] = []

        for input_path in input_paths:
            self._resolve_path(Path(input_path), candidates, skipped)

        return candidates, skipped

    def _resolve_path(
        self,
        path: Path,
        candidates: list[CompressionCandidate],
        skipped: list[dict[str, object]],
    ) -> None:
        """1 つのパスを解決し、必要ならディレクトリを再帰展開する。

        この機能ではフォルダ入力は明示的に再帰仕様なので、UI ではなくプロセッサ層で
        ディレクトリ展開を担う。
        """
        if not path.exists():
            skipped.append({
                "type": "skipped",
                "item": str(path),
                "reason": "missing input",
            })
            return

        if path.is_dir():
            # `rglob('*')` を使うことで、深い階層の PDF もトップレベルと同じ規則で扱える。
            # ソートしているのは、テスト結果とユーザーへの見え方を決定的にするためである。
            for child in sorted(path.rglob("*")):
                if child.is_dir():
                    continue
                self._resolve_file(child, candidates, skipped)
            return

        self._resolve_file(path, candidates, skipped)

    def _resolve_file(
        self,
        path: Path,
        candidates: list[CompressionCandidate],
        skipped: list[dict[str, object]],
    ) -> None:
        """1 つのファイルを候補またはスキップ情報へ変換する。"""
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            if validate_pdf_file(path):
                candidates.append(
                    CompressionCandidate(
                        preferred_filename=path.name,
                        source_type="file",
                        source_label=str(path),
                        source_path=str(path),
                    )
                )
            else:
                skipped.append({
                    "type": "skipped",
                    "item": str(path),
                    "reason": "invalid pdf",
                })
            return

        if suffix == ".zip":
            # フォルダ再帰経由の ZIP と直接選択された ZIP を同じ規則で扱うため、
            # ZIP 解決はここへ集約する。
            self._scan_zip_path(path, candidates, skipped, depth=1)
            return

        skipped.append({
            "type": "skipped",
            "item": str(path),
            "reason": "non-pdf input",
        })

    def _scan_zip_path(
        self,
        zip_path: Path,
        candidates: list[CompressionCandidate],
        skipped: list[dict[str, object]],
        depth: int,
    ) -> None:
        """ディスク上の ZIP を開き、内部の PDF を走査する。"""
        try:
            with zipfile.ZipFile(zip_path) as archive:
                self._scan_zip_archive(archive, str(zip_path), candidates, skipped, depth)
        except zipfile.BadZipFile:
            skipped.append({
                "type": "skipped",
                "item": str(zip_path),
                "reason": "invalid zip",
            })

    def _scan_zip_archive(
        self,
        archive: zipfile.ZipFile,
        archive_label: str,
        candidates: list[CompressionCandidate],
        skipped: list[dict[str, object]],
        depth: int,
    ) -> None:
        """1 つの ZIP アーカイブを再帰的に走査する。

        ネスト ZIP への対応は要件だが、深さ無制限にすると archive bomb 的な入力や
        意図しない異常ネストに弱くなるため、深さ上限は明示している。
        """
        for info in sorted(archive.infolist(), key=lambda item: item.filename):
            if info.is_dir():
                continue

            member_label = f"{archive_label}!{info.filename}"
            suffix = Path(info.filename).suffix.lower()

            if suffix == ".pdf":
                try:
                    pdf_bytes = archive.read(info.filename)
                except Exception:
                    skipped.append({
                        "type": "skipped",
                        "item": member_label,
                        "reason": "unreadable zip member",
                    })
                    continue

                if not validate_pdf_bytes(pdf_bytes):
                    skipped.append({
                        "type": "skipped",
                        "item": member_label,
                        "reason": "invalid pdf",
                    })
                    continue

                candidates.append(
                    CompressionCandidate(
                        preferred_filename=Path(info.filename).name,
                        source_type="zip_entry",
                        source_label=member_label,
                        source_bytes=pdf_bytes,
                        archive_path=archive_label,
                        archive_member=info.filename,
                    )
                )
                continue

            if suffix == ".zip":
                if depth >= ZIP_SCAN_MAX_DEPTH:
                    # 深さ上限で止めたことを明示的に返すのは、無言で消えるよりも
                    # 「仕様で止めた」と後で説明しやすくするためである。
                    skipped.append({
                        "type": "skipped",
                        "item": member_label,
                        "reason": "zip depth limit exceeded",
                    })
                    continue

                try:
                    nested_bytes = archive.read(info.filename)
                    with zipfile.ZipFile(io.BytesIO(nested_bytes)) as nested_archive:
                        self._scan_zip_archive(
                            nested_archive,
                            member_label,
                            candidates,
                            skipped,
                            depth + 1,
                        )
                except zipfile.BadZipFile:
                    skipped.append({
                        "type": "skipped",
                        "item": member_label,
                        "reason": "invalid zip",
                    })
                continue

            skipped.append({
                "type": "skipped",
                "item": member_label,
                "reason": "non-pdf input",
            })

    def _compress_job(
        self,
        job: CompressionJob,
        session: CompressionSession,
    ) -> dict[str, object]:
        """1 件の圧縮ジョブを実行し、キュー投入可能な結果を返す。"""
        output_path = Path(job.output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        input_bytes = self._get_candidate_size_bytes(job.candidate)

        if job.candidate.source_type == "zip_entry":
            if job.candidate.source_bytes is None:
                return {
                    "type": "skipped",
                    "item": job.candidate.source_label,
                    "reason": "missing zip payload",
                }

            import tempfile

            with tempfile.TemporaryDirectory() as temp_dir:
                # 圧縮エンジンはパス前提ライブラリを使うため、ZIP 内 PDF は一時ファイルへ
                # 実体化してから処理する。スコープを局所化することで長いバッチ中に中間ファイル
                # が残り続けるのを避ける。
                temp_source = Path(temp_dir) / job.candidate.preferred_filename
                temp_source.write_bytes(job.candidate.source_bytes)
                ok, message, metrics = self._normalize_compress_result(
                    compress_pdf(
                        temp_source,
                        output_path,
                        mode=session.mode,
                        target_dpi=session.lossy_dpi,
                        jpeg_quality=session.jpeg_quality,
                        png_quality=session.png_quality,
                        pngquant_speed=session.pngquant_speed,
                        lossless_options=session.lossless_options,
                    ),
                    input_bytes,
                    output_path,
                )
        else:
            if job.candidate.source_path is None:
                return {
                    "type": "skipped",
                    "item": job.candidate.source_label,
                    "reason": "missing source path",
                }

            ok, message, metrics = self._normalize_compress_result(
                compress_pdf(
                    job.candidate.source_path,
                    output_path,
                    mode=session.mode,
                    target_dpi=session.lossy_dpi,
                    jpeg_quality=session.jpeg_quality,
                    png_quality=session.png_quality,
                    pngquant_speed=session.pngquant_speed,
                    lossless_options=session.lossless_options,
                ),
                input_bytes,
                output_path,
            )

        if ok:
            metrics = CompressionMetrics(
                input_bytes=input_bytes,
                lossy_output_bytes=input_bytes if metrics is None else metrics.lossy_output_bytes,
                final_output_bytes=input_bytes if metrics is None else metrics.final_output_bytes,
            )
            return {
                "type": "success",
                "item": job.candidate.source_label,
                "output_path": str(output_path),
                "message": message,
                "input_bytes": metrics.input_bytes,
                "lossy_output_bytes": metrics.lossy_output_bytes,
                "final_output_bytes": metrics.final_output_bytes,
            }

        # 失敗を例外で止めず結果として返すのは、他のジョブを継続させるためである。
        return {
            "type": "failure",
            "item": job.candidate.source_label,
            "output_path": str(output_path),
            "message": message,
        }

    def _get_candidate_size_bytes(self, candidate: CompressionCandidate) -> int:
        """候補の出自に応じて元 PDF のサイズを返す。"""
        if candidate.source_bytes is not None:
            return len(candidate.source_bytes)
        if candidate.source_path is None:
            return 0
        try:
            return Path(candidate.source_path).stat().st_size
        except OSError:
            return 0

    def _normalize_compress_result(
        self,
        result: tuple[bool, str] | tuple[bool, str, CompressionMetrics | None],
        input_bytes: int,
        output_path: Path,
    ) -> tuple[bool, str, CompressionMetrics | None]:
        """旧シグネチャの圧縮関数も受け入れられるようにする。"""
        ok = bool(result[0])
        message = str(result[1])
        metrics = cast(CompressionMetrics | None, result[2]) if len(result) >= 3 else None

        if metrics is None and ok:
            output_bytes = output_path.stat().st_size if output_path.exists() else input_bytes
            metrics = CompressionMetrics(
                input_bytes=input_bytes,
                lossy_output_bytes=output_bytes,
                final_output_bytes=output_bytes,
            )
        return ok, message, metrics