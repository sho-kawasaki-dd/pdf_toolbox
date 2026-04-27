from __future__ import annotations

"""Ghostscript 圧縮エンジンの入口。"""

from pathlib import Path

from model.compress.native_compressor import CompressionMetrics
from model.external_tools import resolve_ghostscript_executable


def compress_pdf_with_ghostscript(
    input_path: str | Path,
    output_path: str | Path,
    *,
    preset: str,
    custom_dpi: int,
    run_lossless_postprocess: bool,
    lossless_options: dict[str, bool] | None = None,
) -> tuple[bool, str, CompressionMetrics | None]:
    """Phase 1 では Ghostscript 経路の契約だけを確立する。"""
    _input_path = Path(input_path)
    _output_path = Path(output_path)
    _lossless_options = dict(lossless_options or {})

    executable = resolve_ghostscript_executable()
    if executable is None:
        return False, "Ghostscript compression failed: executable not available", None

    return False, (
        "Ghostscript compression is not implemented yet "
        f"(source={executable.source}, preset={preset}, custom_dpi={custom_dpi}, "
        f"postprocess={run_lossless_postprocess})"
    ), None