"""
Advanced Compression Service
Implements Brotli (Google) and Zstandard (Facebook) algorithms
20-30% better compression than gzip, used by Chrome, Facebook, Netflix
"""

import brotli
import zstandard as zstd
import gzip
import lzma
import io
from typing import Tuple, Optional
from enum import Enum

class CompressionAlgorithm(Enum):
    BROTLI = "brotli"
    ZSTANDARD = "zstd"
    GZIP = "gzip"
    LZMA = "lzma"
    NONE = "none"

class CompressionService:
    """Advanced compression with multiple algorithms"""
    
    # Compression levels
    BROTLI_QUALITY = 6  # 0-11, 6 is balanced
    ZSTD_LEVEL = 3      # 1-22, 3 is fast
    
    @staticmethod
    def compress_brotli(data: bytes, quality: int = BROTLI_QUALITY) -> bytes:
        """Compress using Brotli (Google's algorithm)"""
        return brotli.compress(data, quality=quality)
    
    @staticmethod
    def decompress_brotli(data: bytes) -> bytes:
        """Decompress Brotli data"""
        return brotli.decompress(data)
    
    @staticmethod
    def compress_zstd(data: bytes, level: int = ZSTD_LEVEL) -> bytes:
        """Compress using Zstandard (Facebook's algorithm)"""
        compressor = zstd.ZstdCompressor(level=level)
        return compressor.compress(data)
    
    @staticmethod
    def decompress_zstd(data: bytes) -> bytes:
        """Decompress Zstandard data"""
        decompressor = zstd.ZstdDecompressor()
        return decompressor.decompress(data)
    
    @staticmethod
    def compress_gzip(data: bytes, level: int = 6) -> bytes:
        """Compress using gzip"""
        return gzip.compress(data, compresslevel=level)
    
    @staticmethod
    def decompress_gzip(data: bytes) -> bytes:
        """Decompress gzip data"""
        return gzip.decompress(data)
    
    @staticmethod
    def compress_lzma(data: bytes) -> bytes:
        """Compress using LZMA (highest compression)"""
        return lzma.compress(data, preset=6)
    
    @staticmethod
    def decompress_lzma(data: bytes) -> bytes:
        """Decompress LZMA data"""
        return lzma.decompress(data)
    
    @staticmethod
    def compress(data: bytes, algorithm: CompressionAlgorithm = CompressionAlgorithm.ZSTANDARD) -> Tuple[bytes, str]:
        """
        Compress data with specified algorithm
        Returns: (compressed_data, algorithm_name)
        """
        if algorithm == CompressionAlgorithm.BROTLI:
            return CompressionService.compress_brotli(data), "brotli"
        elif algorithm == CompressionAlgorithm.ZSTANDARD:
            return CompressionService.compress_zstd(data), "zstd"
        elif algorithm == CompressionAlgorithm.GZIP:
            return CompressionService.compress_gzip(data), "gzip"
        elif algorithm == CompressionAlgorithm.LZMA:
            return CompressionService.compress_lzma(data), "lzma"
        else:
            return data, "none"
    
    @staticmethod
    def decompress(data: bytes, algorithm: str) -> bytes:
        """Decompress data based on algorithm name"""
        if algorithm == "brotli":
            return CompressionService.decompress_brotli(data)
        elif algorithm == "zstd":
            return CompressionService.decompress_zstd(data)
        elif algorithm == "gzip":
            return CompressionService.decompress_gzip(data)
        elif algorithm == "lzma":
            return CompressionService.decompress_lzma(data)
        else:
            return data
    
    @staticmethod
    def auto_compress(data: bytes) -> Tuple[bytes, str, float]:
        """
        Automatically choose best compression algorithm
        Returns: (compressed_data, algorithm, compression_ratio)
        """
        original_size = len(data)
        
        # Try all algorithms
        results = []
        
        try:
            brotli_data = CompressionService.compress_brotli(data)
            results.append((brotli_data, "brotli", len(brotli_data) / original_size))
        except:
            pass
        
        try:
            zstd_data = CompressionService.compress_zstd(data)
            results.append((zstd_data, "zstd", len(zstd_data) / original_size))
        except:
            pass
        
        try:
            gzip_data = CompressionService.compress_gzip(data)
            results.append((gzip_data, "gzip", len(gzip_data) / original_size))
        except:
            pass
        
        # Return best compression
        if results:
            best = min(results, key=lambda x: x[2])
            return best
        
        return data, "none", 1.0
    
    @staticmethod
    def compress_file_stream(input_path: str, output_path: str, 
                            algorithm: CompressionAlgorithm = CompressionAlgorithm.ZSTANDARD,
                            chunk_size: int = 1024 * 1024) -> int:
        """
        Compress large file in streaming mode
        Returns: compressed size
        """
        compressed_size = 0
        
        if algorithm == CompressionAlgorithm.ZSTANDARD:
            compressor = zstd.ZstdCompressor(level=CompressionService.ZSTD_LEVEL)
            with open(input_path, 'rb') as infile, open(output_path, 'wb') as outfile:
                with compressor.stream_writer(outfile) as writer:
                    while True:
                        chunk = infile.read(chunk_size)
                        if not chunk:
                            break
                        writer.write(chunk)
                        compressed_size += len(chunk)
        
        elif algorithm == CompressionAlgorithm.BROTLI:
            compressor = brotli.Compressor(quality=CompressionService.BROTLI_QUALITY)
            with open(input_path, 'rb') as infile, open(output_path, 'wb') as outfile:
                while True:
                    chunk = infile.read(chunk_size)
                    if not chunk:
                        break
                    compressed = compressor.process(chunk)
                    if compressed:
                        outfile.write(compressed)
                        compressed_size += len(compressed)
                final = compressor.finish()
                if final:
                    outfile.write(final)
                    compressed_size += len(final)
        
        elif algorithm == CompressionAlgorithm.GZIP:
            with open(input_path, 'rb') as infile, gzip.open(output_path, 'wb') as outfile:
                while True:
                    chunk = infile.read(chunk_size)
                    if not chunk:
                        break
                    outfile.write(chunk)
                    compressed_size += len(chunk)
        
        return compressed_size
    
    @staticmethod
    def decompress_file_stream(input_path: str, output_path: str, 
                               algorithm: str,
                               chunk_size: int = 1024 * 1024) -> int:
        """
        Decompress large file in streaming mode
        Returns: decompressed size
        """
        decompressed_size = 0
        
        if algorithm == "zstd":
            decompressor = zstd.ZstdDecompressor()
            with open(input_path, 'rb') as infile, open(output_path, 'wb') as outfile:
                with decompressor.stream_reader(infile) as reader:
                    while True:
                        chunk = reader.read(chunk_size)
                        if not chunk:
                            break
                        outfile.write(chunk)
                        decompressed_size += len(chunk)
        
        elif algorithm == "brotli":
            decompressor = brotli.Decompressor()
            with open(input_path, 'rb') as infile, open(output_path, 'wb') as outfile:
                while True:
                    chunk = infile.read(chunk_size)
                    if not chunk:
                        break
                    decompressed = decompressor.decompress(chunk)
                    if decompressed:
                        outfile.write(decompressed)
                        decompressed_size += len(decompressed)
        
        elif algorithm == "gzip":
            with gzip.open(input_path, 'rb') as infile, open(output_path, 'wb') as outfile:
                while True:
                    chunk = infile.read(chunk_size)
                    if not chunk:
                        break
                    outfile.write(chunk)
                    decompressed_size += len(chunk)
        
        return decompressed_size
    
    @staticmethod
    def get_compression_stats(original_data: bytes, compressed_data: bytes) -> dict:
        """Get compression statistics"""
        original_size = len(original_data)
        compressed_size = len(compressed_data)
        ratio = compressed_size / original_size if original_size > 0 else 1.0
        savings = original_size - compressed_size
        savings_percent = (savings / original_size * 100) if original_size > 0 else 0
        
        return {
            'original_size': original_size,
            'compressed_size': compressed_size,
            'compression_ratio': ratio,
            'space_saved': savings,
            'space_saved_percent': savings_percent
        }

class AdaptiveCompression:
    """Adaptive compression based on file type"""
    
    # File types that compress well
    COMPRESSIBLE_TYPES = {
        'text', 'json', 'xml', 'html', 'css', 'js', 'csv', 'log',
        'txt', 'md', 'yaml', 'yml', 'sql', 'py', 'java', 'cpp'
    }
    
    # Already compressed formats
    COMPRESSED_TYPES = {
        'jpg', 'jpeg', 'png', 'gif', 'mp4', 'mp3', 'zip', 'rar',
        '7z', 'gz', 'bz2', 'xz', 'pdf', 'docx', 'xlsx'
    }
    
    @staticmethod
    def should_compress(filename: str, size: int) -> bool:
        """Determine if file should be compressed"""
        ext = filename.split('.')[-1].lower()
        
        # Don't compress already compressed files
        if ext in AdaptiveCompression.COMPRESSED_TYPES:
            return False
        
        # Don't compress very small files (overhead not worth it)
        if size < 1024:  # 1KB
            return False
        
        # Compress text-based files
        if ext in AdaptiveCompression.COMPRESSIBLE_TYPES:
            return True
        
        # Compress large unknown files
        if size > 1024 * 1024:  # 1MB
            return True
        
        return False
    
    @staticmethod
    def choose_algorithm(filename: str, size: int) -> CompressionAlgorithm:
        """Choose best compression algorithm for file"""
        ext = filename.split('.')[-1].lower()
        
        # Text files: Brotli (best for text)
        if ext in {'txt', 'log', 'json', 'xml', 'html', 'css', 'js'}:
            return CompressionAlgorithm.BROTLI
        
        # Code files: Zstandard (fast + good ratio)
        if ext in {'py', 'java', 'cpp', 'c', 'h', 'go', 'rs'}:
            return CompressionAlgorithm.ZSTANDARD
        
        # Large files: Zstandard (fast decompression)
        if size > 10 * 1024 * 1024:  # 10MB
            return CompressionAlgorithm.ZSTANDARD
        
        # Default: Zstandard (best balance)
        return CompressionAlgorithm.ZSTANDARD

# Global compression service
compression_service = CompressionService()
