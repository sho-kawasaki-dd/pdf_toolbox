from __future__ import annotations

"""PyMuPDF と pikepdf を使ったネイティブ PDF 圧縮。

このモジュールは公開 API を小さく保ち、低レベルな画像処理の詳細は内部へ閉じ込める。
そうしておくことで、Phase 1 で安定した圧縮エンジンを先に用意でき、後続の Presenter
や View が PDF 内部実装を知らなくても呼び出せる構造になる。
"""

import io
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from PIL import Image, ImageCms

from model.external_tools import is_pngquant_available as external_pngquant_available, resolve_pngquant_executable
from model.compress.settings import (
    PDF_ALLOWED_MODES,
    PDF_LOSSLESS_OPTIONS_DEFAULT,
    PDF_LOSSY_DPI_DEFAULT,
    PDF_LOSSY_JPEG_QUALITY_DEFAULT,
    PDF_LOSSY_PNG_QUALITY_DEFAULT,
    PNGQUANT_DEFAULT_SPEED,
    PNGQUANT_TIMEOUT_SECONDS,
)


PDF_PNG_LIKE_EXTENSIONS = frozenset({"png", "bmp", "gif", "tif", "tiff"})
PDF_UNSUPPORTED_RASTER_EXTENSIONS = frozenset({"jbig2", "jpx"})


@dataclass(frozen=True, slots=True)
class CompressionMetrics:
    """圧縮前後と中間段階のファイルサイズを保持する。"""

    input_bytes: int
    lossy_output_bytes: int
    final_output_bytes: int


def _get_file_size(path: str | Path) -> int:
    """サイズ取得失敗で処理全体を落とさないための軽量ヘルパー。"""
    try:
        return Path(path).stat().st_size
    except OSError:
        return 0


def _normalize_compression_result(
    result: tuple[bool, str] | tuple[bool, str, CompressionMetrics | None],
    input_path: str | Path,
    output_path: str | Path,
    *,
    lossy_output_bytes: int | None = None,
) -> tuple[bool, str, CompressionMetrics | None]:
    """旧戻り値と新戻り値を共通形式へ正規化する。"""
    ok = bool(result[0])
    message = str(result[1])

    metrics = result[2] if len(result) >= 3 else None
    if metrics is not None or not ok:
        return ok, message, metrics

    input_bytes = _get_file_size(input_path)
    final_output_bytes = _get_file_size(output_path)
    intermediate_bytes = final_output_bytes if lossy_output_bytes is None else lossy_output_bytes
    return ok, message, CompressionMetrics(
        input_bytes=input_bytes,
        lossy_output_bytes=intermediate_bytes,
        final_output_bytes=final_output_bytes,
    )


def _import_fitz() -> tuple[Any | None, Exception | None]:
    """PyMuPDF を遅延 import する。

    import 時点でクラッシュさせるのではなく、呼び出し側が依存欠如を構造化された
    失敗として受け取れるようにするためである。これによりバッチ処理は堅牢になり、
    将来的にユーザー向けエラーメッセージへ変換しやすくなる。
    """
    try:
        import fitz as fitz_module

        return fitz_module, None
    except Exception as exc:
        return None, exc


def _import_pikepdf() -> tuple[Any | None, Exception | None]:
    """PyMuPDF と同じ理由で pikepdf も遅延 import する。"""
    try:
        import pikepdf as pikepdf_module

        return pikepdf_module, None
    except Exception as exc:
        return None, exc


def is_pngquant_available() -> bool:
    """外部コマンド pngquant が PATH 上で利用可能かを返す。

    PNG 圧縮では pngquant を優先したい一方、Python 依存だけが入っている環境でも
    機能自体は止めない必要があるため、この判定を入口に持っている。
    """
    return external_pngquant_available()


def validate_pdf_file(file_path: str | Path) -> bool:
    """ファイルシステム上の PDF 候補を軽量に検証する。

    どうせ開けない壊れた入力に対して、出力名解決やスレッド投入や後段の例外処理まで
    進めるのは無駄なので、バッチ処理のなるべく早い段階で弾くために使う。
    """
    fitz_module, _ = _import_fitz()
    if fitz_module is None:
        return False

    try:
        with fitz_module.open(str(file_path)):
            return True
    except Exception:
        return False


def validate_pdf_bytes(pdf_bytes: bytes) -> bool:
    """主に ZIP 内 PDF 向けに、メモリ上の PDF バイト列を検証する。"""
    fitz_module, _ = _import_fitz()
    if fitz_module is None:
        return False

    try:
        with fitz_module.open(stream=pdf_bytes, filetype="pdf"):
            return True
    except Exception:
        return False


def _quality_to_pngquant_range(quality: int) -> tuple[int, int]:
    """単一の品質値を pngquant の min-max 品質帯へ変換する。

    pngquant は単一値ではなく範囲を受け取るため、UI の分かりやすい 1 つの値を保ちつつ、
    内部最適化の余地も残せるように狭い範囲へ写像している。
    """
    clamped = max(0, min(100, quality))
    return max(0, clamped - 20), clamped


def _quality_to_palette_colors(quality: int) -> int:
    """Pillow フォールバック用に、PNG 品質値をパレット色数へ変換する。

    pngquant が使えない場合でも、ユーザーの品質設定と減色強度の関係が単調に保たれる
    必要があるため、この変換を明示している。
    """
    clamped = max(0, min(100, quality))
    return max(16, min(256, round(16 + (clamped / 100.0) * 240)))


def _get_pillow_resample_filter() -> Any:
    """Pillow の互換性差分を吸収した縮小フィルタを返す。"""
    if hasattr(Image, "Resampling"):
        return Image.Resampling.LANCZOS
    return getattr(cast(Any, Image), "LANCZOS")


def _open_pdf_raster_image(image_bytes: bytes) -> Image.Image:
    """PDF から抽出したラスター画像を読み込んだ Pillow 画像として返す。"""
    image = Image.open(io.BytesIO(image_bytes))
    image.load()
    return image


def _convert_cmyk_to_rgb(image: Image.Image) -> tuple[Image.Image, bool]:
    """CMYK 画像を ICC プロファイル優先で RGB へ変換する。"""
    if image.mode != "CMYK":
        return image, False

    icc_profile = image.info.get("icc_profile")
    if isinstance(icc_profile, bytes) and icc_profile:
        try:
            src_profile = ImageCms.ImageCmsProfile(io.BytesIO(icc_profile))
            dst_profile = ImageCms.createProfile("sRGB")
            converted = cast(
                Image.Image,
                ImageCms.profileToProfile(
                    image,
                    src_profile,
                    dst_profile,
                    outputMode="RGB",
                    inPlace=False,
                ),
            )
            converted.load()
            return converted, True
        except Exception:
            pass

    converted = image.convert("RGB")
    converted.load()
    return converted, True


def _pdf_image_has_transparency(image: Image.Image) -> bool:
    """Pillow 画像に有効な透過が含まれているかを返す。"""
    if "A" in image.getbands():
        try:
            alpha_min, _alpha_max = cast(tuple[int, int], image.getchannel("A").getextrema())
            return alpha_min < 255
        except Exception:
            return True

    transparency = image.info.get("transparency")
    if transparency is None:
        return False
    if isinstance(transparency, bytes):
        return any(value < 255 for value in transparency)
    return True


def _normalize_pdf_png_source_image(image: Image.Image) -> Image.Image:
    """PNG 量子化前に PDF 抽出画像の mode を安定した形へ寄せる。"""
    has_alpha = "A" in image.getbands() or "transparency" in image.info

    if image.mode in ("RGB", "RGBA", "L"):
        return image
    if image.mode == "CMYK":
        image, _converted = _convert_cmyk_to_rgb(image)
        return image
    if image.mode == "LA":
        return image.convert("RGBA")
    if image.mode == "P":
        return image.convert("RGBA" if has_alpha else "RGB")
    return image.convert("RGBA" if has_alpha else "RGB")


def _normalize_pdf_soft_mask(mask_image: Image.Image, size: tuple[int, int]) -> Image.Image:
    """soft mask を base image と同じサイズの L 画像へ揃える。"""
    if mask_image.size != size:
        mask_image = mask_image.resize(size, _get_pillow_resample_filter())
    if mask_image.mode != "L":
        mask_image = mask_image.convert("L")
    return mask_image


def _load_pdf_raster_image_with_soft_mask(document: Any, base_image: dict[str, Any]) -> tuple[Image.Image, bool]:
    """PDF 画像本体と optional soft mask を 1 枚の Pillow 画像へ再構成する。"""
    image = _open_pdf_raster_image(cast(bytes, base_image["image"]))
    image, _converted = _convert_cmyk_to_rgb(image)
    smask_xref = base_image.get("smask", 0)
    if not isinstance(smask_xref, int) or smask_xref <= 0:
        return image, _pdf_image_has_transparency(image)

    soft_mask = document.extract_image(smask_xref)
    if not soft_mask:
        return image, _pdf_image_has_transparency(image)

    try:
        mask_image = _open_pdf_raster_image(cast(bytes, soft_mask["image"]))
        alpha_mask = _normalize_pdf_soft_mask(mask_image, image.size)
        if image.mode != "RGBA":
            image = image.convert("RGBA")
        image.putalpha(alpha_mask)
        return image, _pdf_image_has_transparency(image)
    except Exception:
        return image, _pdf_image_has_transparency(image)


def _save_as_jpeg(image: Image.Image, quality: int) -> bytes:
    """必要ならアルファを潰したうえで JPEG として保存する。

    JPEG は透過を持てないため、透明画像は先に合成する必要がある。背景色を白にしている
    のは、一般的な業務 PDF で最も違和感が少なく、透過縁に暗いにじみが出にくいためである。
    """
    image, _converted = _convert_cmyk_to_rgb(image)

    if image.mode in ("RGBA", "LA", "PA", "P"):
        if image.mode == "P":
            image = image.convert("RGBA")
        if "A" in image.mode:
            background = Image.new("RGB", image.size, (255, 255, 255))
            background.paste(image, mask=image.split()[-1])
            image = background
    elif image.mode != "RGB":
        image = image.convert("RGB")

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=max(1, min(100, quality)), optimize=True)
    return buffer.getvalue()


def _compress_png_with_pngquant(png_bytes: bytes, quality: int, speed: int) -> bytes:
    """一時ファイル経由で pngquant による PNG 圧縮を行う。

    pngquant は CLI ツールなので、Windows でも素直に動かせる移植性の高い接続方法は
    一時ファイルを介した round-trip になる。シェル依存の処理も持ち込まずに済む。
    """
    pngquant_executable = shutil.which("pngquant")
    if pngquant_executable is None:
        resolved_pngquant = resolve_pngquant_executable()
        if resolved_pngquant is not None:
            pngquant_executable = str(resolved_pngquant.path)

    if pngquant_executable is None:
        raise RuntimeError("pngquant not found")

    quality_min, quality_max = _quality_to_pngquant_range(quality)
    clamped_speed = max(1, min(11, speed))
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    with tempfile.TemporaryDirectory() as temp_dir:
        input_path = Path(temp_dir) / "input.png"
        output_path = Path(temp_dir) / "output.png"
        input_path.write_bytes(png_bytes)

        completed = subprocess.run(
            [
                pngquant_executable,
                "--force",
                "--output",
                str(output_path),
                f"--quality={quality_min}-{quality_max}",
                f"--speed={clamped_speed}",
                str(input_path),
            ],
            check=False,
            cwd=temp_dir,
            timeout=PNGQUANT_TIMEOUT_SECONDS,
            creationflags=creation_flags,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        if completed.returncode != 0 or not output_path.exists() or output_path.stat().st_size <= 0:
            raise RuntimeError(completed.stderr.decode("utf-8", errors="ignore") or "pngquant failed")

        return output_path.read_bytes()


def _compress_png_with_pillow(png_bytes: bytes, quality: int) -> bytes:
    """Pillow の減色を使った PNG 圧縮フォールバック。

    この経路は依存を極力少なく保つことが目的で、圧縮性能は pngquant に劣っても、
    Python 環境だけで機能を継続できることを優先している。
    """
    with Image.open(io.BytesIO(png_bytes)) as image:
        image.load()
        colors = _quality_to_palette_colors(quality)

        if image.mode in ("RGBA", "LA"):
            working_image = image.convert("RGBA").quantize(colors=colors)
        elif image.mode == "P":
            working_image = image.quantize(colors=colors)
        else:
            working_image = image.convert("RGB").quantize(colors=colors)

        buffer = io.BytesIO()
        working_image.save(buffer, format="PNG", optimize=True, compress_level=9)
        return buffer.getvalue()


def compress_png_bytes(
    png_bytes: bytes,
    quality: int = PDF_LOSSY_PNG_QUALITY_DEFAULT,
    speed: int = PNGQUANT_DEFAULT_SPEED,
) -> bytes:
    """PNG バイト列を圧縮する。まず pngquant を試し、失敗時は Pillow に落とす。

    呼び出し側はどのバックエンドが実際に使われたかを意識しなくてよい。フォールバック
    をここに閉じ込めることで、PDF 圧縮パイプライン全体をバックエンド非依存に保てる。
    """
    if is_pngquant_available():
        try:
            # 画像単位で pngquant が失敗してもバッチ全体は継続したいので、
            # ここでは例外を表に出さず Pillow へ降格する。
            return _compress_png_with_pngquant(png_bytes, quality, speed)
        except Exception:
            pass
    return _compress_png_with_pillow(png_bytes, quality)


def _resize_image_if_needed(image: Image.Image, effective_dpi: float, target_dpi: int) -> tuple[Image.Image, bool, tuple[int, int]]:
    """実効 DPI が目標値を超える場合だけ画像を縮小する。

    すでに十分小さい画像をさらに縮小しても、サイズ低減の見返りなしに画質だけが落ちる。
    そのため、必要なときだけダウンサンプリングする。
    """
    if effective_dpi <= target_dpi:
        return image, False, image.size

    scale = target_dpi / effective_dpi
    new_width = max(1, int(image.width * scale))
    new_height = max(1, int(image.height * scale))

    return image.resize((new_width, new_height), _get_pillow_resample_filter()), True, (new_width, new_height)


def _encode_replacement_image(
    image: Image.Image,
    image_ext: str,
    jpeg_quality: int,
    png_quality: int,
    pngquant_speed: int,
    *,
    preserve_as_png: bool = False,
) -> tuple[bytes, str]:
    """置換画像を、内容に応じて適切な圧縮経路でエンコードする。

    本来的に可逆寄りのラスタ形式は PNG 系統の経路へ残す。そうすることで、
    ベタ塗りや透過を不要に JPEG 化してアーティファクトを増やすのを避ける。
    """
    if preserve_as_png or image_ext in PDF_PNG_LIKE_EXTENSIONS:
        buffer = io.BytesIO()
        image = _normalize_pdf_png_source_image(image)
        image.save(buffer, format="PNG")
        return compress_png_bytes(buffer.getvalue(), png_quality, pngquant_speed), "PNG"

    return _save_as_jpeg(image, jpeg_quality), "JPEG"


def compress_pdf_lossy(
    input_path: str | Path,
    output_path: str | Path,
    target_dpi: int = PDF_LOSSY_DPI_DEFAULT,
    jpeg_quality: int = PDF_LOSSY_JPEG_QUALITY_DEFAULT,
    png_quality: int = PDF_LOSSY_PNG_QUALITY_DEFAULT,
    pngquant_speed: int = PNGQUANT_DEFAULT_SPEED,
) -> tuple[bool, str, CompressionMetrics | None]:
    """PyMuPDF を使って PDF 内のラスタ画像を圧縮する。

    この関数は意図的に保守的で、新しい画像バイト列が元より小さい場合にだけ置換する。
    既に最適化された画像を再圧縮すると、かえって肥大化することがあるためである。
    """
    input_file = Path(input_path)
    output_file = Path(output_path)

    fitz_module, fitz_error = _import_fitz()
    if fitz_module is None:
        return False, f"Lossy compression failed: {input_file.name} (PyMuPDF unavailable: {fitz_error})", None

    try:
        with fitz_module.open(str(input_file)) as document:
            replaced_count = 0
            processed_xrefs: set[int] = set()

            for page_index in range(len(document)):
                page = document[page_index]
                for image_info in page.get_image_info(xrefs=True):
                    xref = image_info.get("xref", 0)
                    if not isinstance(xref, int) or xref <= 0 or xref in processed_xrefs:
                        continue

                    # 同じ画像オブジェクトが複数ページで再利用されることがあるため、
                    # xref 単位で追跡して重複再圧縮を避ける。これにより無駄な処理が減り、
                    # 出力も決定的になる。
                    processed_xrefs.add(xref)
                    bbox = image_info.get("bbox")
                    if bbox is None:
                        continue

                    rect = fitz_module.Rect(bbox)
                    if rect.width <= 0 or rect.height <= 0:
                        continue

                    extracted = document.extract_image(xref)
                    if not extracted:
                        continue

                    image_bytes = extracted["image"]
                    image_ext = str(extracted.get("ext", "")).lower()
                    if image_ext in PDF_UNSUPPORTED_RASTER_EXTENSIONS:
                        # これらは特殊化された画像形式であり、Pillow 経由で round-trip すると
                        # 破損や肥大化のリスクが高いため触らない。
                        continue

                    try:
                        pil_image, has_transparency = _load_pdf_raster_image_with_soft_mask(document, extracted)
                        effective_dpi_x = pil_image.width / (rect.width / 72.0)
                        effective_dpi_y = pil_image.height / (rect.height / 72.0)
                        effective_dpi = max(effective_dpi_x, effective_dpi_y)
                        working_image, _, _ = _resize_image_if_needed(pil_image, effective_dpi, target_dpi)
                        replacement_bytes, _ = _encode_replacement_image(
                            working_image,
                            image_ext,
                            jpeg_quality,
                            png_quality,
                            pngquant_speed,
                            preserve_as_png=image_ext in PDF_PNG_LIKE_EXTENSIONS or has_transparency,
                        )
                    except Exception:
                        # 一部画像が壊れていても PDF 全体のバッチを落とさないことを優先する。
                        # MVP では資産ごとの完全性より、バッチ全体の継続性が重要である。
                        continue

                    if len(replacement_bytes) >= len(image_bytes):
                        # 再圧縮が得にならないなら元画像を残す。ユーザーが欲しいのは
                        # 任意の再エンコードではなく、サイズ削減だからである。
                        continue

                    page.replace_image(xref, stream=replacement_bytes)
                    replaced_count += 1

            document.save(str(output_file), garbage=4, deflate=True)

        output_bytes = _get_file_size(output_file)
        return True, (
            f"Lossy compression completed: {input_file.name} "
            f"(replaced_images={replaced_count}, dpi={target_dpi}, "
            f"jpeg_quality={jpeg_quality}, png_quality={png_quality})"
        ), CompressionMetrics(
            input_bytes=_get_file_size(input_file),
            lossy_output_bytes=output_bytes,
            final_output_bytes=output_bytes,
        )
    except Exception as exc:
        return False, f"Lossy compression failed: {input_file.name} ({exc})", None


def compress_pdf_lossless(
    input_path: str | Path,
    output_path: str | Path,
    options: dict[str, bool] | None = None,
) -> tuple[bool, str, CompressionMetrics | None]:
    """pikepdf による PDF 構造最適化を行う。

    この経路ではページ描画内容には触れず、コンテナ構造の無駄削減やメタデータ整理だけを
    担当する。見た目の内容を保ったまま軽量化したい場合のための経路である。
    """
    input_file = Path(input_path)
    output_file = Path(output_path)
    applied_options = dict(PDF_LOSSLESS_OPTIONS_DEFAULT if options is None else options)

    pikepdf_module, pikepdf_error = _import_pikepdf()
    if pikepdf_module is None:
        return False, f"Lossless compression failed: {input_file.name} (pikepdf unavailable: {pikepdf_error})", None

    try:
        with pikepdf_module.open(str(input_file)) as pdf:
            if applied_options.get("remove_unreferenced", True):
                # 未参照リソース削除は比較的低リスクで、機械生成 PDF に溜まりがちな
                # 死んだオブジェクトを減らせるため、既定で有効にしている。
                pdf.remove_unreferenced_resources()

            if applied_options.get("clean_metadata", False):
                if "/Metadata" in pdf.Root:
                    try:
                        del pdf.Root["/Metadata"]
                    except Exception:
                        try:
                            del pdf.Root.Metadata
                        except Exception:
                            pass
                if "/Info" in pdf.trailer:
                    try:
                        del pdf.trailer["/Info"]
                    except Exception:
                        # メタデータの持ち方は PDF ごとに揺れるため、除去失敗だけで
                        # 保存全体を失敗扱いにはしない。
                        pass

            object_stream_mode = (
                pikepdf_module.ObjectStreamMode.generate
                if applied_options.get("object_streams", True)
                else pikepdf_module.ObjectStreamMode.preserve
            )

            pdf.save(
                str(output_file),
                linearize=applied_options.get("linearize", True),
                object_stream_mode=object_stream_mode,
                compress_streams=True,
                recompress_flate=applied_options.get("recompress_streams", True),
            )

        return True, f"Lossless compression completed: {input_file.name} ({applied_options})", CompressionMetrics(
            input_bytes=_get_file_size(input_file),
            lossy_output_bytes=_get_file_size(input_file),
            final_output_bytes=_get_file_size(output_file),
        )
    except Exception as exc:
        return False, f"Lossless compression failed: {input_file.name} ({exc})", None


def compress_pdf(
    input_path: str | Path,
    output_path: str | Path,
    mode: str = "both",
    target_dpi: int = PDF_LOSSY_DPI_DEFAULT,
    jpeg_quality: int = PDF_LOSSY_JPEG_QUALITY_DEFAULT,
    png_quality: int = PDF_LOSSY_PNG_QUALITY_DEFAULT,
    pngquant_speed: int = PNGQUANT_DEFAULT_SPEED,
    lossless_options: dict[str, bool] | None = None,
) -> tuple[bool, str, CompressionMetrics | None]:
    """非可逆・可逆・両方を統一的に扱う圧縮入口。

    `both` モードでは意図的に lossy を先、lossless を後に実行する。逆順にすると、
    後で画像を書き換える前の構造を先に最適化することになり、最適化コストが無駄になりやすい。
    """
    input_file = Path(input_path)
    output_file = Path(output_path)
    selected_mode = mode if mode in PDF_ALLOWED_MODES else "both"

    if selected_mode == "lossy":
        return compress_pdf_lossy(
            input_file,
            output_file,
            target_dpi=target_dpi,
            jpeg_quality=jpeg_quality,
            png_quality=png_quality,
            pngquant_speed=pngquant_speed,
        )

    if selected_mode == "lossless":
        return compress_pdf_lossless(input_file, output_file, options=lossless_options)

    temp_output = output_file.with_suffix(output_file.suffix + ".tmp_lossy.pdf")
    try:
        lossy_ok, lossy_message, lossy_metrics = _normalize_compression_result(
            compress_pdf_lossy(
                input_file,
                temp_output,
                target_dpi=target_dpi,
                jpeg_quality=jpeg_quality,
                png_quality=png_quality,
                pngquant_speed=pngquant_speed,
            ),
            input_file,
            temp_output,
        )
        if not lossy_ok:
            # 安全に置換できる画像が無い場合や、一部画像のデコードに失敗した場合でも、
            # lossless 側だけで処理を成立させた方がユーザーにとって有益である。
            return _normalize_compression_result(
                compress_pdf_lossless(input_file, output_file, options=lossless_options),
                input_file,
                output_file,
                lossy_output_bytes=_get_file_size(input_file),
            )

        lossy_output_bytes = 0 if lossy_metrics is None else lossy_metrics.final_output_bytes
        lossless_ok, lossless_message, lossless_metrics = _normalize_compression_result(
            compress_pdf_lossless(
                temp_output,
                output_file,
                options=lossless_options,
            ),
            temp_output,
            output_file,
            lossy_output_bytes=lossy_output_bytes,
        )
        if not lossless_ok:
            # 最も重い前段処理が終わっているなら、後段失敗で全体を無にするより、
            # lossy 結果を残した方がバッチ処理としては有益である。
            shutil.copy2(temp_output, output_file)
            final_output_bytes = _get_file_size(output_file)
            return True, f"{lossy_message} / {lossless_message} (kept lossy output)", CompressionMetrics(
                input_bytes=0 if lossy_metrics is None else lossy_metrics.input_bytes,
                lossy_output_bytes=lossy_output_bytes,
                final_output_bytes=final_output_bytes,
            )

        return True, f"{lossy_message} / {lossless_message}", CompressionMetrics(
            input_bytes=0 if lossy_metrics is None else lossy_metrics.input_bytes,
            lossy_output_bytes=lossy_output_bytes,
            final_output_bytes=lossy_output_bytes if lossless_metrics is None else lossless_metrics.final_output_bytes,
        )
    finally:
        try:
            if temp_output.exists():
                temp_output.unlink()
        except Exception:
            pass