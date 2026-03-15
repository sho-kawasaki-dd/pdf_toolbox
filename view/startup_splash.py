"""起動時スプラッシュ表示ユーティリティ (PySide6)。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QSplashScreen
from PySide6.QtGui import QPixmap, QPainter, QColor, QFont, QGuiApplication, QIcon
from PySide6.QtCore import Qt

from view.font_config import make_app_font


SPLASH_MIN_WIDTH = 420
SPLASH_MIN_HEIGHT = 260
SPLASH_MAX_WIDTH = 720
SPLASH_MAX_HEIGHT = 420
PREFERRED_SPLASH_ICON_SIZE = 256


def _compute_splash_size(screen_width: int, screen_height: int) -> tuple[int, int]:
    """画面解像度に応じたスプラッシュサイズを返す。"""
    width = max(SPLASH_MIN_WIDTH, min(SPLASH_MAX_WIDTH, int(screen_width * 0.28)))
    height = max(SPLASH_MIN_HEIGHT, min(SPLASH_MAX_HEIGHT, int(screen_height * 0.24)))
    return width, height


def _select_icon_size(available_sizes: list[tuple[int, int]]) -> int:
    """`.ico` に含まれるサイズから、256px を優先して選ぶ。"""
    if not available_sizes:
        return PREFERRED_SPLASH_ICON_SIZE

    square_sizes = sorted({min(width, height) for width, height in available_sizes if width > 0 and height > 0})
    if not square_sizes:
        return PREFERRED_SPLASH_ICON_SIZE

    for size in square_sizes:
        if size >= PREFERRED_SPLASH_ICON_SIZE:
            return size
    return square_sizes[-1]


def _load_splash_icon_pixmap(icon_path: Path) -> QPixmap:
    """`.ico` からスプラッシュ向けの高解像度表現を読み込む。"""
    icon = QIcon(str(icon_path))
    if icon.isNull():
        return QPixmap()

    available_sizes = [(size.width(), size.height()) for size in icon.availableSizes()]
    chosen_size = _select_icon_size(available_sizes)
    return icon.pixmap(chosen_size, chosen_size)


def show_startup_splash(icon_path: Path) -> QSplashScreen:
    """画面サイズに応じたスプラッシュを表示して返す。"""
    screen = QGuiApplication.primaryScreen()
    if screen is not None:
        rect = screen.availableGeometry()
        splash_width, splash_height = _compute_splash_size(rect.width(), rect.height())
    else:
        splash_width, splash_height = _compute_splash_size(1920, 1080)

    pixmap = QPixmap(splash_width, splash_height)
    pixmap.fill(QColor("white"))

    painter = QPainter(pixmap)
    painter.fillRect(pixmap.rect(), QColor("#f8fafc"))
    painter.fillRect(0, 0, splash_width, splash_height, QColor(248, 250, 252))

    if icon_path.exists():
        icon_pixmap = _load_splash_icon_pixmap(icon_path)
        if not icon_pixmap.isNull():
            icon_box = min(int(splash_width * 0.32), int(splash_height * 0.62))
            scaled = icon_pixmap.scaled(
                icon_box,
                icon_box,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            margin_x = max(24, splash_width // 14)
            icon_x = margin_x
            icon_y = (splash_height - scaled.height()) // 2
            painter.drawPixmap(icon_x, icon_y, scaled)
        else:
            _draw_fallback_text(painter, pixmap)
    else:
        _draw_fallback_text(painter, pixmap)

    text_left = max(24, splash_width // 14) + min(int(splash_width * 0.32), int(splash_height * 0.62)) + 24
    text_width = max(80, splash_width - text_left - 24)
    title_top = max(32, splash_height // 4)
    title_height = max(36, splash_height // 6)
    subtitle_top = title_top + title_height + max(18, splash_height // 14)
    subtitle_height = max(28, splash_height // 7)
    title_rect = pixmap.rect().adjusted(
        text_left,
        title_top,
        -(24),
        -(splash_height - title_top - title_height),
    )
    subtitle_rect = pixmap.rect().adjusted(
        text_left,
        subtitle_top,
        -(24),
        -(splash_height - subtitle_top - subtitle_height),
    )

    painter.setPen(QColor("#0f172a"))
    painter.setFont(make_app_font(max(18, splash_height // 12), bold=True))
    painter.drawText(title_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "PDF Splitter")

    painter.setPen(QColor("#475569"))
    painter.setFont(make_app_font(max(10, splash_height // 24)))
    painter.drawText(
        subtitle_rect,
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
        "PySide6 UI を初期化しています...",
    )
    painter.end()

    splash = QSplashScreen(pixmap)
    splash.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)
    splash.show()
    return splash


def _draw_fallback_text(painter: QPainter, pixmap: QPixmap) -> None:
    """アイコンが読み込めない場合のフォールバックテキストを描画する。"""
    fallback_rect = pixmap.rect().adjusted(24, 24, -24, -24)
    painter.setPen(QColor("#334155"))
    painter.setFont(make_app_font(18, bold=True))
    painter.drawText(fallback_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, "PDF Splitter")
