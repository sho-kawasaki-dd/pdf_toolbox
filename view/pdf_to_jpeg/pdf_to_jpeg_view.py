from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from view.font_config import make_app_font


@dataclass(slots=True)
class PdfToJpegUiState:
    """PdfToJpegView を 1 回で描画更新するための状態スナップショット。"""

    selected_pdf_text: str = "変換対象の PDF を選択してください"
    output_dir_text: str = "保存先フォルダを選択してください"
    output_detail_text: str = "出力先サブフォルダ: 保存先フォルダを選択してください"
    note_text: str = "透明要素を含むページは白背景へ合成して JPEG 保存します。"
    progress_text: str = "待機中"
    summary_text: str = "成功: 0ページ / 失敗: 0ページ"
    progress_value: int = 0
    jpeg_quality: int = 90
    current_page_number: int = 0
    preview_png_bytes: bytes | None = None
    preview_text: str = "PDFを選択すると\n先頭ページプレビューを表示します"
    has_input_pdf: bool = False
    has_output_dir: bool = False
    has_preview: bool = False
    can_choose_pdf: bool = True
    can_choose_output: bool = True
    can_execute: bool = False
    can_edit_quality: bool = True
    can_back_home: bool = True
    is_running: bool = False


class PreviewDropLabel(QLabel):
    """PDF のドロップ入力も兼ねるプレビュー表示ラベル。"""

    paths_dropped = Signal(list)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:
        if not event.mimeData().hasUrls():
            super().dropEvent(event)
            return

        paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        if paths:
            self.paths_dropped.emit(paths)
            event.acceptProposedAction()
            return

        super().dropEvent(event)


class PdfToJpegView(QWidget):
    """PDF→JPEG 画面のウィジェット構築と表示更新を担う。"""

    back_to_home_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()
        self._sync_slider_label()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(16)

        header = QHBoxLayout()
        header.setSpacing(12)
        self.btn_back_home = QPushButton("← ホーム")
        self.btn_back_home.setMinimumHeight(40)
        self.btn_back_home.clicked.connect(
            lambda checked=False: self.back_to_home_requested.emit(),
        )
        header.addWidget(self.btn_back_home, stretch=0)

        title_box = QVBoxLayout()
        title = QLabel("PDF → JPEG")
        title.setFont(make_app_font(24, bold=True))
        subtitle = QLabel("単一PDFの全ページを JPEG として書き出します")
        subtitle.setFont(make_app_font(13))
        subtitle.setStyleSheet("color: #475569;")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box, stretch=1)
        root.addLayout(header)

        body = QGridLayout()
        body.setHorizontalSpacing(16)
        body.setVerticalSpacing(16)
        body.setColumnStretch(0, 5)
        body.setColumnStretch(1, 4)
        root.addLayout(body, stretch=1)

        self.input_group = QGroupBox("入力PDFとプレビュー")
        input_layout = QVBoxLayout(self.input_group)
        input_layout.setSpacing(12)

        input_row = QHBoxLayout()
        input_row.setSpacing(8)
        self.txt_selected_pdf = QLineEdit()
        self.txt_selected_pdf.setReadOnly(True)
        self.txt_selected_pdf.setPlaceholderText("変換対象の PDF を選択してください")
        self.btn_choose_pdf = QPushButton("PDFを選択")
        self.btn_choose_pdf.setMinimumHeight(38)
        input_row.addWidget(self.txt_selected_pdf, stretch=1)
        input_row.addWidget(self.btn_choose_pdf)
        input_layout.addLayout(input_row)

        self.lbl_drop_hint = QLabel("PDF をプレビュー領域へドラッグ&ドロップして選択できます")
        self.lbl_drop_hint.setFont(make_app_font(12))
        self.lbl_drop_hint.setStyleSheet("color: #64748b;")
        input_layout.addWidget(self.lbl_drop_hint)

        self.preview_label = PreviewDropLabel()
        self.preview_label.setObjectName("pdf_to_jpeg_preview")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumSize(280, 360)
        self.preview_label.setStyleSheet(
            "QLabel {"
            " background-color: #f8fafc;"
            " border: 1px solid #cbd5e1;"
            " border-radius: 12px;"
            " color: #475569;"
            " padding: 12px;"
            "}"
        )
        self.preview_label.setFont(make_app_font(12))
        self.preview_label.setText("PDFを選択すると\n先頭ページプレビューを表示します")
        input_layout.addWidget(self.preview_label, stretch=1)
        body.addWidget(self.input_group, 0, 0, 2, 1)

        self.settings_group = QGroupBox("変換設定")
        settings_layout = QVBoxLayout(self.settings_group)
        settings_layout.setSpacing(14)

        quality_row = QHBoxLayout()
        quality_row.setSpacing(8)
        self.lbl_quality_title = QLabel("JPEG品質")
        self.lbl_quality_title.setFont(make_app_font(12, bold=True))
        self.sld_jpeg_quality = QSlider(Qt.Orientation.Horizontal)
        self.sld_jpeg_quality.setRange(10, 100)
        self.sld_jpeg_quality.setValue(90)
        self.sld_jpeg_quality.valueChanged.connect(self._sync_slider_label)
        self.lbl_jpeg_quality = QLabel()
        self.lbl_jpeg_quality.setMinimumWidth(40)
        self.lbl_jpeg_quality.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        quality_row.addWidget(self.lbl_quality_title)
        quality_row.addWidget(self.sld_jpeg_quality, stretch=1)
        quality_row.addWidget(self.lbl_jpeg_quality)
        settings_layout.addLayout(quality_row)

        self.lbl_note = QLabel()
        self.lbl_note.setWordWrap(True)
        self.lbl_note.setFont(make_app_font(11))
        self.lbl_note.setStyleSheet("color: #7c2d12;")
        settings_layout.addWidget(self.lbl_note)
        settings_layout.addStretch(1)
        body.addWidget(self.settings_group, 0, 1)

        self.progress_group = QGroupBox("出力と進捗")
        progress_layout = QVBoxLayout(self.progress_group)
        progress_layout.setSpacing(12)

        output_row = QHBoxLayout()
        output_row.setSpacing(8)
        self.txt_output_dir = QLineEdit()
        self.txt_output_dir.setReadOnly(True)
        self.txt_output_dir.setPlaceholderText("保存先フォルダを選択してください")
        self.btn_choose_output = QPushButton("保存先を選択")
        self.btn_choose_output.setMinimumHeight(38)
        output_row.addWidget(self.txt_output_dir, stretch=1)
        output_row.addWidget(self.btn_choose_output)
        progress_layout.addLayout(output_row)

        self.lbl_output_detail = QLabel("出力先サブフォルダ: 保存先フォルダを選択してください")
        self.lbl_output_detail.setWordWrap(True)
        self.lbl_output_detail.setStyleSheet("color: #64748b;")
        self.lbl_output_detail.setFont(make_app_font(11))
        progress_layout.addWidget(self.lbl_output_detail)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar)

        self.lbl_progress = QLabel("待機中")
        self.lbl_progress.setFont(make_app_font(12, bold=True))
        self.lbl_summary = QLabel("成功: 0ページ / 失敗: 0ページ")
        self.lbl_summary.setFont(make_app_font(11))
        progress_layout.addWidget(self.lbl_progress)
        progress_layout.addWidget(self.lbl_summary)

        self.btn_execute = QPushButton("JPEG書き出しを実行")
        self.btn_execute.setMinimumHeight(48)
        self.btn_execute.setFont(make_app_font(16, bold=True))
        self.btn_execute.setStyleSheet(
            "QPushButton { background-color: #0f766e; color: white; border-radius: 8px; }"
            "QPushButton:disabled { background-color: #94a3b8; color: #e2e8f0; }"
        )
        progress_layout.addWidget(self.btn_execute)
        progress_layout.addStretch(1)
        body.addWidget(self.progress_group, 1, 1)

    def set_presenter(self, presenter: Any) -> None:
        self.btn_choose_pdf.clicked.connect(presenter.choose_pdf_file)
        self.preview_label.paths_dropped.connect(presenter.handle_dropped_paths)
        self.sld_jpeg_quality.valueChanged.connect(presenter.set_jpeg_quality)
        self.btn_choose_output.clicked.connect(presenter.choose_output_directory)
        self.btn_execute.clicked.connect(presenter.execute_conversion)

    def update_ui(self, state: PdfToJpegUiState) -> None:
        self._apply_slider_value(self.sld_jpeg_quality, state.jpeg_quality)
        self._sync_slider_label()

        self.txt_selected_pdf.setText(state.selected_pdf_text)
        self.txt_output_dir.setText(state.output_dir_text)
        self.lbl_output_detail.setText(state.output_detail_text)
        self.lbl_note.setText(state.note_text)
        self.progress_bar.setValue(state.progress_value)
        self.lbl_progress.setText(state.progress_text)
        self.lbl_summary.setText(state.summary_text)

        self.btn_back_home.setEnabled(state.can_back_home)
        self.btn_choose_pdf.setEnabled(state.can_choose_pdf)
        self.btn_choose_output.setEnabled(state.can_choose_output)
        self.btn_execute.setEnabled(state.can_execute)
        self.sld_jpeg_quality.setEnabled(state.can_edit_quality)
        self.preview_label.setAcceptDrops(not state.is_running)

        self._apply_preview(state.preview_png_bytes, state.preview_text)

    def get_preview_size(self) -> tuple[int, int]:
        size = self.preview_label.contentsRect().size()
        return max(1, size.width()), max(1, size.height())

    def _sync_slider_label(self) -> None:
        self.lbl_jpeg_quality.setText(str(self.sld_jpeg_quality.value()))

    def _apply_slider_value(self, slider: QSlider, value: int) -> None:
        if slider.value() == value:
            return
        blocked = slider.blockSignals(True)
        slider.setValue(value)
        slider.blockSignals(blocked)

    def _apply_preview(self, png_bytes: bytes | None, text: str) -> None:
        if png_bytes:
            pixmap = QPixmap()
            if pixmap.loadFromData(png_bytes, "PNG"):
                scaled = pixmap.scaled(
                    self.preview_label.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self.preview_label.setPixmap(scaled)
                self.preview_label.setText("")
                return

        self.preview_label.setPixmap(QPixmap())
        self.preview_label.setText(text)