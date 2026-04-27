from __future__ import annotations

"""Ghostscript 圧縮エンジンの入口。"""

import shutil
import subprocess
from pathlib import Path
from typing import Any

from model.compress.native_compressor import (
    CompressionMetrics,
    _get_file_size,
    _import_fitz,
    compress_pdf_lossless,
)
from model.compress.settings import (
    PDF_GHOSTSCRIPT_PRESET_CUSTOM,
    PDF_GHOSTSCRIPT_PRESET_DEFAULT_PROFILE,
    PDF_GHOSTSCRIPT_PRESET_EBOOK,
    PDF_GHOSTSCRIPT_PRESET_PREPRESS,
    PDF_GHOSTSCRIPT_PRESET_PRINTER,
    PDF_GHOSTSCRIPT_PRESET_SCREEN,
)
from model.external_tools import resolve_ghostscript_executable


GHOSTSCRIPT_TIMEOUT_SECONDS = 600
GHOSTSCRIPT_BASELINE_FLAGS: tuple[str, ...] = (
    "-dNOPAUSE",
    "-dBATCH",
    "-dSAFER",
    "-dQUIET",
    "-dColorConversionStrategy=/LeaveColorUnchanged",
    "-dEmbedAllFonts=true",
    "-dSubsetFonts=true",
)
GHOSTSCRIPT_PRESET_TO_PDFSETTINGS: dict[str, str] = {
    PDF_GHOSTSCRIPT_PRESET_SCREEN: "/screen",
    PDF_GHOSTSCRIPT_PRESET_EBOOK: "/ebook",
    PDF_GHOSTSCRIPT_PRESET_PRINTER: "/printer",
    PDF_GHOSTSCRIPT_PRESET_PREPRESS: "/prepress",
    PDF_GHOSTSCRIPT_PRESET_DEFAULT_PROFILE: "/default",
}


def _document_requires_compatibility_floor(input_path: str | Path) -> bool:
    """透明画像や soft mask を含む文書では PDF 1.4 未満へ落とさない。"""
    fitz_module, _fitz_error = _import_fitz()
    if fitz_module is None:
        return False

    try:
        with fitz_module.open(str(input_path)) as document:
            for page_index in range(len(document)):
                page = document[page_index]
                try:
                    drawings = page.get_drawings()
                except Exception:
                    drawings = []

                for drawing in drawings:
                    fill_opacity = drawing.get("fill_opacity", 1.0)
                    stroke_opacity = drawing.get("stroke_opacity", 1.0)
                    if float(fill_opacity) < 1.0 or float(stroke_opacity) < 1.0:
                        return True

                for image_info in page.get_image_info(xrefs=True):
                    xref = image_info.get("xref", 0)
                    if not isinstance(xref, int) or xref <= 0:
                        continue
                    extracted = document.extract_image(xref)
                    if not extracted:
                        continue
                    smask = extracted.get("smask", 0)
                    if isinstance(smask, int) and smask > 0:
                        return True
    except Exception:
        return False

    return False


def _make_ghostscript_output_flags(*, preset: str, custom_dpi: int) -> list[str]:
    if preset == PDF_GHOSTSCRIPT_PRESET_CUSTOM:
        dpi = max(1, int(custom_dpi))
        return [
            "-dDownsampleColorImages=true",
            "-dColorImageDownsampleType=/Bicubic",
            f"-dColorImageResolution={dpi}",
            "-dDownsampleGrayImages=true",
            "-dGrayImageDownsampleType=/Bicubic",
            f"-dGrayImageResolution={dpi}",
            "-dDownsampleMonoImages=true",
            "-dMonoImageDownsampleType=/Subsample",
            f"-dMonoImageResolution={dpi}",
        ]

    pdfsettings = GHOSTSCRIPT_PRESET_TO_PDFSETTINGS.get(preset, "/ebook")
    return [f"-dPDFSETTINGS={pdfsettings}"]


def build_ghostscript_command(
    executable_path: str | Path,
    input_path: str | Path,
    output_path: str | Path,
    *,
    preset: str,
    custom_dpi: int,
) -> list[str]:
    """Ghostscript 実行コマンドを組み立てる。"""
    command = [
        str(executable_path),
        "-sDEVICE=pdfwrite",
        *GHOSTSCRIPT_BASELINE_FLAGS,
        *_make_ghostscript_output_flags(preset=preset, custom_dpi=custom_dpi),
    ]

    if _document_requires_compatibility_floor(input_path):
        command.append("-dCompatibilityLevel=1.4")

    command.extend([
        f"-sOutputFile={Path(output_path)}",
        str(input_path),
    ])
    return command


def _run_ghostscript(command: list[str], working_directory: Path) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        command,
        check=False,
        cwd=str(working_directory),
        timeout=GHOSTSCRIPT_TIMEOUT_SECONDS,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def compress_pdf_with_ghostscript(
    input_path: str | Path,
    output_path: str | Path,
    *,
    preset: str,
    custom_dpi: int,
    run_lossless_postprocess: bool,
    lossless_options: dict[str, bool] | None = None,
) -> tuple[bool, str, CompressionMetrics | None]:
    """Ghostscript による PDF 圧縮を実行し、必要なら後段 pikepdf を流す。"""
    input_file = Path(input_path)
    output_file = Path(output_path)
    applied_lossless_options = dict(lossless_options or {})

    executable = resolve_ghostscript_executable()
    if executable is None:
        return False, "Ghostscript compression failed: executable not available", None

    temp_output = output_file.with_suffix(output_file.suffix + ".tmp_ghostscript.pdf")
    ghostscript_output = temp_output if run_lossless_postprocess else output_file
    command = build_ghostscript_command(
        executable.path,
        input_file,
        ghostscript_output,
        preset=preset,
        custom_dpi=custom_dpi,
    )

    try:
        completed = _run_ghostscript(command, input_file.parent)
        if completed.returncode != 0 or not ghostscript_output.exists() or ghostscript_output.stat().st_size <= 0:
            stderr = completed.stderr.decode("utf-8", errors="ignore").strip()
            stdout = completed.stdout.decode("utf-8", errors="ignore").strip()
            error_text = stderr or stdout or f"exit code {completed.returncode}"
            return False, f"Ghostscript compression failed: {input_file.name} ({error_text})", None

        lossy_output_bytes = _get_file_size(ghostscript_output)
        if not run_lossless_postprocess:
            return True, (
                f"Ghostscript compression completed: {input_file.name} "
                f"(preset={preset}, custom_dpi={custom_dpi}, source={executable.source})"
            ), CompressionMetrics(
                input_bytes=_get_file_size(input_file),
                lossy_output_bytes=lossy_output_bytes,
                final_output_bytes=lossy_output_bytes,
            )

        lossless_ok, lossless_message, _lossless_metrics = compress_pdf_lossless(
            ghostscript_output,
            output_file,
            options=applied_lossless_options,
        )
        if not lossless_ok:
            shutil.copy2(ghostscript_output, output_file)
            final_output_bytes = _get_file_size(output_file)
            return True, (
                f"Ghostscript compression completed: {input_file.name} "
                f"(preset={preset}, custom_dpi={custom_dpi}, source={executable.source}) / "
                f"{lossless_message} (kept ghostscript output)"
            ), CompressionMetrics(
                input_bytes=_get_file_size(input_file),
                lossy_output_bytes=lossy_output_bytes,
                final_output_bytes=final_output_bytes,
            )

        final_output_bytes = _get_file_size(output_file)
        return True, (
            f"Ghostscript compression completed: {input_file.name} "
            f"(preset={preset}, custom_dpi={custom_dpi}, source={executable.source}) / {lossless_message}"
        ), CompressionMetrics(
            input_bytes=_get_file_size(input_file),
            lossy_output_bytes=lossy_output_bytes,
            final_output_bytes=final_output_bytes,
        )
    except Exception as exc:
        return False, f"Ghostscript compression failed: {input_file.name} ({exc})", None
    finally:
        try:
            if temp_output.exists():
                temp_output.unlink()
        except Exception:
            pass