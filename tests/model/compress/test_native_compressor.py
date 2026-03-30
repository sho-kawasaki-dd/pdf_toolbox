from __future__ import annotations

import io
import subprocess
from pathlib import Path

import fitz
import pytest
from PIL import Image

from model.compress import native_compressor


def _make_png_bytes() -> bytes:
    image = Image.new("RGBA", (128, 128))
    pixels = image.load()
    for x in range(128):
        for y in range(128):
            pixels[x, y] = ((x * 9) % 255, (y * 5) % 255, ((x + y) * 7) % 255, 255)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _make_rgb_image() -> Image.Image:
    image = Image.new("RGB", (256, 256))
    pixels = image.load()
    for x in range(256):
        for y in range(256):
            pixels[x, y] = ((x * 3) % 255, (y * 5) % 255, ((x + y) * 7) % 255)
    return image


def _load_page_image(pdf_path: Path, page_index: int) -> tuple[dict[str, object], Image.Image, bool]:
    with fitz.open(str(pdf_path)) as document:
        image_infos = document[page_index].get_image_info(xrefs=True)
        assert image_infos
        xref = image_infos[0]["xref"]
        extracted = document.extract_image(xref)
        image, has_transparency = native_compressor._load_pdf_raster_image_with_soft_mask(document, extracted)
        image.load()
    return extracted, image, has_transparency


def test_compress_png_bytes_prefers_pngquant(monkeypatch) -> None:
    calls: list[tuple[int, int]] = []

    monkeypatch.setattr(native_compressor, "is_pngquant_available", lambda: True)
    monkeypatch.setattr(
        native_compressor,
        "_compress_png_with_pngquant",
        lambda payload, quality, speed: calls.append((quality, speed)) or b"pngquant",
    )

    result = native_compressor.compress_png_bytes(b"png", quality=75, speed=4)
    assert result == b"pngquant"
    assert calls == [(75, 4)]


def test_compress_png_bytes_falls_back_to_pillow(monkeypatch) -> None:
    calls: list[int] = []

    monkeypatch.setattr(native_compressor, "is_pngquant_available", lambda: False)
    monkeypatch.setattr(
        native_compressor,
        "_compress_png_with_pillow",
        lambda payload, quality: calls.append(quality) or b"pillow",
    )

    result = native_compressor.compress_png_bytes(b"png", quality=62, speed=3)
    assert result == b"pillow"
    assert calls == [62]


def test_compress_png_bytes_falls_back_when_pngquant_raises(monkeypatch) -> None:
    """pngquant 実行失敗時も Pillow フォールバックで処理継続できることを確認する。"""
    pillow_calls: list[int] = []

    monkeypatch.setattr(native_compressor, "is_pngquant_available", lambda: True)

    def raise_pngquant(_payload: bytes, _quality: int, _speed: int) -> bytes:
        raise RuntimeError("pngquant failed")

    monkeypatch.setattr(native_compressor, "_compress_png_with_pngquant", raise_pngquant)
    monkeypatch.setattr(
        native_compressor,
        "_compress_png_with_pillow",
        lambda payload, quality: pillow_calls.append(quality) or b"pillow-fallback",
    )

    result = native_compressor.compress_png_bytes(b"png", quality=55, speed=6)

    assert result == b"pillow-fallback"
    assert pillow_calls == [55]


def test_compress_png_with_pngquant_uses_resolved_path_and_safety_options(monkeypatch) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(native_compressor.shutil, "which", lambda command: "C:/tools/pngquant.exe" if command == "pngquant" else None)

    def fake_run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        captured["args"] = args
        captured["kwargs"] = kwargs

        output_path = Path(args[args.index("--output") + 1])
        output_path.write_bytes(b"optimized")
        return subprocess.CompletedProcess(args=args, returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr(native_compressor.subprocess, "run", fake_run)

    result = native_compressor._compress_png_with_pngquant(_make_png_bytes(), quality=74, speed=8)

    assert result == b"optimized"
    assert captured["args"][0] == "C:/tools/pngquant.exe"
    assert captured["kwargs"]["timeout"] == native_compressor.PNGQUANT_TIMEOUT_SECONDS
    assert Path(captured["kwargs"]["cwd"]) == Path(captured["args"][3]).parent
    assert captured["kwargs"]["creationflags"] == getattr(subprocess, "CREATE_NO_WINDOW", 0)


def test_compress_png_with_pngquant_rejects_empty_output(monkeypatch) -> None:
    monkeypatch.setattr(native_compressor.shutil, "which", lambda command: "C:/tools/pngquant.exe" if command == "pngquant" else None)

    def fake_run(args: list[str], **_kwargs: object) -> subprocess.CompletedProcess[bytes]:
        output_path = Path(args[args.index("--output") + 1])
        output_path.write_bytes(b"")
        return subprocess.CompletedProcess(args=args, returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr(native_compressor.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="pngquant failed"):
        native_compressor._compress_png_with_pngquant(_make_png_bytes(), quality=65, speed=3)


def test_jpeg_quality_changes_output_size() -> None:
    image = _make_rgb_image()
    low_quality = native_compressor._save_as_jpeg(image, 25)
    high_quality = native_compressor._save_as_jpeg(image, 90)

    assert len(low_quality) < len(high_quality)


def test_png_quality_maps_to_more_colors() -> None:
    assert native_compressor._quality_to_palette_colors(20) < native_compressor._quality_to_palette_colors(80)


def test_load_pdf_raster_image_with_soft_mask_reconstructs_alpha(image_pdf: Path) -> None:
    extracted, image, has_transparency = _load_page_image(image_pdf, 1)

    assert extracted.get("smask", 0)
    assert has_transparency is True
    assert "A" in image.getbands()
    alpha_min, alpha_max = image.getchannel("A").getextrema()
    assert alpha_min < 255
    assert alpha_max == 255


def test_compress_pdf_lossless_applies_options(sample_pdf: Path, tmp_path: Path, monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakePdf:
        def __init__(self) -> None:
            self.Root = {"/Metadata": "meta"}
            self.trailer = {"/Info": "info"}
            self.removed_unreferenced = False

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def remove_unreferenced_resources(self) -> None:
            self.removed_unreferenced = True

        def save(self, output_path: str, **kwargs) -> None:
            captured["output_path"] = output_path
            captured.update(kwargs)
            Path(output_path).write_bytes(b"pdf")

    class FakePikePdfModule:
        class ObjectStreamMode:
            generate = "generate"
            preserve = "preserve"

        @staticmethod
        def open(_path: str) -> FakePdf:
            return FakePdf()

    monkeypatch.setattr(native_compressor, "_import_pikepdf", lambda: (FakePikePdfModule, None))

    output_path = tmp_path / "lossless.pdf"
    ok, _message, metrics = native_compressor.compress_pdf_lossless(
        sample_pdf,
        output_path,
        options={
            "linearize": False,
            "object_streams": False,
            "recompress_streams": False,
            "remove_unreferenced": True,
            "clean_metadata": True,
        },
    )

    assert ok is True
    assert captured["output_path"] == str(output_path)
    assert captured["linearize"] is False
    assert captured["object_stream_mode"] == "preserve"
    assert captured["recompress_flate"] is False
    assert metrics is not None
    assert metrics.input_bytes == sample_pdf.stat().st_size
    assert metrics.lossy_output_bytes == sample_pdf.stat().st_size
    assert metrics.final_output_bytes == output_path.stat().st_size


def test_compress_pdf_lossy_creates_output(image_pdf: Path, tmp_path: Path) -> None:
    output_path = tmp_path / "compressed.pdf"
    ok, message, metrics = native_compressor.compress_pdf_lossy(
        image_pdf,
        output_path,
        target_dpi=96,
        jpeg_quality=40,
        png_quality=40,
    )

    assert ok is True
    assert output_path.exists()
    assert "jpeg_quality=40" in message
    assert "png_quality=40" in message
    assert metrics is not None
    assert metrics.input_bytes == image_pdf.stat().st_size
    assert metrics.lossy_output_bytes == output_path.stat().st_size
    assert metrics.final_output_bytes == output_path.stat().st_size


def test_compress_pdf_lossy_passes_transparency_to_png_encoder(
    image_pdf: Path,
    tmp_path: Path,
    monkeypatch,
) -> None:
    observed_transparency: list[bool] = []
    original_compress_png_bytes = native_compressor.compress_png_bytes

    def recording_compress_png_bytes(png_bytes: bytes, quality: int, speed: int) -> bytes:
        with Image.open(io.BytesIO(png_bytes)) as image:
            image.load()
            observed_transparency.append(native_compressor._pdf_image_has_transparency(image))
        return original_compress_png_bytes(png_bytes, quality, speed)

    monkeypatch.setattr(native_compressor, "compress_png_bytes", recording_compress_png_bytes)

    output_path = tmp_path / "transparent-compressed.pdf"
    ok, _message, _metrics = native_compressor.compress_pdf_lossy(
        image_pdf,
        output_path,
        target_dpi=96,
        jpeg_quality=40,
        png_quality=40,
    )

    assert ok is True
    assert output_path.exists()
    assert any(observed_transparency)


def test_validate_pdf_helpers(sample_pdf: Path, broken_pdf: Path) -> None:
    assert native_compressor.validate_pdf_file(sample_pdf) is True
    assert native_compressor.validate_pdf_file(broken_pdf) is False
    assert native_compressor.validate_pdf_bytes(sample_pdf.read_bytes()) is True
    assert native_compressor.validate_pdf_bytes(broken_pdf.read_bytes()) is False


def test_compress_pdf_both_mode_falls_back_to_lossless_when_lossy_fails(
    sample_pdf: Path,
    tmp_path: Path,
    monkeypatch,
) -> None:
    """both モードでは lossy 失敗時に lossless 経路だけでも出力を成立させる。"""
    calls: list[tuple[str, Path, Path]] = []

    def fake_lossy(input_path: str | Path, output_path: str | Path, **_kwargs):
        calls.append(("lossy", Path(input_path), Path(output_path)))
        return False, "lossy failed"

    def fake_lossless(input_path: str | Path, output_path: str | Path, **_kwargs):
        calls.append(("lossless", Path(input_path), Path(output_path)))
        Path(output_path).write_bytes(Path(input_path).read_bytes())
        return True, "lossless ok"

    monkeypatch.setattr(native_compressor, "compress_pdf_lossy", fake_lossy)
    monkeypatch.setattr(native_compressor, "compress_pdf_lossless", fake_lossless)

    output_path = tmp_path / "fallback.pdf"
    ok, message, metrics = native_compressor.compress_pdf(sample_pdf, output_path, mode="both")

    assert ok is True
    assert output_path.exists()
    assert "lossless ok" in message
    assert [call[0] for call in calls] == ["lossy", "lossless"]
    assert calls[1][1] == sample_pdf
    assert metrics is not None
    assert metrics.input_bytes == sample_pdf.stat().st_size
    assert metrics.lossy_output_bytes == sample_pdf.stat().st_size
    assert metrics.final_output_bytes == output_path.stat().st_size


def test_compress_pdf_both_mode_keeps_lossy_output_when_lossless_fails(
    sample_pdf: Path,
    tmp_path: Path,
    monkeypatch,
) -> None:
    """後段 lossless が失敗しても、前段 lossy 出力は残す。"""
    def fake_lossy(input_path: str | Path, output_path: str | Path, **_kwargs):
        Path(output_path).write_bytes(Path(input_path).read_bytes())
        return True, "lossy ok"

    def fake_lossless(_input_path: str | Path, _output_path: str | Path, **_kwargs):
        return False, "lossless failed"

    monkeypatch.setattr(native_compressor, "compress_pdf_lossy", fake_lossy)
    monkeypatch.setattr(native_compressor, "compress_pdf_lossless", fake_lossless)

    output_path = tmp_path / "kept-lossy.pdf"
    ok, message, metrics = native_compressor.compress_pdf(sample_pdf, output_path, mode="both")

    assert ok is True
    assert output_path.exists()
    assert "kept lossy output" in message
    assert metrics is not None
    assert metrics.input_bytes == sample_pdf.stat().st_size
    assert metrics.lossy_output_bytes == sample_pdf.stat().st_size
    assert metrics.final_output_bytes == output_path.stat().st_size