"""PySide6 の import が成功することを確認するテスト。"""

from __future__ import annotations


def test_import_pyside6():
    import PySide6  # noqa: F401


def test_import_qapplication():
    from PySide6.QtWidgets import QApplication  # noqa: F401


def test_import_qmainwindow():
    from PySide6.QtWidgets import QMainWindow  # noqa: F401


def test_import_qtcore():
    from PySide6.QtCore import Qt, QTimer  # noqa: F401


def test_import_qtgui():
    from PySide6.QtGui import QPixmap, QImage  # noqa: F401
