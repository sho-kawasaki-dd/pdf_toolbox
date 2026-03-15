"""PDF 分割アプリケーション - エントリーポイント。

MVP アーキテクチャに基づき、Model / View / Presenter を組み立てて起動する。
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

from view.main_window import MainWindow
from view.startup_splash import show_startup_splash
from presenter.main_presenter import MainPresenter


SPLASH_MIN_SECONDS = 1.0


def _resource_path(filename: str) -> Path:
    """開発実行と PyInstaller 実行の両方で使えるリソースパスを返す。"""
    base_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base_dir / filename


def main() -> None:
    startup_started_at = time.perf_counter()

    view = MainWindow()
    icon_path = _resource_path("pdf_splitter_icon.ico")
    if icon_path.exists():
        view.iconbitmap(str(icon_path))

    view.withdraw()
    splash = show_startup_splash(view, icon_path)

    _presenter = MainPresenter(view)  # noqa: F841  -- View が参照を保持する

    elapsed_seconds = time.perf_counter() - startup_started_at
    remaining_ms = max(0, int((SPLASH_MIN_SECONDS - elapsed_seconds) * 1000))

    def close_splash() -> None:
        if splash.winfo_exists():
            splash.destroy()
        view.deiconify()
        view.lift()
        view.focus_force()

    if remaining_ms > 0:
        view.after(remaining_ms, close_splash)
    else:
        close_splash()

    view.mainloop()


if __name__ == "__main__":
    main()
