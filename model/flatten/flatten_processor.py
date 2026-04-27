from __future__ import annotations

"""PDF フラット化の探索・事前検出・バックグラウンド実行。"""

import os
import queue
import threading
import uuid
from pathlib import Path

import fitz

from model.compress.ghostscript_compressor import compress_pdf_with_ghostscript
from model.compress.settings import PDF_GHOSTSCRIPT_CUSTOM_DPI_DEFAULT
from model.flatten.flatten_session import (
    PREVIEW_TEMP_TOKEN,
    FlattenBatchPlan,
    FlattenCandidate,
    FlattenConflict,
    FlattenJob,
    FlattenSession,
)


class FlattenCancelledError(Exception):
    """フラット化処理がキャンセルされたことを表す内部例外。"""


class FlattenProcessor:
    """PDF フラット化を逐次バックグラウンド実行する。"""

    def __init__(self) -> None:
        self.is_running = False
        self.result_queue: queue.Queue[dict[str, object]] = queue.Queue()
        self._cancel_event = threading.Event()

    def prepare_batch(self, session: FlattenSession) -> FlattenBatchPlan:
        plan = FlattenBatchPlan()
        for input_path in session.input_paths:
            self._resolve_path(Path(input_path), session, plan)
        return plan

    def start_flatten(self, session: FlattenSession, plan: FlattenBatchPlan) -> None:
        if self.is_running:
            return

        self._drain_queue()
        self._cancel_event.clear()
        self.is_running = True
        worker = threading.Thread(
            target=self._flatten_worker,
            args=(session, plan),
            daemon=True,
        )
        worker.start()

    def request_cancel(self) -> None:
        self._cancel_event.set()

    def poll_results(self) -> list[dict[str, object]]:
        results: list[dict[str, object]] = []
        while True:
            try:
                results.append(self.result_queue.get_nowait())
            except queue.Empty:
                break
        return results

    def drain_queue(self) -> None:
        self._drain_queue()

    def _drain_queue(self) -> None:
        while True:
            try:
                self.result_queue.get_nowait()
            except queue.Empty:
                break

    def _resolve_path(
        self,
        path: Path,
        session: FlattenSession,
        plan: FlattenBatchPlan,
    ) -> None:
        if not path.exists():
            plan.preflight_issues.append({
                "type": "skipped",
                "item": str(path),
                "reason": "missing input",
            })
            return

        if path.is_dir():
            for child in sorted(path.rglob("*")):
                if child.is_dir():
                    continue
                self._resolve_file(child, session, plan)
            return

        self._resolve_file(path, session, plan)

    def _resolve_file(
        self,
        path: Path,
        session: FlattenSession,
        plan: FlattenBatchPlan,
    ) -> None:
        if path.suffix.lower() != ".pdf":
            plan.preflight_issues.append({
                "type": "skipped",
                "item": str(path),
                "reason": "non-pdf input",
            })
            return

        output_path = session.build_output_path(str(path))
        temp_output_path = session.build_temp_output_path(output_path, PREVIEW_TEMP_TOKEN)

        try:
            session.validate_windows_path_limit(output_path)
        except ValueError:
            plan.preflight_issues.append({
                "type": "failure",
                "item": str(path),
                "message": f"出力パスが長すぎるため処理できません: {output_path}",
            })
            return

        try:
            session.validate_windows_path_limit(temp_output_path)
        except ValueError:
            plan.preflight_issues.append({
                "type": "failure",
                "item": str(path),
                "message": f"一時出力パスが長すぎるため処理できません: {temp_output_path}",
            })
            return

        if session.post_compression_enabled:
            compressed_temp_output_path = session.build_post_compression_temp_output_path(
                output_path,
                PREVIEW_TEMP_TOKEN,
            )
            try:
                session.validate_windows_path_limit(compressed_temp_output_path)
            except ValueError:
                plan.preflight_issues.append({
                    "type": "failure",
                    "item": str(path),
                    "message": f"圧縮一時出力パスが長すぎるため処理できません: {compressed_temp_output_path}",
                })
                return

        if Path(output_path).exists():
            plan.conflicts.append(
                FlattenConflict(source_path=str(path), output_path=output_path)
            )
            return

        plan.jobs.append(
            FlattenJob(
                candidate=FlattenCandidate(
                    source_path=str(path),
                    source_label=str(path),
                ),
                output_path=output_path,
            )
        )

    def _flatten_worker(self, session: FlattenSession, plan: FlattenBatchPlan) -> None:
        session.begin_batch(len(plan.jobs) + len(plan.preflight_issues))

        try:
            for issue in plan.preflight_issues:
                if issue.get("type") == "skipped":
                    session.record_skip()
                else:
                    session.record_failure()
                self.result_queue.put(issue)
                self.result_queue.put({"type": "progress", **session.progress_snapshot()})

            for job in plan.jobs:
                self._raise_if_cancelled()
                result = self._flatten_job(session, job)
                result_type = result.get("type")
                if result_type == "success":
                    session.record_success()
                elif result_type == "warning":
                    session.record_warning()
                elif result_type == "skipped":
                    session.record_skip()
                else:
                    session.record_failure()

                self.result_queue.put(result)
                self.result_queue.put({"type": "progress", **session.progress_snapshot()})

            self.result_queue.put({"type": "finished", **session.progress_snapshot()})
        except FlattenCancelledError:
            self.result_queue.put({
                "type": "cancelled",
                **session.progress_snapshot(),
                "message": "PDFフラット化をキャンセルしました。",
            })
        except Exception as exc:
            self.result_queue.put({
                "type": "failure",
                **session.progress_snapshot(),
                "message": str(exc),
            })
        finally:
            self.is_running = False
            self._cancel_event.clear()

    def _flatten_job(
        self,
        session: FlattenSession,
        job: FlattenJob,
    ) -> dict[str, object]:
        output_path = Path(job.output_path)
        temp_output = Path(session.build_temp_output_path(job.output_path, uuid.uuid4().hex))
        compressed_temp_output = Path(
            session.build_post_compression_temp_output_path(job.output_path, uuid.uuid4().hex),
        )
        source_path = Path(job.candidate.source_path)
        document: fitz.Document | None = None

        try:
            session.validate_windows_path_limit(str(output_path))
            session.validate_windows_path_limit(str(temp_output))
            if session.post_compression_enabled:
                session.validate_windows_path_limit(str(compressed_temp_output))

            if output_path.exists() and not job.allow_overwrite:
                return {
                    "type": "failure",
                    "item": job.candidate.source_label,
                    "message": f"既存の出力ファイルがあるため処理できません: {output_path}",
                }

            output_path.parent.mkdir(parents=True, exist_ok=True)
            self._raise_if_cancelled()
            document = self._open_source_pdf(source_path)
            document.bake()
            self._raise_if_cancelled()
            self._save_flattened_pdf(document, temp_output)
            self._raise_if_cancelled()

            if session.post_compression_enabled:
                return self._run_post_compression(
                    session=session,
                    job=job,
                    flattened_temp_output=temp_output,
                    compressed_temp_output=compressed_temp_output,
                    final_output_path=output_path,
                )

            os.replace(temp_output, output_path)
            return {
                "type": "success",
                "item": job.candidate.source_label,
                "output_path": str(output_path),
            }
        except FlattenCancelledError:
            self._cleanup_temp_output(temp_output)
            self._cleanup_temp_output(compressed_temp_output)
            raise
        except PermissionError:
            self._cleanup_temp_output(temp_output)
            self._cleanup_temp_output(compressed_temp_output)
            return {
                "type": "failure",
                "item": job.candidate.source_label,
                "message": "ファイルが他のアプリで開かれています。",
            }
        except OSError as exc:
            self._cleanup_temp_output(temp_output)
            self._cleanup_temp_output(compressed_temp_output)
            return {
                "type": "failure",
                "item": job.candidate.source_label,
                "message": f"保存に失敗しました: {exc}",
            }
        except ValueError as exc:
            self._cleanup_temp_output(temp_output)
            self._cleanup_temp_output(compressed_temp_output)
            return {
                "type": "failure",
                "item": job.candidate.source_label,
                "message": str(exc),
            }
        except Exception as exc:
            self._cleanup_temp_output(temp_output)
            self._cleanup_temp_output(compressed_temp_output)
            return {
                "type": "failure",
                "item": job.candidate.source_label,
                "message": f"flatten 実行に失敗しました: {exc}",
            }
        finally:
            if document is not None:
                document.close()

    def _open_source_pdf(self, input_path: Path) -> fitz.Document:
        if not input_path.exists() or not input_path.is_file():
            raise ValueError(f"入力ファイルが見つかりません: {input_path}")

        if input_path.suffix.lower() != ".pdf":
            raise ValueError(f"PDFではない入力が含まれています: {input_path}")

        try:
            source_doc = fitz.open(str(input_path))
        except fitz.FileDataError:
            raise ValueError(f"不正なPDFのため読み込めませんでした: {input_path}") from None
        except RuntimeError:
            raise ValueError(f"PDFを開けませんでした: {input_path}") from None

        if source_doc.needs_pass or source_doc.is_encrypted:
            source_doc.close()
            raise ValueError(f"暗号化されたPDFのため処理できません: {input_path}")

        if source_doc.page_count <= 0:
            source_doc.close()
            raise ValueError(f"ページを持たないPDFです: {input_path}")

        return source_doc

    def _save_flattened_pdf(self, document: fitz.Document, temp_output: Path) -> None:
        document.save(str(temp_output), garbage=3, deflate=True)

    def _run_post_compression(
        self,
        *,
        session: FlattenSession,
        job: FlattenJob,
        flattened_temp_output: Path,
        compressed_temp_output: Path,
        final_output_path: Path,
    ) -> dict[str, object]:
        compression_ok, compression_message, _compression_metrics = compress_pdf_with_ghostscript(
            flattened_temp_output,
            compressed_temp_output,
            preset=session.ghostscript_preset,
            custom_dpi=PDF_GHOSTSCRIPT_CUSTOM_DPI_DEFAULT,
            run_lossless_postprocess=session.post_compression_use_pikepdf,
            lossless_options=session.build_post_compression_lossless_options(),
        )

        self._raise_if_cancelled()

        if compression_ok:
            os.replace(compressed_temp_output, final_output_path)
            self._cleanup_temp_output(flattened_temp_output)
            return {
                "type": "success",
                "item": job.candidate.source_label,
                "output_path": str(final_output_path),
                "message": compression_message,
            }

        self._cleanup_temp_output(compressed_temp_output)
        os.replace(flattened_temp_output, final_output_path)
        return {
            "type": "warning",
            "item": job.candidate.source_label,
            "output_path": str(final_output_path),
            "message": f"フラット化完了（圧縮はスキップされました）: {compression_message}",
        }

    def _raise_if_cancelled(self) -> None:
        if self._cancel_event.is_set():
            raise FlattenCancelledError()

    def _cleanup_temp_output(self, temp_output: Path) -> None:
        try:
            if temp_output.exists():
                temp_output.unlink()
        except OSError:
            pass