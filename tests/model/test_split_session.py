"""SplitSession の回帰テスト。

分割点管理・ページナビゲーション・ズーム・ファイル名サニタイズ・ジョブ生成を網羅する。
"""

from __future__ import annotations

import pytest

from model.split_session import SplitSession


# ======================================================================
# reset() 後の初期状態
# ======================================================================

class TestReset:

    def test_reset_initializes_state(self):
        s = SplitSession()
        s.reset(10)
        assert s.total_pages == 10
        assert s.current_page_idx == 0
        assert s.split_points == []
        assert s.preview_zoom == SplitSession.ZOOM_DEFAULT
        assert len(s.sections_data) == 1

    def test_reset_clears_previous_state(self):
        s = SplitSession()
        s.reset(10)
        s.add_split_point()  # ページ 0 では追加不可
        s.go_to_page(3)
        s.add_split_point()
        s.reset(5)
        assert s.total_pages == 5
        assert s.current_page_idx == 0
        assert s.split_points == []

    def test_reset_zero_pages(self):
        s = SplitSession()
        s.reset(0)
        assert s.total_pages == 0
        assert s.sections_data == []

    def test_single_section_after_reset(self):
        s = SplitSession()
        s.reset(10)
        sec = s.sections_data[0]
        assert sec["start"] == 0
        assert sec["end"] == 9
        assert sec["filename"] == "output_part1.pdf"
        assert sec["is_custom_name"] is False


# ======================================================================
# ページナビゲーション
# ======================================================================

class TestPageNavigation:

    def test_next_page(self):
        s = SplitSession()
        s.reset(10)
        assert s.next_page() is True
        assert s.current_page_idx == 1

    def test_prev_page(self):
        s = SplitSession()
        s.reset(10)
        s.go_to_page(5)
        assert s.prev_page() is True
        assert s.current_page_idx == 4

    def test_prev_page_at_first(self):
        s = SplitSession()
        s.reset(10)
        assert s.prev_page() is False
        assert s.current_page_idx == 0

    def test_next_page_at_last(self):
        s = SplitSession()
        s.reset(10)
        s.go_to_page(9)
        assert s.next_page() is False
        assert s.current_page_idx == 9

    def test_go_to_page(self):
        s = SplitSession()
        s.reset(10)
        assert s.go_to_page(5) is True
        assert s.current_page_idx == 5

    def test_go_to_page_out_of_range(self):
        s = SplitSession()
        s.reset(10)
        assert s.go_to_page(10) is False
        assert s.go_to_page(-1) is False

    def test_go_to_same_page(self):
        s = SplitSession()
        s.reset(10)
        assert s.go_to_page(0) is False

    def test_prev_10_pages(self):
        s = SplitSession()
        s.reset(20)
        s.go_to_page(15)
        assert s.prev_10_pages() is True
        assert s.current_page_idx == 5

    def test_prev_10_pages_clamps_to_zero(self):
        s = SplitSession()
        s.reset(20)
        s.go_to_page(3)
        assert s.prev_10_pages() is True
        assert s.current_page_idx == 0

    def test_prev_10_pages_at_first(self):
        s = SplitSession()
        s.reset(10)
        assert s.prev_10_pages() is False

    def test_next_10_pages(self):
        s = SplitSession()
        s.reset(20)
        assert s.next_10_pages() is True
        assert s.current_page_idx == 10

    def test_next_10_pages_clamps_to_last(self):
        s = SplitSession()
        s.reset(20)
        s.go_to_page(17)
        assert s.next_10_pages() is True
        assert s.current_page_idx == 19

    def test_next_10_pages_at_last(self):
        s = SplitSession()
        s.reset(10)
        s.go_to_page(9)
        assert s.next_10_pages() is False

    def test_navigation_with_no_pages(self):
        s = SplitSession()
        s.reset(0)
        assert s.next_page() is False
        assert s.prev_page() is False
        assert s.go_to_page(0) is False


# ======================================================================
# 分割点の追加・削除・クリア・全ページ分割
# ======================================================================

class TestSplitPoints:

    def test_add_split_point(self):
        s = SplitSession()
        s.reset(10)
        s.go_to_page(5)
        assert s.add_split_point() is True
        assert 5 in s.split_points

    def test_add_split_point_at_page_zero(self):
        """先頭ページには分割点を追加できない。"""
        s = SplitSession()
        s.reset(10)
        assert s.add_split_point() is False

    def test_add_duplicate_split_point(self):
        s = SplitSession()
        s.reset(10)
        s.go_to_page(5)
        s.add_split_point()
        assert s.add_split_point() is False

    def test_remove_split_point(self):
        s = SplitSession()
        s.reset(10)
        s.go_to_page(5)
        s.add_split_point()
        assert s.remove_split_point() is True
        assert 5 not in s.split_points

    def test_remove_nonexistent_split_point(self):
        s = SplitSession()
        s.reset(10)
        s.go_to_page(5)
        assert s.remove_split_point() is False

    def test_clear_split_points(self):
        s = SplitSession()
        s.reset(10)
        s.go_to_page(3)
        s.add_split_point()
        s.go_to_page(7)
        s.add_split_point()
        s.clear_split_points()
        assert s.split_points == []
        assert len(s.sections_data) == 1

    def test_split_every_page(self):
        s = SplitSession()
        s.reset(5)
        s.split_every_page()
        assert s.split_points == [1, 2, 3, 4]
        assert len(s.sections_data) == 5

    def test_split_every_page_single_page(self):
        s = SplitSession()
        s.reset(1)
        s.split_every_page()
        assert s.split_points == []

    def test_remove_split_point_at(self):
        s = SplitSession()
        s.reset(10)
        s.go_to_page(3)
        s.add_split_point()
        assert s.remove_split_point_at(3) is True
        assert 3 not in s.split_points

    def test_remove_active_section_split_point(self):
        s = SplitSession()
        s.reset(10)
        s.go_to_page(5)
        s.add_split_point()
        # アクティブセクション 1 の開始分割点を消去
        assert s.remove_active_section_split_point() is True
        assert 5 not in s.split_points

    def test_remove_active_section_split_point_first_section(self):
        """最初のセクションには開始分割点がない。"""
        s = SplitSession()
        s.reset(10)
        assert s.remove_active_section_split_point() is False

    def test_split_points_sorted(self):
        s = SplitSession()
        s.reset(10)
        s.go_to_page(7)
        s.add_split_point()
        s.go_to_page(3)
        s.add_split_point()
        assert s.split_points == [3, 7]


# ======================================================================
# セクションデータの再構築
# ======================================================================

class TestSectionsData:

    def test_sections_after_split(self):
        s = SplitSession()
        s.reset(10)
        s.go_to_page(5)
        s.add_split_point()
        assert len(s.sections_data) == 2
        assert s.sections_data[0]["start"] == 0
        assert s.sections_data[0]["end"] == 4
        assert s.sections_data[1]["start"] == 5
        assert s.sections_data[1]["end"] == 9

    def test_sections_default_filenames(self):
        s = SplitSession()
        s.reset(10)
        s.go_to_page(5)
        s.add_split_point()
        assert s.sections_data[0]["filename"] == "output_part1.pdf"
        assert s.sections_data[1]["filename"] == "output_part2.pdf"

    def test_custom_filename_preserved_on_rebuild(self):
        """分割点変更後もカスタムファイル名が引き継がれる。"""
        s = SplitSession()
        s.reset(10)
        s.go_to_page(5)
        s.add_split_point()
        s.save_section_filename(0, "intro")
        assert s.sections_data[0]["filename"] == "intro.pdf"
        # 新しい分割点を追加してもセクション0のカスタム名は残る
        s.go_to_page(8)
        s.add_split_point()
        assert s.sections_data[0]["filename"] == "intro.pdf"

    def test_get_active_section_index(self):
        s = SplitSession()
        s.reset(10)
        s.go_to_page(5)
        s.add_split_point()
        s.go_to_page(3)
        assert s.get_active_section_index() == 0
        s.go_to_page(7)
        assert s.get_active_section_index() == 1

    def test_get_active_section_index_no_data(self):
        s = SplitSession()
        s.reset(0)
        assert s.get_active_section_index() == -1


# ======================================================================
# ファイル名サニタイズ
# ======================================================================

class TestFilenameSanitize:

    def test_normal_filename(self):
        s = SplitSession()
        s.reset(10)
        s.save_section_filename(0, "chapter1")
        assert s.sections_data[0]["filename"] == "chapter1.pdf"
        assert s.sections_data[0]["is_custom_name"] is True

    def test_invalid_characters_replaced(self):
        s = SplitSession()
        s.reset(10)
        s.save_section_filename(0, 'file*name?<test>:"ok|')
        assert "*" not in s.sections_data[0]["filename"]
        assert "?" not in s.sections_data[0]["filename"]
        assert "<" not in s.sections_data[0]["filename"]
        assert ">" not in s.sections_data[0]["filename"]
        assert '"' not in s.sections_data[0]["filename"]
        assert "|" not in s.sections_data[0]["filename"]

    def test_reserved_name_falls_back_to_default(self):
        s = SplitSession()
        s.reset(10)
        s.save_section_filename(0, "CON")
        assert s.sections_data[0]["filename"] == "output_part1.pdf"
        assert s.sections_data[0]["is_custom_name"] is False

    def test_reserved_name_case_insensitive(self):
        s = SplitSession()
        s.reset(10)
        s.save_section_filename(0, "nul")
        assert s.sections_data[0]["filename"] == "output_part1.pdf"

    def test_empty_string_falls_back_to_default(self):
        s = SplitSession()
        s.reset(10)
        s.save_section_filename(0, "")
        assert s.sections_data[0]["filename"] == "output_part1.pdf"
        assert s.sections_data[0]["is_custom_name"] is False

    def test_whitespace_only_falls_back_to_default(self):
        s = SplitSession()
        s.reset(10)
        s.save_section_filename(0, "   ")
        assert s.sections_data[0]["filename"] == "output_part1.pdf"

    def test_pdf_extension_removed(self):
        s = SplitSession()
        s.reset(10)
        s.save_section_filename(0, "chapter1.pdf")
        assert s.sections_data[0]["filename"] == "chapter1.pdf"
        # .pdf が二重にならないことを確認
        assert not s.sections_data[0]["filename"].endswith(".pdf.pdf")

    def test_underscores_only_falls_back_to_default(self):
        s = SplitSession()
        s.reset(10)
        s.save_section_filename(0, "___")
        assert s.sections_data[0]["filename"] == "output_part1.pdf"

    def test_out_of_range_section_index(self):
        s = SplitSession()
        s.reset(10)
        # 範囲外のインデックスではエラーにならない
        s.save_section_filename(-1, "test")
        s.save_section_filename(99, "test")

    def test_setting_default_name_clears_custom_flag(self):
        """デフォルト名と同じ名前を入力すると is_custom_name が False になる。"""
        s = SplitSession()
        s.reset(10)
        s.save_section_filename(0, "output_part1")
        assert s.sections_data[0]["is_custom_name"] is False


# ======================================================================
# ズーム操作
# ======================================================================

class TestZoom:

    def test_zoom_in(self):
        s = SplitSession()
        s.reset(10)
        assert s.zoom_in() is True
        assert s.preview_zoom > SplitSession.ZOOM_DEFAULT

    def test_zoom_out(self):
        s = SplitSession()
        s.reset(10)
        assert s.zoom_out() is True
        assert s.preview_zoom < SplitSession.ZOOM_DEFAULT

    def test_zoom_max(self):
        s = SplitSession()
        s.reset(10)
        s.set_zoom(SplitSession.ZOOM_MAX)
        assert s.zoom_in() is False

    def test_zoom_min(self):
        s = SplitSession()
        s.reset(10)
        s.set_zoom(SplitSession.ZOOM_MIN)
        assert s.zoom_out() is False

    def test_reset_zoom(self):
        s = SplitSession()
        s.reset(10)
        s.zoom_in()
        assert s.reset_zoom() is True
        assert s.preview_zoom == SplitSession.ZOOM_DEFAULT

    def test_reset_zoom_no_change(self):
        s = SplitSession()
        s.reset(10)
        assert s.reset_zoom() is False

    def test_zoom_percent(self):
        s = SplitSession()
        s.reset(10)
        assert s.zoom_percent == 100
        s.zoom_in()
        assert s.zoom_percent == 110

    def test_zoom_step(self):
        s = SplitSession()
        s.reset(10)
        s.zoom_in()
        expected = round(SplitSession.ZOOM_DEFAULT + SplitSession.ZOOM_STEP, 2)
        assert s.preview_zoom == expected


# ======================================================================
# セクション間ナビゲーション
# ======================================================================

class TestSectionNavigation:

    def test_next_section(self):
        s = SplitSession()
        s.reset(10)
        s.go_to_page(5)
        s.add_split_point()
        s.go_to_page(0)
        assert s.next_section() is True
        assert s.current_page_idx == 5

    def test_prev_section(self):
        s = SplitSession()
        s.reset(10)
        s.go_to_page(5)
        s.add_split_point()
        s.go_to_page(7)
        assert s.prev_section() is True
        assert s.current_page_idx == 0

    def test_next_section_at_last(self):
        s = SplitSession()
        s.reset(10)
        assert s.next_section() is False

    def test_prev_section_at_first(self):
        s = SplitSession()
        s.reset(10)
        assert s.prev_section() is False


# ======================================================================
# collect_split_jobs()
# ======================================================================

class TestCollectSplitJobs:

    def test_single_section(self):
        s = SplitSession()
        s.reset(10)
        jobs = s.collect_split_jobs()
        assert len(jobs) == 1
        assert jobs[0]["index"] == 1
        assert jobs[0]["start"] == 0
        assert jobs[0]["end"] == 9
        assert jobs[0]["filename"] == "output_part1.pdf"

    def test_multiple_sections(self):
        s = SplitSession()
        s.reset(10)
        s.go_to_page(5)
        s.add_split_point()
        jobs = s.collect_split_jobs()
        assert len(jobs) == 2
        assert jobs[0]["start"] == 0
        assert jobs[0]["end"] == 4
        assert jobs[1]["start"] == 5
        assert jobs[1]["end"] == 9

    def test_jobs_with_custom_filename(self):
        s = SplitSession()
        s.reset(10)
        s.save_section_filename(0, "introduction")
        jobs = s.collect_split_jobs()
        assert jobs[0]["filename"] == "introduction.pdf"

    def test_every_page_split_jobs(self):
        s = SplitSession()
        s.reset(5)
        s.split_every_page()
        jobs = s.collect_split_jobs()
        assert len(jobs) == 5
        for i, job in enumerate(jobs):
            assert job["start"] == i
            assert job["end"] == i
