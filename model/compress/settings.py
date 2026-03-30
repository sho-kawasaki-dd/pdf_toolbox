from __future__ import annotations

"""バッチ PDF 圧縮の既定設定。

ここで値を一元管理するのは、View の初期値、Presenter の状態、Model の挙動が
将来的に静かにずれていくのを防ぐためである。Phase 2 では GUI ウィジェットの
初期値も同じ定数を参照するため、このファイルは UI 非依存のまま保っている。
"""

# 対応モードを 3 つに絞っているのは、圧縮パイプラインが
# 「PyMuPDF のみ」「pikepdf のみ」「その 2 段構成」のいずれかとして
# 明確に設計されているためである。
PDF_ALLOWED_MODES: frozenset[str] = frozenset({"lossy", "lossless", "both"})

# 150 DPI は一般的な業務 PDF に対して保守的で扱いやすい既定値であり、
# 画面上の可読性を大きく崩さずに画像サイズを下げやすい。
PDF_LOSSY_DPI_DEFAULT = 150

# 既定値 75 はプロンプト要件であり、ここに集約しておくことで、
# 将来のスライダー初期値とバッチ処理既定値を確実に一致させられる。
PDF_LOSSY_JPEG_QUALITY_DEFAULT = 75
PDF_LOSSY_PNG_QUALITY_DEFAULT = 75

# これらのトグルは pikepdf の save 挙動に直接対応する。
# 既定値は比較的安全な構造最適化を有効にしつつ、メタデータ削除だけは
# 文書管理や保管用途で情報を必要とする可能性があるため明示 opt-in にしている。
PDF_LOSSLESS_OPTIONS_DEFAULT: dict[str, bool] = {
    "linearize": True,
    "object_streams": True,
    "recompress_streams": True,
    "remove_unreferenced": True,
    "clean_metadata": False,
}

# ZIP の再帰深度を制限するのは、異常に深いネストや悪意あるアーカイブによって
# バッチ処理が無制限探索になるのを防ぐためである。
ZIP_SCAN_MAX_DEPTH = 5

# pngquant の speed=3 は、純粋な処理速度よりも圧縮率をやや優先する設定である。
# デスクトップツールではベンチマーク速度より出力サイズの妥当性が重要なため、
# 既定値としてこのバランスを採用している。
PNGQUANT_DEFAULT_SPEED = 3

# 外部 CLI がハングした場合でもバッチ全体を巻き添えにしないため、
# pngquant 実行には十分に保守的なタイムアウトを設ける。
PNGQUANT_TIMEOUT_SECONDS = 300