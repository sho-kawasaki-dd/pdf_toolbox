"""Model と View を調停する Presenter。

ドメインロジック（Model）と描画（View）のいずれにも依存するが、
Tkinter / CustomTkinter のウィジェット API を直接呼ぶことはない。
View が公開するメソッド（``update_ui``, ``display_page`` など）と
ダイアログラッパー（``show_info``, ``ask_yes_no`` など）のみを使用する。
"""

from __future__ import annotations

from model.pdf_document import PdfDocument
from model.split_session import SplitSession
from model.pdf_processor import PdfProcessor
from view.main_window import MainWindow, UiState
from view.components.split_bar import SECTION_COLORS


class MainPresenter:
    """View からのイベントを受け取り、Model を操作し、View を更新する。"""

    def __init__(self, view: MainWindow) -> None:
        self._view = view
        self._doc = PdfDocument()
        self._session = SplitSession()
        self._processor = PdfProcessor()
        self._poll_job_id: str | None = None

        # View にこの Presenter を接続
        self._view.set_presenter(self)

    # ==================================================================
    # PDF を開く / 閉じる
    # ==================================================================

    def open_pdf(self) -> None:
        if self._processor.is_splitting:
            self._view.show_info("実行中", "分割処理の実行中はPDFを開けません。")
            return

        file_path = self._view.ask_open_file()
        if not file_path:
            return

        total_pages = self._doc.open(file_path)
        self._session.reset(total_pages)
        self._render_and_refresh()

    def on_closing(self) -> None:
        if self._processor.is_splitting:
            if not self._view.ask_ok_cancel(
                "確認",
                "現在PDFの分割処理中です。強制終了するとファイルが破損する可能性があります。本当に終了しますか？",
            ):
                return

        if self._poll_job_id is not None:
            self._view.cancel_schedule(self._poll_job_id)
            self._poll_job_id = None

        self._doc.close()
        self._view.destroy_window()

    # ==================================================================
    # ページナビゲーション
    # ==================================================================

    def prev_page(self) -> None:
        if self._session.prev_page():
            self._render_and_refresh()

    def next_page(self) -> None:
        if self._session.next_page():
            self._render_and_refresh()

    def prev_10_pages(self) -> None:
        if self._session.prev_10_pages():
            self._render_and_refresh()

    def next_10_pages(self) -> None:
        if self._session.next_10_pages():
            self._render_and_refresh()

    def go_to_first_page(self) -> None:
        if self._session.go_to_page(0):
            self._render_and_refresh()

    def go_to_last_page(self) -> None:
        if self._session.total_pages > 0:
            if self._session.go_to_page(self._session.total_pages - 1):
                self._render_and_refresh()

    def go_to_page(self, page_idx: int) -> None:
        self._save_active_section_filename()
        if self._session.go_to_page(page_idx):
            self._render_and_refresh()

    # ==================================================================
    # セクション間ナビゲーション
    # ==================================================================

    def prev_section(self) -> None:
        self._save_active_section_filename()
        if self._session.prev_section():
            self._render_and_refresh()

    def next_section(self) -> None:
        self._save_active_section_filename()
        if self._session.next_section():
            self._render_and_refresh()

    # ==================================================================
    # 分割点操作
    # ==================================================================

    def add_split_point(self) -> None:
        self._save_active_section_filename()
        if self._session.add_split_point():
            self._refresh_ui()

    def remove_split_point(self) -> None:
        self._save_active_section_filename()
        if self._session.remove_split_point():
            self._refresh_ui()

    def remove_active_section_split_point(self) -> None:
        self._save_active_section_filename()
        if self._session.remove_active_section_split_point():
            self._refresh_ui()

    def clear_split_points(self) -> None:
        if not self._view.ask_yes_no(
            "確認", "現在の分割点をすべてリセットします。\n実行しますか？"
        ):
            return
        self._session.clear_split_points()
        self._refresh_ui()

    def split_every_page(self) -> None:
        if not self._view.ask_yes_no(
            "確認",
            "分割点を1ページごとに一括設定します。現在の分割点は上書きされます。\n実行しますか？",
        ):
            return
        self._session.split_every_page()
        self._refresh_ui()

    # ==================================================================
    # ズーム
    # ==================================================================

    def zoom_in(self) -> None:
        if self._session.zoom_in():
            self._render_and_refresh()

    def zoom_out(self) -> None:
        if self._session.zoom_out():
            self._render_and_refresh()

    def reset_zoom(self) -> None:
        if self._session.reset_zoom():
            self._render_and_refresh()

    # ==================================================================
    # セクションファイル名
    # ==================================================================

    def save_section_filename(self) -> None:
        """View のテキスト入力を Model に反映する。"""
        self._save_active_section_filename()

    def save_and_advance_section(self) -> None:
        """ファイル名を保存し、次のセクションに移動してテキスト欄を全選択する。"""
        self._save_active_section_filename()
        idx = self._session.get_active_section_index()
        if idx < len(self._session.sections_data) - 1:
            self._session.current_page_idx = self._session.sections_data[idx + 1]["start"]
            self._render_and_refresh()
            self._view.schedule_focus_filename_entry()

    # ==================================================================
    # 分割実行
    # ==================================================================

    def execute_split(self) -> None:
        if not self._doc.is_open or self._processor.is_splitting:
            return

        self._save_active_section_filename()

        out_dir = self._view.ask_directory()
        if not out_dir:
            return

        source_path = self._doc.source_path
        if not source_path:
            self._view.show_error(
                "エラー", "元PDFのパスが取得できませんでした。PDFを開き直してください。"
            )
            return

        jobs = self._session.collect_split_jobs()
        if not jobs:
            self._view.show_error("エラー", "分割対象のセクションがありません。")
            return

        self._processor.start_split(source_path, out_dir, jobs)
        self._refresh_ui()

        # 結果ポーリングを開始
        if self._poll_job_id is None:
            self._poll_job_id = self._view.schedule(100, self._poll_split_results)

    # ==================================================================
    # 非同期結果ポーリング
    # ==================================================================

    def _poll_split_results(self) -> None:
        results = self._processor.poll_results()

        for result in results:
            result_type = result.get("type")
            if result_type == "success":
                self._refresh_ui()
                self._view.show_info(
                    "完了",
                    f"PDFの分割が完了しました。\n作成ファイル数: {result.get('file_count', 0)}",
                )
            elif result_type == "error":
                self._refresh_ui()
                self._view.show_error(
                    "保存エラー",
                    result.get("message", "不明なエラーが発生しました。"),
                )

        if self._processor.is_splitting:
            self._poll_job_id = self._view.schedule(100, self._poll_split_results)
        else:
            self._poll_job_id = None

    # ==================================================================
    # 内部ヘルパー
    # ==================================================================

    def _save_active_section_filename(self) -> None:
        """View のファイル名入力を Model に反映する。"""
        idx = self._session.get_active_section_index()
        if idx >= 0:
            text = self._view.get_section_filename()
            self._session.save_section_filename(idx, text)

    def _render_and_refresh(self) -> None:
        """現在ページをレンダリングし、UI 全体を更新する。"""
        if self._doc.is_open:
            frame_w, frame_h = self._view.get_preview_size()
            pil_img, w, h = self._doc.render_page_image(
                self._session.current_page_idx,
                frame_w,
                frame_h,
                self._session.preview_zoom,
            )
            self._view.display_page(pil_img, w, h)
        self._refresh_ui()

    def _refresh_ui(self) -> None:
        """Model の最新状態から UiState を構築し、View に一括反映する。"""
        state = self._build_ui_state()
        self._view.update_ui(state)

    def _build_ui_state(self) -> UiState:
        """Model の現在状態を UiState に変換する。"""
        s = self._session
        doc_open = self._doc.is_open
        splitting = self._processor.is_splitting
        active_idx = s.get_active_section_index()
        total_sections = len(s.sections_data)

        # セクション情報
        if active_idx >= 0 and total_sections > 0:
            sec = s.sections_data[active_idx]
            section_info = f"セクション {active_idx + 1} / {total_sections}"
            section_range = f"ページ範囲: P.{sec['start'] + 1} - P.{sec['end'] + 1}"
            section_color = SECTION_COLORS[active_idx % len(SECTION_COLORS)]
            section_filename = sec["filename"]
        else:
            section_info = "- / -"
            section_range = "ページ範囲: -"
            section_color = "gray"
            section_filename = ""

        # ボタン状態（基本値）
        can_prev = doc_open and s.current_page_idx > 0
        can_next = doc_open and s.current_page_idx < s.total_pages - 1
        can_add_split = (
            doc_open
            and s.current_page_idx > 0
            and s.current_page_idx not in s.split_points
        )
        can_remove_split = doc_open and s.current_page_idx in s.split_points
        can_clear_split = doc_open
        can_split_every = doc_open and s.total_pages > 1
        can_execute = doc_open
        can_open = True
        can_prev_section = doc_open and active_idx > 0
        can_next_section = doc_open and active_idx < total_sections - 1
        can_remove_active_split = (
            doc_open
            and active_idx > 0
            and active_idx < total_sections
            and s.sections_data[active_idx]["start"] in s.split_points
        )
        can_edit_filename = doc_open

        # 分割中はすべての操作を無効化
        if splitting:
            can_prev = False
            can_next = False
            can_add_split = False
            can_remove_split = False
            can_clear_split = False
            can_split_every = False
            can_execute = False
            can_open = False
            can_prev_section = False
            can_next_section = False
            can_remove_active_split = False
            can_edit_filename = False

        return UiState(
            page_info_text=(
                f"{s.current_page_idx + 1} / {s.total_pages}" if doc_open else "0 / 0"
            ),
            zoom_info_text=f"倍率: {s.zoom_percent}%",
            total_pages=s.total_pages,
            current_page=s.current_page_idx,
            split_points=list(s.split_points),
            active_section_index=active_idx,
            section_info_text=section_info,
            section_range_text=section_range,
            section_color=section_color,
            section_filename=section_filename,
            can_prev=can_prev,
            can_next=can_next,
            can_add_split=can_add_split,
            can_remove_split=can_remove_split,
            can_clear_split=can_clear_split,
            can_split_every=can_split_every,
            can_execute=can_execute,
            can_open=can_open,
            can_prev_section=can_prev_section,
            can_next_section=can_next_section,
            can_remove_active_split=can_remove_active_split,
            can_edit_filename=can_edit_filename,
        )
