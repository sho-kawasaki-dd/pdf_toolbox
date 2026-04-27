from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, cast

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QSlider,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from model.compress.settings import (
    PDF_COMPRESSION_ENGINE_GHOSTSCRIPT,
    PDF_COMPRESSION_ENGINE_NATIVE,
    PDF_GHOSTSCRIPT_CUSTOM_DPI_DEFAULT,
    PDF_GHOSTSCRIPT_POSTPROCESS_DEFAULT,
    PDF_GHOSTSCRIPT_PRESET_DEFAULT,
    PDF_LOSSLESS_OPTIONS_DEFAULT,
    PDF_LOSSY_DPI_DEFAULT,
    PDF_LOSSY_JPEG_QUALITY_DEFAULT,
    PDF_LOSSY_PNG_QUALITY_DEFAULT,
)
from view.font_config import make_app_font


@dataclass(slots=True)
class CompressionInputItem:
    """入力一覧 1 行ぶんの表示データ。"""

    path: str
    label: str


@dataclass(slots=True)
class CompressionUiState:
    """CompressionView を 1 回で描画更新するための状態スナップショット。"""

    input_items: list[CompressionInputItem] = field(default_factory=list)
    output_dir_text: str = "保存先フォルダを選択してください"
    progress_text: str = "待機中"
    summary_text: str = "成功: 0件 / 失敗: 0件 / スキップ: 0件"
    progress_value: int = 0

    engine: str = PDF_COMPRESSION_ENGINE_NATIVE
    mode: str = "both"
    jpeg_quality: int = PDF_LOSSY_JPEG_QUALITY_DEFAULT
    png_quality: int = PDF_LOSSY_PNG_QUALITY_DEFAULT
    dpi: int = PDF_LOSSY_DPI_DEFAULT
    ghostscript_available: bool = False
    ghostscript_status_text: str = ""
    ghostscript_preset: str = PDF_GHOSTSCRIPT_PRESET_DEFAULT
    ghostscript_custom_dpi: int = PDF_GHOSTSCRIPT_CUSTOM_DPI_DEFAULT
    ghostscript_postprocess: bool = PDF_GHOSTSCRIPT_POSTPROCESS_DEFAULT
    linearize: bool = PDF_LOSSLESS_OPTIONS_DEFAULT["linearize"]
    object_streams: bool = PDF_LOSSLESS_OPTIONS_DEFAULT["object_streams"]
    recompress_streams: bool = PDF_LOSSLESS_OPTIONS_DEFAULT["recompress_streams"]
    remove_unreferenced: bool = PDF_LOSSLESS_OPTIONS_DEFAULT["remove_unreferenced"]
    clean_metadata: bool = PDF_LOSSLESS_OPTIONS_DEFAULT["clean_metadata"]
    native_lossy_controls_enabled: bool = True
    native_lossless_controls_enabled: bool = True
    ghostscript_custom_dpi_enabled: bool = False
    ghostscript_lossless_controls_enabled: bool = False

    can_add_inputs: bool = True
    can_remove_selected: bool = False
    can_clear_inputs: bool = False
    can_choose_output: bool = True
    can_execute: bool = False
    can_edit_settings: bool = True
    can_back_home: bool = True
    is_running: bool = False


class DroppableInputList(QListWidget):
    """ローカルファイルの DnD を Presenter へ中継する一覧。"""

    paths_dropped = Signal(list)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setAlternatingRowColors(True)

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

        # URL をそのまま扱わずローカルパスへ揃えて、Presenter 側の入力判定を単純にする。
        paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        if paths:
            self.paths_dropped.emit(paths)
            event.acceptProposedAction()
            return

        super().dropEvent(event)


class CompressionView(QWidget):
    """PDF 圧縮画面のウィジェット構築と表示更新を担う。"""

    back_to_home_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._can_remove_selected = False
        self._build_ui()
        self._sync_slider_labels()

    def _build_ui(self) -> None:
        """圧縮画面のレイアウトを組み立てる。"""
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
        title = QLabel("PDF 圧縮")
        title.setFont(make_app_font(24, bold=True))
        subtitle = QLabel("複数PDF / フォルダ / ZIP / DnD に対応したバッチ圧縮")
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

        # 左カラムは入力ソース管理に専念させ、右カラムへ設定と進捗をまとめる。
        self.source_group = QGroupBox("入力ソース")
        source_layout = QVBoxLayout(self.source_group)
        source_layout.setSpacing(12)

        input_buttons = QHBoxLayout()
        input_buttons.setSpacing(8)
        self.btn_add_pdf = QPushButton("PDF追加")
        self.btn_add_folder = QPushButton("フォルダ追加")
        self.btn_add_zip = QPushButton("ZIP追加")
        self.btn_remove_selected = QPushButton("選択削除")
        self.btn_clear = QPushButton("一覧クリア")
        for button in (
            self.btn_add_pdf,
            self.btn_add_folder,
            self.btn_add_zip,
            self.btn_remove_selected,
            self.btn_clear,
        ):
            button.setMinimumHeight(38)
            input_buttons.addWidget(button)
        source_layout.addLayout(input_buttons)

        self.lbl_drop_hint = QLabel("PDF / フォルダ / ZIP をこの一覧へドラッグ&ドロップできます")
        self.lbl_drop_hint.setFont(make_app_font(12))
        self.lbl_drop_hint.setStyleSheet("color: #64748b;")
        source_layout.addWidget(self.lbl_drop_hint)

        self.input_list = DroppableInputList()
        self.input_list.setObjectName("compression_input_list")
        self.input_list.itemSelectionChanged.connect(self._update_selection_buttons)
        source_layout.addWidget(self.input_list, stretch=1)
        body.addWidget(self.source_group, 0, 0, 2, 1)

        self.settings_group = QGroupBox("圧縮設定")
        settings_layout = QVBoxLayout(self.settings_group)
        settings_layout.setSpacing(14)

        self.lbl_ghostscript_status = QLabel("")
        self.lbl_ghostscript_status.setWordWrap(True)
        self.lbl_ghostscript_status.setStyleSheet(
            "color: #9a3412; background-color: #fff7ed; border: 1px solid #fdba74; "
            "border-radius: 6px; padding: 8px;"
        )
        self.lbl_ghostscript_status.hide()
        settings_layout.addWidget(self.lbl_ghostscript_status)

        self.settings_tabs = QTabWidget()
        settings_layout.addWidget(self.settings_tabs)

        self.tab_native = QWidget()
        native_layout = QVBoxLayout(self.tab_native)
        native_layout.setSpacing(14)

        native_form = QFormLayout()
        native_form.setHorizontalSpacing(10)
        native_form.setVerticalSpacing(10)

        self.cmb_mode = QComboBox()
        self.cmb_mode.addItem("非可逆 + 可逆最適化", "both")
        self.cmb_mode.addItem("非可逆のみ", "lossy")
        self.cmb_mode.addItem("可逆最適化のみ", "lossless")
        native_form.addRow("圧縮モード", self.cmb_mode)

        self.sld_jpeg_quality = self._build_slider(10, 100, PDF_LOSSY_JPEG_QUALITY_DEFAULT)
        self.lbl_jpeg_quality = QLabel()
        native_form.addRow("JPEG品質", self._with_value_label(self.sld_jpeg_quality, self.lbl_jpeg_quality))

        self.sld_png_quality = self._build_slider(10, 100, PDF_LOSSY_PNG_QUALITY_DEFAULT)
        self.lbl_png_quality = QLabel()
        native_form.addRow("PNG品質", self._with_value_label(self.sld_png_quality, self.lbl_png_quality))

        self.sld_dpi = self._build_slider(72, 300, PDF_LOSSY_DPI_DEFAULT)
        self.lbl_dpi = QLabel()
        native_form.addRow("DPI", self._with_value_label(self.sld_dpi, self.lbl_dpi))
        native_layout.addLayout(native_form)

        self.native_options_group = self._build_lossless_options_group("native")
        native_layout.addWidget(self.native_options_group)
        native_layout.addStretch(1)
        self.settings_tabs.addTab(self.tab_native, "標準エンジン")

        self.tab_ghostscript = QWidget()
        ghostscript_layout = QVBoxLayout(self.tab_ghostscript)
        ghostscript_layout.setSpacing(14)

        ghostscript_form = QFormLayout()
        ghostscript_form.setHorizontalSpacing(10)
        ghostscript_form.setVerticalSpacing(10)

        self.cmb_ghostscript_preset = QComboBox()
        self.cmb_ghostscript_preset.addItem("画面向け (screen)", "screen")
        self.cmb_ghostscript_preset.addItem("電子文書向け (ebook)", "ebook")
        self.cmb_ghostscript_preset.addItem("印刷向け (printer)", "printer")
        self.cmb_ghostscript_preset.addItem("プリプレス向け (prepress)", "prepress")
        self.cmb_ghostscript_preset.addItem("標準設定 (default)", "default")
        self.cmb_ghostscript_preset.addItem("カスタム DPI", "custom")
        ghostscript_form.addRow("Ghostscript プリセット", self.cmb_ghostscript_preset)

        self.sld_ghostscript_dpi = self._build_slider(72, 300, PDF_GHOSTSCRIPT_CUSTOM_DPI_DEFAULT)
        self.lbl_ghostscript_dpi = QLabel()
        ghostscript_form.addRow("カスタム DPI", self._with_value_label(self.sld_ghostscript_dpi, self.lbl_ghostscript_dpi))

        self.chk_ghostscript_postprocess = QCheckBox("Ghostscript 後に pikepdf 可逆最適化を実行する")
        self.chk_ghostscript_postprocess.setChecked(PDF_GHOSTSCRIPT_POSTPROCESS_DEFAULT)
        ghostscript_form.addRow("後段処理", self.chk_ghostscript_postprocess)
        ghostscript_layout.addLayout(ghostscript_form)

        self.ghostscript_options_group = self._build_lossless_options_group("ghostscript")
        ghostscript_layout.addWidget(self.ghostscript_options_group)
        ghostscript_layout.addStretch(1)
        self.settings_tabs.addTab(self.tab_ghostscript, "Ghostscript")

        self._collect_lossless_checkboxes()
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

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar)

        self.lbl_progress = QLabel("待機中")
        self.lbl_progress.setFont(make_app_font(12, bold=True))
        self.lbl_summary = QLabel("成功: 0件 / 失敗: 0件 / スキップ: 0件")
        self.lbl_summary.setFont(make_app_font(11))
        self.lbl_summary.setWordWrap(True)
        progress_layout.addWidget(self.lbl_progress)
        progress_layout.addWidget(self.lbl_summary)

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet("color: #cbd5e1;")
        progress_layout.addWidget(divider)

        self.btn_execute = QPushButton("圧縮を実行")
        self.btn_execute.setMinimumHeight(48)
        self.btn_execute.setFont(make_app_font(16, bold=True))
        self.btn_execute.setStyleSheet(
            "QPushButton { background-color: #0f766e; color: white; border-radius: 8px; }"
            "QPushButton:disabled { background-color: #94a3b8; color: #e2e8f0; }"
        )
        progress_layout.addWidget(self.btn_execute)
        progress_layout.addStretch(1)
        body.addWidget(self.progress_group, 1, 1)

    def _build_slider(self, minimum: int, maximum: int, value: int) -> QSlider:
        """共通設定でスライダーを生成する。"""
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(minimum, maximum)
        slider.setValue(value)
        slider.valueChanged.connect(self._sync_slider_labels)
        return slider

    def _build_lossless_options_group(self, prefix: str) -> QGroupBox:
        group = QGroupBox("可逆最適化")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        linearize = QCheckBox("Web 表示用に最適化")
        linearize.setChecked(PDF_LOSSLESS_OPTIONS_DEFAULT["linearize"])
        setattr(self, f"chk_{prefix}_linearize", linearize)
        layout.addWidget(linearize)

        object_streams = QCheckBox("オブジェクトストリームを有効化")
        object_streams.setChecked(PDF_LOSSLESS_OPTIONS_DEFAULT["object_streams"])
        setattr(self, f"chk_{prefix}_object_streams", object_streams)
        layout.addWidget(object_streams)

        recompress_streams = QCheckBox("圧縮ストリームを再最適化")
        recompress_streams.setChecked(PDF_LOSSLESS_OPTIONS_DEFAULT["recompress_streams"])
        setattr(self, f"chk_{prefix}_recompress_streams", recompress_streams)
        layout.addWidget(recompress_streams)

        remove_unreferenced = QCheckBox("未参照オブジェクトを削除")
        remove_unreferenced.setChecked(PDF_LOSSLESS_OPTIONS_DEFAULT["remove_unreferenced"])
        setattr(self, f"chk_{prefix}_remove_unreferenced", remove_unreferenced)
        layout.addWidget(remove_unreferenced)

        clean_metadata = QCheckBox("メタデータを削除")
        clean_metadata.setChecked(PDF_LOSSLESS_OPTIONS_DEFAULT["clean_metadata"])
        setattr(self, f"chk_{prefix}_clean_metadata", clean_metadata)
        layout.addWidget(clean_metadata)
        return group

    def _collect_lossless_checkboxes(self) -> None:
        native_linearize = cast(QCheckBox, getattr(self, "chk_native_linearize"))
        ghostscript_linearize = cast(QCheckBox, getattr(self, "chk_ghostscript_linearize"))
        native_object_streams = cast(QCheckBox, getattr(self, "chk_native_object_streams"))
        ghostscript_object_streams = cast(QCheckBox, getattr(self, "chk_ghostscript_object_streams"))
        native_recompress_streams = cast(QCheckBox, getattr(self, "chk_native_recompress_streams"))
        ghostscript_recompress_streams = cast(QCheckBox, getattr(self, "chk_ghostscript_recompress_streams"))
        native_remove_unreferenced = cast(QCheckBox, getattr(self, "chk_native_remove_unreferenced"))
        ghostscript_remove_unreferenced = cast(QCheckBox, getattr(self, "chk_ghostscript_remove_unreferenced"))
        native_clean_metadata = cast(QCheckBox, getattr(self, "chk_native_clean_metadata"))
        ghostscript_clean_metadata = cast(QCheckBox, getattr(self, "chk_ghostscript_clean_metadata"))

        self._lossless_checkboxes_by_key = {
            "linearize": [native_linearize, ghostscript_linearize],
            "object_streams": [native_object_streams, ghostscript_object_streams],
            "recompress_streams": [native_recompress_streams, ghostscript_recompress_streams],
            "remove_unreferenced": [native_remove_unreferenced, ghostscript_remove_unreferenced],
            "clean_metadata": [native_clean_metadata, ghostscript_clean_metadata],
        }

        # 既存テストや MainWindow 互換のため、標準エンジン側を従来名でも公開する。
        self.chk_linearize = native_linearize
        self.chk_object_streams = native_object_streams
        self.chk_recompress_streams = native_recompress_streams
        self.chk_remove_unreferenced = native_remove_unreferenced
        self.chk_clean_metadata = native_clean_metadata

    def _with_value_label(self, slider: QSlider, label: QLabel) -> QWidget:
        """スライダーの右側に現在値ラベルを並べた行を作る。"""
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        label.setMinimumWidth(48)
        label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(slider, stretch=1)
        layout.addWidget(label)
        return container

    def _sync_slider_labels(self) -> None:
        """現在のスライダー値を画面上のラベルへ反映する。"""
        self.lbl_jpeg_quality.setText(str(self.sld_jpeg_quality.value()))
        self.lbl_png_quality.setText(str(self.sld_png_quality.value()))
        self.lbl_dpi.setText(str(self.sld_dpi.value()))
        self.lbl_ghostscript_dpi.setText(str(self.sld_ghostscript_dpi.value()))

    def set_presenter(self, presenter: Any) -> None:
        """View の操作シグナルを Presenter の公開メソッドへ接続する。"""
        self._presenter = presenter
        # 各 UI 要素は自前で状態変更を完結させず、必ず Presenter を経由して
        # Session と整合する形で反映させる。
        self.btn_add_pdf.clicked.connect(presenter.add_pdf_files)
        self.btn_add_folder.clicked.connect(presenter.add_folder)
        self.btn_add_zip.clicked.connect(presenter.add_zip_files)
        self.btn_remove_selected.clicked.connect(presenter.remove_selected_inputs)
        self.btn_clear.clicked.connect(presenter.clear_inputs)
        self.btn_choose_output.clicked.connect(presenter.choose_output_directory)
        self.btn_execute.clicked.connect(presenter.execute_compression)
        self.input_list.paths_dropped.connect(presenter.handle_dropped_paths)
        self.settings_tabs.currentChanged.connect(self._on_settings_tab_changed)

        self.cmb_mode.currentIndexChanged.connect(
            lambda _index: presenter.set_mode(self.cmb_mode.currentData()),
        )
        self.sld_jpeg_quality.valueChanged.connect(presenter.set_jpeg_quality)
        self.sld_png_quality.valueChanged.connect(presenter.set_png_quality)
        self.sld_dpi.valueChanged.connect(presenter.set_dpi)
        self.cmb_ghostscript_preset.currentIndexChanged.connect(
            lambda _index: presenter.set_ghostscript_preset(self.cmb_ghostscript_preset.currentData()),
        )
        self.sld_ghostscript_dpi.valueChanged.connect(presenter.set_ghostscript_custom_dpi)
        self.chk_ghostscript_postprocess.toggled.connect(presenter.set_ghostscript_postprocess_enabled)
        for key, checkboxes in self._lossless_checkboxes_by_key.items():
            for checkbox in checkboxes:
                checkbox.toggled.connect(
                    lambda checked, option_key=key: presenter.set_lossless_option(option_key, checked),
                )

    def update_ui(self, state: CompressionUiState) -> None:
        """受け取った状態スナップショットで画面全体を更新する。"""
        # 先に設定系ウィジェットを state に合わせ、そのあと一覧や文言を更新する。
        # こうしておくと、非同期ポーリングで途中状態が来ても画面の整合が取りやすい。
        self._apply_engine(state.engine, state.ghostscript_available)
        self._apply_mode(state.mode)
        self._apply_slider_value(self.sld_jpeg_quality, state.jpeg_quality)
        self._apply_slider_value(self.sld_png_quality, state.png_quality)
        self._apply_slider_value(self.sld_dpi, state.dpi)
        self._apply_ghostscript_preset(state.ghostscript_preset)
        self._apply_slider_value(self.sld_ghostscript_dpi, state.ghostscript_custom_dpi)
        self._apply_checkbox(self.chk_ghostscript_postprocess, state.ghostscript_postprocess)
        self._apply_lossless_checkbox("linearize", state.linearize)
        self._apply_lossless_checkbox("object_streams", state.object_streams)
        self._apply_lossless_checkbox("recompress_streams", state.recompress_streams)
        self._apply_lossless_checkbox("remove_unreferenced", state.remove_unreferenced)
        self._apply_lossless_checkbox("clean_metadata", state.clean_metadata)
        self._sync_slider_labels()

        self.input_list.clear()
        for item_state in state.input_items:
            # 実際の削除対象は表示文字列ではなく元パスで保持する。
            item = QListWidgetItem(item_state.label)
            item.setData(Qt.ItemDataRole.UserRole, item_state.path)
            self.input_list.addItem(item)

        self.txt_output_dir.setText(state.output_dir_text)
        self.progress_bar.setValue(state.progress_value)
        self.lbl_progress.setText(state.progress_text)
        self.lbl_summary.setText(state.summary_text)
        self.lbl_ghostscript_status.setText(state.ghostscript_status_text)
        self.lbl_ghostscript_status.setVisible(bool(state.ghostscript_status_text))

        self._can_remove_selected = state.can_remove_selected
        self.btn_add_pdf.setEnabled(state.can_add_inputs)
        self.btn_add_folder.setEnabled(state.can_add_inputs)
        self.btn_add_zip.setEnabled(state.can_add_inputs)
        self.btn_clear.setEnabled(state.can_clear_inputs)
        self.btn_choose_output.setEnabled(state.can_choose_output)
        self.btn_execute.setEnabled(state.can_execute)
        self.btn_back_home.setEnabled(state.can_back_home)

        self.settings_tabs.setEnabled(state.can_edit_settings)
        ghostscript_tab_index = self.settings_tabs.indexOf(self.tab_ghostscript)
        self.settings_tabs.setTabEnabled(ghostscript_tab_index, state.ghostscript_available)
        self.cmb_mode.setEnabled(state.can_edit_settings)
        self.sld_jpeg_quality.setEnabled(state.can_edit_settings and state.native_lossy_controls_enabled)
        self.sld_png_quality.setEnabled(state.can_edit_settings and state.native_lossy_controls_enabled)
        self.sld_dpi.setEnabled(state.can_edit_settings and state.native_lossy_controls_enabled)
        self.native_options_group.setEnabled(state.can_edit_settings and state.native_lossless_controls_enabled)
        self.cmb_ghostscript_preset.setEnabled(state.can_edit_settings and state.ghostscript_available)
        self.sld_ghostscript_dpi.setEnabled(
            state.can_edit_settings and state.ghostscript_available and state.ghostscript_custom_dpi_enabled,
        )
        self.chk_ghostscript_postprocess.setEnabled(state.can_edit_settings and state.ghostscript_available)
        self.ghostscript_options_group.setEnabled(
            state.can_edit_settings and state.ghostscript_available and state.ghostscript_lossless_controls_enabled,
        )

        self._update_selection_buttons()

    def get_selected_input_paths(self) -> list[str]:
        """一覧で選択中の入力パスだけを返す。"""
        return [item.data(Qt.ItemDataRole.UserRole) for item in self.input_list.selectedItems()]

    def _apply_mode(self, mode: str) -> None:
        """シグナルを再発火させずにモード選択を反映する。"""
        index = self.cmb_mode.findData(mode)
        if index >= 0 and index != self.cmb_mode.currentIndex():
            blocked = self.cmb_mode.blockSignals(True)
            self.cmb_mode.setCurrentIndex(index)
            self.cmb_mode.blockSignals(blocked)

    def _apply_engine(self, engine: str, ghostscript_available: bool) -> None:
        desired_index = self.settings_tabs.indexOf(self.tab_native)
        if engine == PDF_COMPRESSION_ENGINE_GHOSTSCRIPT and ghostscript_available:
            desired_index = self.settings_tabs.indexOf(self.tab_ghostscript)
        if desired_index == self.settings_tabs.currentIndex():
            return
        blocked = self.settings_tabs.blockSignals(True)
        self.settings_tabs.setCurrentIndex(desired_index)
        self.settings_tabs.blockSignals(blocked)

    def _apply_ghostscript_preset(self, preset: str) -> None:
        index = self.cmb_ghostscript_preset.findData(preset)
        if index < 0 or index == self.cmb_ghostscript_preset.currentIndex():
            return
        blocked = self.cmb_ghostscript_preset.blockSignals(True)
        self.cmb_ghostscript_preset.setCurrentIndex(index)
        self.cmb_ghostscript_preset.blockSignals(blocked)

    def _apply_slider_value(self, slider: QSlider, value: int) -> None:
        """外部状態に合わせてスライダー値を静かに更新する。"""
        if slider.value() == value:
            return
        blocked = slider.blockSignals(True)
        slider.setValue(value)
        slider.blockSignals(blocked)

    def _apply_checkbox(self, checkbox: QCheckBox, checked: bool) -> None:
        """チェックボックス状態を Presenter へ再通知せずに揃える。"""
        if checkbox.isChecked() == checked:
            return
        blocked = checkbox.blockSignals(True)
        checkbox.setChecked(checked)
        checkbox.blockSignals(blocked)

    def _apply_lossless_checkbox(self, key: str, checked: bool) -> None:
        for checkbox in self._lossless_checkboxes_by_key[key]:
            self._apply_checkbox(checkbox, checked)

    def _on_settings_tab_changed(self, index: int) -> None:
        presenter = getattr(self, "_presenter", None)
        if presenter is None:
            return
        if self.settings_tabs.widget(index) is self.tab_ghostscript:
            presenter.set_engine(PDF_COMPRESSION_ENGINE_GHOSTSCRIPT)
            return
        presenter.set_engine(PDF_COMPRESSION_ENGINE_NATIVE)

    def _update_selection_buttons(self) -> None:
        """選択状態と実行状態に応じて削除ボタンの活性を調整する。"""
        has_selection = bool(self.input_list.selectedItems())
        self.btn_remove_selected.setEnabled(self._can_remove_selected and has_selection)
