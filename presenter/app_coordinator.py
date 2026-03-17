"""アプリ全体の画面遷移と終了制御を束ねる Coordinator。"""

from __future__ import annotations

from presenter.compress_presenter import CompressionPresenter
from presenter.merge_presenter import MergePresenter
from presenter.pdf_to_jpeg_presenter import PdfToJpegPresenter
from presenter.split_presenter import SplitPresenter
from view.main_window import MainWindow


FEATURE_LABELS = {
    "split": "PDF 分割",
    "merge": "PDF 結合",
    "reorder": "ページ並び替え",
    "compress": "PDF 圧縮",
    "pdf-to-jpeg": "PDF → JPEG",
}


class AppCoordinator:
    """ホーム画面と各機能画面の遷移を調停する。"""

    def __init__(self, view: MainWindow) -> None:
        self._view = view
        # 各 Presenter はアプリ起動時に一度だけ組み立て、
        # 画面を行き来してもセッション状態を保持できるようにする。
        self._split_presenter = SplitPresenter(view)
        self._merge_presenter = MergePresenter(view)
        self._compress_presenter = CompressionPresenter(view)
        self._pdf_to_jpeg_presenter = PdfToJpegPresenter(view)

        # 画面固有の戻る操作とウィンドウ終了操作をここへ集約して、
        # 各 Presenter が自分の実行中状態だけを判断すれば済むようにする。
        self._view.home_view.feature_selected.connect(self._on_feature_selected)
        self._view.split_view.back_to_home_requested.connect(self.on_back_to_home)
        self._view.merge_view.back_to_home_requested.connect(self.on_back_to_home)
        self._view.compress_view.back_to_home_requested.connect(self.on_back_to_home)
        self._view.pdf_to_jpeg_view.back_to_home_requested.connect(self.on_back_to_home)
        self._view.set_close_handler(self.on_window_closing)

    @property
    def split_presenter(self) -> SplitPresenter:
        return self._split_presenter

    @property
    def compress_presenter(self) -> CompressionPresenter:
        return self._compress_presenter

    @property
    def merge_presenter(self) -> MergePresenter:
        return self._merge_presenter

    @property
    def pdf_to_jpeg_presenter(self) -> PdfToJpegPresenter:
        return self._pdf_to_jpeg_presenter

    def _on_feature_selected(self, feature: str) -> None:
        """ホーム画面で選ばれた機能に応じて遷移先を切り替える。"""
        if feature == "split":
            self._view.show_split()
            return

        if feature == "merge":
            self._view.show_merge()
            return

        if feature == "compress":
            self._view.show_compress()
            return

        if feature == "pdf-to-jpeg":
            self._view.show_pdf_to_jpeg()
            return

        label = FEATURE_LABELS.get(feature, feature)
        self._view.show_info("準備中", f"「{label}」機能は準備中です。")

    def on_back_to_home(self) -> None:
        """現在画面の状態を確認したうえでホームへ戻す。"""
        current_widget = self._view.stack.currentWidget()

        if current_widget is self._view.split_view:
            # 分割と圧縮は「実行中は戻れない」「作業途中なら確認する」という
            # 同じ UX ルールを機能単位で対称に保つ。
            if self._split_presenter.is_busy():
                self._view.show_info("実行中", "分割処理の実行中はホームへ戻れません。")
                return

            if self._split_presenter.has_active_session():
                if not self._view.ask_yes_no(
                    "確認",
                    "現在の分割セッションを保持したままホームへ戻ります。よろしいですか？",
                ):
                    return

        if current_widget is self._view.compress_view:
            if self._compress_presenter.is_busy():
                self._view.show_info("実行中", "圧縮処理の実行中はホームへ戻れません。")
                return

            if self._compress_presenter.has_active_session():
                if not self._view.ask_yes_no(
                    "確認",
                    "現在の圧縮セッションを保持したままホームへ戻ります。よろしいですか？",
                ):
                    return

        if current_widget is self._view.merge_view:
            if self._merge_presenter.is_busy():
                self._view.show_info("実行中", "結合処理の実行中はホームへ戻れません。")
                return

            if self._merge_presenter.has_active_session():
                if not self._view.ask_yes_no(
                    "確認",
                    "現在の結合セッションを保持したままホームへ戻ります。よろしいですか？",
                ):
                    return

        if current_widget is self._view.pdf_to_jpeg_view:
            if self._pdf_to_jpeg_presenter.is_busy():
                self._view.show_info("実行中", "JPEG変換処理の実行中はホームへ戻れません。")
                return

            if self._pdf_to_jpeg_presenter.has_active_session():
                if not self._view.ask_yes_no(
                    "確認",
                    "現在の PDF→JPEG セッションを保持したままホームへ戻ります。よろしいですか？",
                ):
                    return

        self._view.show_home()

    def on_window_closing(self) -> None:
        """現在の機能画面に応じて終了確認を各 Presenter へ委譲する。"""
        current_widget = self._view.stack.currentWidget()
        # 現在その画面を開いていなくても、セッションが残っていれば
        # 各 Presenter 側の終了確認ロジックを通す。
        if current_widget is self._view.split_view or self._split_presenter.has_active_session():
            self._split_presenter.on_closing()
            return

        if current_widget is self._view.merge_view or self._merge_presenter.has_active_session():
            self._merge_presenter.on_closing()
            return

        if current_widget is self._view.compress_view or self._compress_presenter.has_active_session():
            self._compress_presenter.on_closing()
            return

        if current_widget is self._view.pdf_to_jpeg_view or self._pdf_to_jpeg_presenter.has_active_session():
            self._pdf_to_jpeg_presenter.on_closing()
            return

        self._view.destroy_window()
