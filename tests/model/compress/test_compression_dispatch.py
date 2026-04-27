from __future__ import annotations

from pathlib import Path

import pytest

from model.compress import compression_dispatch
from model.compress.native_compressor import CompressionMetrics
from model.compress.settings import PDF_COMPRESSION_ENGINE_GHOSTSCRIPT, PDF_COMPRESSION_ENGINE_NATIVE


def test_dispatch_uses_native_engine(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    def fake_native(input_path: str | Path, output_path: str | Path, **kwargs: object):
        captured["input_path"] = Path(input_path)
        captured["output_path"] = Path(output_path)
        captured.update(kwargs)
        return True, "native", CompressionMetrics(1, 1, 1)

    monkeypatch.setattr(compression_dispatch, "compress_pdf_native", fake_native)

    ok, message, metrics = compression_dispatch.compress_pdf(
        tmp_path / "in.pdf",
        tmp_path / "out.pdf",
        engine=PDF_COMPRESSION_ENGINE_NATIVE,
        mode="lossless",
        jpeg_quality=55,
    )

    assert ok is True
    assert message == "native"
    assert metrics == CompressionMetrics(1, 1, 1)
    assert captured["mode"] == "lossless"
    assert captured["jpeg_quality"] == 55


def test_dispatch_uses_ghostscript_engine(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    def fake_ghostscript(input_path: str | Path, output_path: str | Path, **kwargs: object):
        captured["input_path"] = Path(input_path)
        captured["output_path"] = Path(output_path)
        captured.update(kwargs)
        return True, "ghostscript", CompressionMetrics(2, 2, 2)

    monkeypatch.setattr(compression_dispatch, "compress_pdf_with_ghostscript", fake_ghostscript)

    ok, message, metrics = compression_dispatch.compress_pdf(
        tmp_path / "in.pdf",
        tmp_path / "out.pdf",
        engine=PDF_COMPRESSION_ENGINE_GHOSTSCRIPT,
        ghostscript_preset="printer",
        ghostscript_custom_dpi=144,
        ghostscript_use_pikepdf_postprocess=True,
    )

    assert ok is True
    assert message == "ghostscript"
    assert metrics == CompressionMetrics(2, 2, 2)
    assert captured["preset"] == "printer"
    assert captured["custom_dpi"] == 144
    assert captured["run_lossless_postprocess"] is True


def test_dispatch_rejects_unknown_engine(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Unsupported compression engine"):
        compression_dispatch.compress_pdf(tmp_path / "in.pdf", tmp_path / "out.pdf", engine="unknown")