"""PdfProcessor の回帰テスト。

バックグラウンドスレッドでの PDF 分割・保存処理を検証する。
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from model.split.pdf_processor import PdfProcessor
from model.split.split_session import SplitSession


class TestStartSplit:

    def test_split_success(self, sample_pdf: Path, tmp_path: Path):
        processor = PdfProcessor()
        out_dir = tmp_path / "output"
        out_dir.mkdir()

        session = SplitSession()
        session.reset(10)
        session.go_to_page(5)
        session.add_split_point()
        jobs = session.collect_split_jobs()

        processor.start_split(str(sample_pdf), str(out_dir), jobs)

        # ワーカースレッド完了を待つ
        deadline = time.monotonic() + 10
        while processor.is_splitting and time.monotonic() < deadline:
            time.sleep(0.05)

        results = processor.poll_results()
        assert len(results) == 1
        assert results[0]["type"] == "success"
        assert results[0]["file_count"] == 2

    def test_output_files_exist(self, sample_pdf: Path, tmp_path: Path):
        processor = PdfProcessor()
        out_dir = tmp_path / "output"
        out_dir.mkdir()

        session = SplitSession()
        session.reset(10)
        session.go_to_page(5)
        session.add_split_point()
        jobs = session.collect_split_jobs()

        processor.start_split(str(sample_pdf), str(out_dir), jobs)

        deadline = time.monotonic() + 10
        while processor.is_splitting and time.monotonic() < deadline:
            time.sleep(0.05)

        processor.poll_results()
        assert (out_dir / "output_part1.pdf").exists()
        assert (out_dir / "output_part2.pdf").exists()

    def test_duplicate_filename_gets_numbered(self, sample_pdf: Path, tmp_path: Path):
        """同名ファイルが存在する場合、連番が付与される。"""
        processor = PdfProcessor()
        out_dir = tmp_path / "output"
        out_dir.mkdir()

        # 先にファイルを作っておく
        (out_dir / "output_part1.pdf").write_text("dummy")

        session = SplitSession()
        session.reset(10)
        jobs = session.collect_split_jobs()  # output_part1.pdf

        processor.start_split(str(sample_pdf), str(out_dir), jobs)

        deadline = time.monotonic() + 10
        while processor.is_splitting and time.monotonic() < deadline:
            time.sleep(0.05)

        results = processor.poll_results()
        assert results[0]["type"] == "success"
        # 元のファイルは残り、連番付きファイルが生成される
        assert (out_dir / "output_part1.pdf").exists()
        assert (out_dir / "output_part1 (1).pdf").exists()

    def test_split_single_page_sections(self, sample_pdf: Path, tmp_path: Path):
        processor = PdfProcessor()
        out_dir = tmp_path / "output"
        out_dir.mkdir()

        session = SplitSession()
        session.reset(10)
        session.split_every_page()
        jobs = session.collect_split_jobs()

        processor.start_split(str(sample_pdf), str(out_dir), jobs)

        deadline = time.monotonic() + 10
        while processor.is_splitting and time.monotonic() < deadline:
            time.sleep(0.05)

        results = processor.poll_results()
        assert results[0]["type"] == "success"
        assert results[0]["file_count"] == 10


class TestPollAndDrain:

    def test_poll_empty_queue(self):
        processor = PdfProcessor()
        assert processor.poll_results() == []

    def test_drain_queue(self, sample_pdf: Path, tmp_path: Path):
        processor = PdfProcessor()
        out_dir = tmp_path / "output"
        out_dir.mkdir()

        session = SplitSession()
        session.reset(10)
        jobs = session.collect_split_jobs()

        processor.start_split(str(sample_pdf), str(out_dir), jobs)

        deadline = time.monotonic() + 10
        while processor.is_splitting and time.monotonic() < deadline:
            time.sleep(0.05)

        processor.drain_queue()
        assert processor.poll_results() == []

    def test_no_duplicate_start(self, sample_pdf: Path, tmp_path: Path):
        """is_splitting 中は start_split が無視される。"""
        processor = PdfProcessor()
        out_dir = tmp_path / "output"
        out_dir.mkdir()

        session = SplitSession()
        session.reset(10)
        jobs = session.collect_split_jobs()

        processor.start_split(str(sample_pdf), str(out_dir), jobs)
        # まだ実行中の間に再度呼び出し
        processor.start_split(str(sample_pdf), str(out_dir), jobs)

        deadline = time.monotonic() + 10
        while processor.is_splitting and time.monotonic() < deadline:
            time.sleep(0.05)

        results = processor.poll_results()
        # 結果は 1 つだけ（二重実行されていない）
        assert len(results) == 1
