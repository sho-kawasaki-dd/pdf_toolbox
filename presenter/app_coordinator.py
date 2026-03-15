"""Application-level screen coordinator."""

from __future__ import annotations

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
    """Manage screen transitions and presenter lifecycles."""

    def __init__(self, view: MainWindow) -> None:
        self._view = view
        self._split_presenter = SplitPresenter(view)

        self._view.home_view.feature_selected.connect(self._on_feature_selected)
        self._view.split_view.back_to_home_requested.connect(self.on_back_to_home)

    @property
    def split_presenter(self) -> SplitPresenter:
        return self._split_presenter

    def _on_feature_selected(self, feature: str) -> None:
        if feature == "split":
            self._view.show_split()
            return

        label = FEATURE_LABELS.get(feature, feature)
        self._view.show_info("準備中", f"「{label}」機能は準備中です。")

    def on_back_to_home(self) -> None:
        if self._split_presenter.is_busy():
            self._view.show_info("実行中", "分割処理の実行中はホームへ戻れません。")
            return

        if self._split_presenter.has_active_session():
            if not self._view.ask_yes_no(
                "確認",
                "現在の分割セッションを保持したままホームへ戻ります。よろしいですか？",
            ):
                return

        self._view.show_home()
