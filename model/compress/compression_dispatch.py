from __future__ import annotations

"""圧縮エンジンのディスパッチ層。"""

from dataclasses import dataclass, field
from pathlib import Path

from model.compress.ghostscript_compressor import compress_pdf_with_ghostscript
from model.compress.native_compressor import CompressionMetrics, compress_pdf as compress_pdf_native
from model.compress.settings import (
    PDF_ALLOWED_ENGINES,
    PDF_COMPRESSION_ENGINE_GHOSTSCRIPT,
    PDF_COMPRESSION_ENGINE_NATIVE,
    PDF_GHOSTSCRIPT_CUSTOM_DPI_DEFAULT,
    PDF_GHOSTSCRIPT_POSTPROCESS_DEFAULT,
    PDF_GHOSTSCRIPT_PRESET_DEFAULT,
    PDF_LOSSLESS_OPTIONS_DEFAULT,
    PDF_LOSSY_DPI_DEFAULT,
    PDF_LOSSY_JPEG_QUALITY_DEFAULT,
    PDF_LOSSY_PNG_QUALITY_DEFAULT,
    PNGQUANT_DEFAULT_SPEED,
)


@dataclass(frozen=True, slots=True)
class CompressionRequest:
    engine: str = PDF_COMPRESSION_ENGINE_NATIVE
    mode: str = "both"
    target_dpi: int = PDF_LOSSY_DPI_DEFAULT
    jpeg_quality: int = PDF_LOSSY_JPEG_QUALITY_DEFAULT
    png_quality: int = PDF_LOSSY_PNG_QUALITY_DEFAULT
    pngquant_speed: int = PNGQUANT_DEFAULT_SPEED
    lossless_options: dict[str, bool] = field(default_factory=lambda: dict(PDF_LOSSLESS_OPTIONS_DEFAULT))
    ghostscript_preset: str = PDF_GHOSTSCRIPT_PRESET_DEFAULT
    ghostscript_custom_dpi: int = PDF_GHOSTSCRIPT_CUSTOM_DPI_DEFAULT
    ghostscript_use_pikepdf_postprocess: bool = PDF_GHOSTSCRIPT_POSTPROCESS_DEFAULT


def compress_pdf(
    input_path: str | Path,
    output_path: str | Path,
    *,
    request: CompressionRequest | None = None,
    engine: str = PDF_COMPRESSION_ENGINE_NATIVE,
    mode: str = "both",
    target_dpi: int = PDF_LOSSY_DPI_DEFAULT,
    jpeg_quality: int = PDF_LOSSY_JPEG_QUALITY_DEFAULT,
    png_quality: int = PDF_LOSSY_PNG_QUALITY_DEFAULT,
    pngquant_speed: int = PNGQUANT_DEFAULT_SPEED,
    lossless_options: dict[str, bool] | None = None,
    ghostscript_preset: str = PDF_GHOSTSCRIPT_PRESET_DEFAULT,
    ghostscript_custom_dpi: int = PDF_GHOSTSCRIPT_CUSTOM_DPI_DEFAULT,
    ghostscript_use_pikepdf_postprocess: bool = PDF_GHOSTSCRIPT_POSTPROCESS_DEFAULT,
) -> tuple[bool, str, CompressionMetrics | None]:
    """要求されたエンジンに応じて圧縮実装を切り替える。"""
    effective_request = request or CompressionRequest(
        engine=engine,
        mode=mode,
        target_dpi=target_dpi,
        jpeg_quality=jpeg_quality,
        png_quality=png_quality,
        pngquant_speed=pngquant_speed,
        lossless_options=dict(PDF_LOSSLESS_OPTIONS_DEFAULT if lossless_options is None else lossless_options),
        ghostscript_preset=ghostscript_preset,
        ghostscript_custom_dpi=ghostscript_custom_dpi,
        ghostscript_use_pikepdf_postprocess=ghostscript_use_pikepdf_postprocess,
    )
    selected_engine = effective_request.engine
    if selected_engine not in PDF_ALLOWED_ENGINES:
        raise ValueError(f"Unsupported compression engine: {selected_engine}")

    if selected_engine == PDF_COMPRESSION_ENGINE_GHOSTSCRIPT:
        return compress_pdf_with_ghostscript(
            input_path,
            output_path,
            preset=effective_request.ghostscript_preset,
            custom_dpi=effective_request.ghostscript_custom_dpi,
            run_lossless_postprocess=effective_request.ghostscript_use_pikepdf_postprocess,
            lossless_options=effective_request.lossless_options,
        )

    return compress_pdf_native(
        input_path,
        output_path,
        mode=effective_request.mode,
        target_dpi=effective_request.target_dpi,
        jpeg_quality=effective_request.jpeg_quality,
        png_quality=effective_request.png_quality,
        pngquant_speed=effective_request.pngquant_speed,
        lossless_options=effective_request.lossless_options,
    )