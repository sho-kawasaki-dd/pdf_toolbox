from __future__ import annotations

import subprocess
from pathlib import Path

from model.compress import ghostscript_compressor
from model.compress.native_compressor import CompressionMetrics
from model.external_tools import ResolvedExecutable


def _resolved_ghostscript(path: Path) -> ResolvedExecutable:
    return ResolvedExecutable(tool_name="ghostscript", path=path, source="bundled")


def test_build_ghostscript_command_uses_preset_and_baseline_flags(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(ghostscript_compressor, "_document_requires_compatibility_floor", lambda _path: False)

    command = ghostscript_compressor.build_ghostscript_command(
        tmp_path / "gswin64c.exe",
        tmp_path / "input.pdf",
        tmp_path / "output.pdf",
        preset="ebook",
        custom_dpi=144,
    )

    assert command[0].endswith("gswin64c.exe")
    assert "-sDEVICE=pdfwrite" in command
    assert "-dPDFSETTINGS=/ebook" in command
    assert "-dColorConversionStrategy=/LeaveColorUnchanged" in command
    assert "-dEmbedAllFonts=true" in command
    assert "-dSubsetFonts=true" in command
    assert not any(flag.startswith("-dCompatibilityLevel=") for flag in command)
    assert not any(flag.startswith("-dColorImageResolution=") for flag in command)


def test_build_ghostscript_command_for_custom_preset_uses_explicit_dpi(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(ghostscript_compressor, "_document_requires_compatibility_floor", lambda _path: False)

    command = ghostscript_compressor.build_ghostscript_command(
        tmp_path / "gswin64c.exe",
        tmp_path / "input.pdf",
        tmp_path / "output.pdf",
        preset="custom",
        custom_dpi=144,
    )

    assert "-dPDFSETTINGS=/ebook" not in command
    assert "-dColorImageResolution=144" in command
    assert "-dGrayImageResolution=144" in command
    assert "-dMonoImageResolution=144" in command


def test_build_ghostscript_command_applies_compatibility_floor_when_needed(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(ghostscript_compressor, "_document_requires_compatibility_floor", lambda _path: True)

    command = ghostscript_compressor.build_ghostscript_command(
        tmp_path / "gswin64c.exe",
        tmp_path / "input.pdf",
        tmp_path / "output.pdf",
        preset="screen",
        custom_dpi=72,
    )

    assert "-dCompatibilityLevel=1.4" in command


def test_document_requires_compatibility_floor_for_soft_mask(image_pdf: Path) -> None:
    assert ghostscript_compressor._document_requires_compatibility_floor(image_pdf) is True


def test_document_requires_compatibility_floor_false_for_plain_pdf(sample_pdf: Path) -> None:
    assert ghostscript_compressor._document_requires_compatibility_floor(sample_pdf) is False


def test_compress_pdf_with_ghostscript_writes_output(monkeypatch, sample_pdf: Path, tmp_path: Path) -> None:
    output_path = tmp_path / "ghostscript.pdf"
    executable_path = tmp_path / "gswin64c.exe"
    executable_path.write_bytes(b"exe")

    monkeypatch.setattr(
        ghostscript_compressor,
        "resolve_ghostscript_executable",
        lambda: _resolved_ghostscript(executable_path),
    )

    def fake_run(command: list[str], working_directory: Path) -> subprocess.CompletedProcess[bytes]:
        output_arg = next(arg for arg in command if arg.startswith("-sOutputFile="))
        Path(output_arg.split("=", 1)[1]).write_bytes(b"ghostscript-output")
        assert working_directory == sample_pdf.parent
        return subprocess.CompletedProcess(command, 0, stdout=b"", stderr=b"")

    monkeypatch.setattr(ghostscript_compressor, "_run_ghostscript", fake_run)

    ok, message, metrics = ghostscript_compressor.compress_pdf_with_ghostscript(
        sample_pdf,
        output_path,
        preset="printer",
        custom_dpi=200,
        run_lossless_postprocess=False,
    )

    assert ok is True
    assert output_path.exists()
    assert "preset=printer" in message
    assert metrics == CompressionMetrics(
        input_bytes=sample_pdf.stat().st_size,
        lossy_output_bytes=output_path.stat().st_size,
        final_output_bytes=output_path.stat().st_size,
    )


def test_compress_pdf_with_ghostscript_runs_postprocess(monkeypatch, sample_pdf: Path, tmp_path: Path) -> None:
    output_path = tmp_path / "ghostscript-post.pdf"
    executable_path = tmp_path / "gswin64c.exe"
    executable_path.write_bytes(b"exe")
    lossless_calls: list[tuple[Path, Path, dict[str, bool] | None]] = []

    monkeypatch.setattr(
        ghostscript_compressor,
        "resolve_ghostscript_executable",
        lambda: _resolved_ghostscript(executable_path),
    )

    def fake_run(command: list[str], _working_directory: Path) -> subprocess.CompletedProcess[bytes]:
        output_arg = next(arg for arg in command if arg.startswith("-sOutputFile="))
        Path(output_arg.split("=", 1)[1]).write_bytes(b"ghostscript-temp-output")
        return subprocess.CompletedProcess(command, 0, stdout=b"", stderr=b"")

    def fake_lossless(input_path: str | Path, final_output_path: str | Path, options: dict[str, bool] | None = None):
        lossless_calls.append((Path(input_path), Path(final_output_path), options))
        Path(final_output_path).write_bytes(b"postprocessed")
        return True, "lossless ok", CompressionMetrics(1, 1, 1)

    monkeypatch.setattr(ghostscript_compressor, "_run_ghostscript", fake_run)
    monkeypatch.setattr(ghostscript_compressor, "compress_pdf_lossless", fake_lossless)

    ok, message, metrics = ghostscript_compressor.compress_pdf_with_ghostscript(
        sample_pdf,
        output_path,
        preset="ebook",
        custom_dpi=150,
        run_lossless_postprocess=True,
        lossless_options={"linearize": False},
    )

    assert ok is True
    assert "lossless ok" in message
    assert len(lossless_calls) == 1
    assert lossless_calls[0][0].name.endswith(".tmp_ghostscript.pdf")
    assert lossless_calls[0][1] == output_path
    assert lossless_calls[0][2] == {"linearize": False}
    assert metrics is not None
    assert metrics.input_bytes == sample_pdf.stat().st_size
    assert metrics.lossy_output_bytes > 0
    assert metrics.final_output_bytes == output_path.stat().st_size


def test_compress_pdf_with_ghostscript_keeps_ghostscript_output_when_postprocess_fails(
    monkeypatch,
    sample_pdf: Path,
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "ghostscript-fallback.pdf"
    executable_path = tmp_path / "gswin64c.exe"
    executable_path.write_bytes(b"exe")

    monkeypatch.setattr(
        ghostscript_compressor,
        "resolve_ghostscript_executable",
        lambda: _resolved_ghostscript(executable_path),
    )

    def fake_run(command: list[str], _working_directory: Path) -> subprocess.CompletedProcess[bytes]:
        output_arg = next(arg for arg in command if arg.startswith("-sOutputFile="))
        Path(output_arg.split("=", 1)[1]).write_bytes(b"ghostscript-only")
        return subprocess.CompletedProcess(command, 0, stdout=b"", stderr=b"")

    monkeypatch.setattr(ghostscript_compressor, "_run_ghostscript", fake_run)
    monkeypatch.setattr(
        ghostscript_compressor,
        "compress_pdf_lossless",
        lambda *_args, **_kwargs: (False, "lossless failed", None),
    )

    ok, message, metrics = ghostscript_compressor.compress_pdf_with_ghostscript(
        sample_pdf,
        output_path,
        preset="ebook",
        custom_dpi=150,
        run_lossless_postprocess=True,
    )

    assert ok is True
    assert output_path.exists()
    assert "kept ghostscript output" in message
    assert metrics is not None
    assert metrics.final_output_bytes == output_path.stat().st_size