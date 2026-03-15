"""アプリケーション共通フォント設定。"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase


APP_FONT_RELATIVE_PATH = Path("fonts") / "ipaexg.ttf"
APP_FONT_FALLBACK_FAMILY = "Sans Serif"

_loaded_font_family: str | None = None


def _resource_path(relative_path: Path) -> Path:
    """開発実行と PyInstaller 実行の両方で使えるリソースパスを返す。"""
    base_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base_dir / relative_path


def ensure_application_font_family() -> str:
    """ipaexg.ttf を読み込み、利用可能なフォントファミリー名を返す。"""
    global _loaded_font_family

    if _loaded_font_family is not None:
        return _loaded_font_family

    font_path = _resource_path(APP_FONT_RELATIVE_PATH)
    if font_path.exists():
        font_id = QFontDatabase.addApplicationFont(str(font_path))
        if font_id != -1:
            families = QFontDatabase.applicationFontFamilies(font_id)
            if families:
                _loaded_font_family = families[0]

    if _loaded_font_family is None:
        _loaded_font_family = APP_FONT_FALLBACK_FAMILY

    return _loaded_font_family


def make_app_font(point_size: int, *, bold: bool = False) -> QFont:
    """アプリケーション共通フォントを生成する。"""
    font = QFont(ensure_application_font_family(), point_size)
    font.setBold(bold)
    return font