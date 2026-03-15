"""PDF 分割アプリケーション - エントリーポイント。

MVP アーキテクチャに基づき、Model / View / Presenter を組み立てて起動する。
PySide6 ベースの QApplication + QMainWindow 構成。
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon

from view.main_window import MainWindow
from view.startup_splash import show_startup_splash
from view.font_config import make_app_font
from presenter.main_presenter import MainPresenter


SPLASH_MIN_SECONDS = 2.0


def _resource_path(filename: str) -> Path:
    """開発実行と PyInstaller 実行の両方で使えるリソースパスを返す。"""
    base_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base_dir / filename


def main() -> None:
    app = QApplication(sys.argv)
    app.setFont(make_app_font(10))

    icon_path = _resource_path("pdf_splitter_icon.ico")
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    startup_started_at = time.perf_counter()

    splash = show_startup_splash(icon_path)
    app.processEvents()

    view = MainWindow()

    _presenter = MainPresenter(view)  # noqa: F841  -- View が参照を保持する

    elapsed_seconds = time.perf_counter() - startup_started_at
    remaining_ms = max(0, int((SPLASH_MIN_SECONDS - elapsed_seconds) * 1000))

    def close_splash_and_show() -> None:
        splash.close()
        view.show()
        view.raise_()
        view.activateWindow()

    if remaining_ms > 0:
        from PySide6.QtCore import QTimer
        QTimer.singleShot(remaining_ms, close_splash_and_show)
    else:
        close_splash_and_show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
