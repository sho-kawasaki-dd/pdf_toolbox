from model.compress.compression_processor import CompressionProcessor
from model.compress.compression_session import CompressionCandidate, CompressionJob, CompressionSession
from model.compress.compression_dispatch import CompressionRequest, compress_pdf
from model.compress.ghostscript_compressor import compress_pdf_with_ghostscript
from model.compress.native_compressor import (
    compress_pdf as compress_pdf_native,
    compress_pdf_lossless,
    compress_pdf_lossy,
    compress_png_bytes,
    is_pngquant_available,
)

__all__ = [
    "CompressionCandidate",
    "CompressionJob",
    "CompressionSession",
    "CompressionRequest",
    "CompressionProcessor",
    "compress_pdf",
    "compress_pdf_native",
    "compress_pdf_with_ghostscript",
    "compress_pdf_lossy",
    "compress_pdf_lossless",
    "compress_png_bytes",
    "is_pngquant_available",
]