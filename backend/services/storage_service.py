"""
Unified Storage Service — FlowBridge
─────────────────────────────────────
Write strategy  : R2 (sync primary) → B2 (async global replica) → MinIO (async local replica)
Read strategy   : R2 presigned URL → B2 presigned URL (fallback) → MinIO presigned URL (LAN)
Key format      : files/{sha256[:2]}/{sha256[2:]}  (content-addressable, auto-dedup)
"""
import hashlib
import logging
import mimetypes
import os
import threading
from typing import Optional, Tuple

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError

from config import Config

logger = logging.getLogger(__name__)

# ── Boto3 config shared by all S3-compatible clients ──────────────────────
_S3_CFG_PATH = BotoConfig(
    signature_version='s3v4',
    s3={'addressing_style': 'path'},
    retries={'max_attempts': 3, 'mode': 'adaptive'},
)
_S3_CFG_VHOST = BotoConfig(
    signature_version='s3v4',
    s3={'addressing_style': 'virtual'},
    retries={'max_attempts': 3, 'mode': 'adaptive'},
)


def _make_client(endpoint: str, key: str, secret: str,
                 path_style: bool = True) -> Optional[object]:
    """Create a boto3 S3 client. Returns None if credentials missing."""
    if not all([endpoint, key, secret]):
        return None
    try:
        return boto3.client(
            's3',
            endpoint_url=endpoint,
            aws_access_key_id=key,
            aws_secret_access_key=secret,
            region_name='auto',
            config=_S3_CFG_PATH if path_style else _S3_CFG_VHOST,
        )
    except Exception as e:
        logger.warning(f"Storage client init failed ({endpoint}): {e}")
        return None


# ── SHA-256 content-addressable key ───────────────────────────────────────

def compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def storage_key(sha256: str) -> str:
    """files/{first2}/{rest}  — distributes objects across prefixes."""
    return f"files/{sha256[:2]}/{sha256[2:]}"


# ══════════════════════════════════════════════════════════════════════════
#  StorageService
# ══════════════════════════════════════════════════════════════════════════

class StorageService:
    """
    Unified storage with three backends:
      • R2    — Cloudflare (primary, ~5ms via Mumbai CF PoP)
      • B2    — Backblaze EU Central (global replica, ~120ms)
      • MinIO — Docker localhost (local replica + LAN transfers, ~0ms)
    """

    def __init__(self):
        # ── R2 primary ────────────────────────────────────────────────
        r2_endpoint = (
            f"https://{Config.R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
            if Config.R2_ACCOUNT_ID else ""
        )
        self.r2 = _make_client(
            r2_endpoint,
            Config.R2_ACCESS_KEY_ID,
            Config.R2_SECRET_ACCESS_KEY,
            path_style=False,   # R2 uses virtual-hosted style
        )
        self.r2_bucket = Config.R2_BUCKET_FILES

        # ── B2 global replica ─────────────────────────────────────────
        self.b2 = _make_client(
            Config.B2_ENDPOINT_URL,
            Config.B2_ACCESS_KEY_ID,
            Config.B2_SECRET_ACCESS_KEY,
            path_style=True,
        )
        self.b2_bucket = Config.B2_BUCKET_FILES

        # ── MinIO local replica ───────────────────────────────────────
        self.minio = _make_client(
            Config.MINIO_ENDPOINT_URL,
            Config.MINIO_ACCESS_KEY,
            Config.MINIO_SECRET_KEY,
            path_style=True,
        )
        # Separate MinIO client for presigned URLs (uses public endpoint)
        self.minio_presign = _make_client(
            Config.MINIO_PUBLIC_ENDPOINT_URL or Config.MINIO_ENDPOINT_URL,
            Config.MINIO_ACCESS_KEY,
            Config.MINIO_SECRET_KEY,
            path_style=True,
        )
        self.minio_bucket = Config.MINIO_BUCKET_FILES

        self._log_status()

    def _log_status(self):
        r2_ok    = "✅" if self.r2    else "❌ (not configured)"
        b2_ok    = "✅" if self.b2    else "❌ (not configured)"
        minio_ok = "✅" if self.minio else "❌ (not configured)"
        logger.info(f"Storage backends — R2: {r2_ok} | B2: {b2_ok} | MinIO: {minio_ok}")

    # ── Internal helpers ───────────────────────────────────────────────────

    def _object_exists(self, client, bucket: str, key: str) -> bool:
        try:
            client.head_object(Bucket=bucket, Key=key)
            return True
        except ClientError:
            return False

    def _put_object(self, client, bucket: str, key: str,
                    data: bytes, content_type: str, filename: str) -> bool:
        try:
            client.put_object(
                Bucket=bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
                Metadata={'original-filename': filename},
            )
            return True
        except Exception as e:
            logger.error(f"put_object failed [{bucket}/{key}]: {e}")
            return False

    def _presigned_get(self, client, bucket: str, key: str,
                       expiry: int, filename: str) -> Optional[str]:
        try:
            return client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': bucket,
                    'Key': key,
                    'ResponseContentDisposition': f'attachment; filename="{filename}"',
                },
                ExpiresIn=expiry,
            )
        except Exception as e:
            logger.error(f"presigned_url failed [{bucket}/{key}]: {e}")
            return None

    # ── Public API ─────────────────────────────────────────────────────────

    def upload(self, file_data: bytes, filename: str,
               content_type: str = None) -> dict:
        """
        Upload file to all configured backends.

        Returns:
            {
              'sha256'       : str,
              'key'          : str,   # content-addressable key (same on all backends)
              'r2_key'       : str | None,
              'b2_key'       : str | None,
              'minio_key'    : str | None,
              'b2_synced'    : bool,
              'minio_synced' : bool,
              'deduplicated' : bool,  # True if file already existed in R2
            }
        """
        if not content_type:
            content_type, _ = mimetypes.guess_type(filename)
            content_type = content_type or 'application/octet-stream'

        sha256   = compute_sha256(file_data)
        key      = storage_key(sha256)
        result   = {
            'sha256': sha256, 'key': key,
            'r2_key': None, 'b2_key': None, 'minio_key': None,
            'b2_synced': False, 'minio_synced': False,
            'deduplicated': False,
        }

        # ── 1. R2 primary (synchronous — must succeed) ─────────────────
        if self.r2:
            already = self._object_exists(self.r2, self.r2_bucket, key)
            if already:
                logger.info(f"R2 dedup hit: {key}")
                result['deduplicated'] = True
            else:
                ok = self._put_object(self.r2, self.r2_bucket, key,
                                      file_data, content_type, filename)
                if not ok:
                    raise RuntimeError("R2 primary upload failed — aborting")
            result['r2_key'] = key
        else:
            # R2 not configured — fall through to MinIO as primary
            logger.warning("R2 not configured — using MinIO as primary")

        # ── 2. B2 global replica (asynchronous — non-blocking) ─────────
        if self.b2:
            def _b2_replicate():
                try:
                    if not self._object_exists(self.b2, self.b2_bucket, key):
                        self._put_object(self.b2, self.b2_bucket, key,
                                         file_data, content_type, filename)
                    logger.info(f"B2 replica synced: {key}")
                except Exception as e:
                    logger.error(f"B2 replica failed: {e}")
            threading.Thread(target=_b2_replicate, daemon=True).start()
            result['b2_key'] = key
            # b2_synced stays False until background thread confirms
            # The models layer will update this flag after async completes

        # ── 3. MinIO local replica (asynchronous — non-blocking) ───────
        if self.minio:
            def _minio_replicate():
                try:
                    if not self._object_exists(self.minio, self.minio_bucket, key):
                        self._put_object(self.minio, self.minio_bucket, key,
                                         file_data, content_type, filename)
                    logger.info(f"MinIO replica synced: {key}")
                except Exception as e:
                    logger.error(f"MinIO replica failed: {e}")
            threading.Thread(target=_minio_replicate, daemon=True).start()
            result['minio_key'] = key

        return result

    def get_download_url(self, r2_key: str, b2_key: str = None,
                         minio_key: str = None, filename: str = 'file',
                         expiry: int = 900) -> Optional[str]:
        """
        Get best available presigned download URL.
        Priority: R2 (CF edge ~5ms) → B2 (global ~120ms) → MinIO (LAN ~0ms)
        """
        # R2 first — fastest for internet users (CF edge Mumbai PoP)
        if self.r2 and r2_key:
            url = self._presigned_get(self.r2, self.r2_bucket,
                                      r2_key, expiry, filename)
            if url:
                return url

        # B2 fallback — global replica
        if self.b2 and b2_key:
            url = self._presigned_get(self.b2, self.b2_bucket,
                                      b2_key, expiry, filename)
            if url:
                logger.warning(f"R2 unavailable, serving from B2: {b2_key}")
                return url

        # MinIO fallback — LAN / local dev only
        if self.minio_presign and minio_key:
            url = self._presigned_get(self.minio_presign, self.minio_bucket,
                                      minio_key, expiry, filename)
            if url:
                logger.warning(f"R2+B2 unavailable, serving from MinIO: {minio_key}")
                return url

        logger.error(f"All storage backends unavailable for key: {r2_key}")
        return None

    def download_bytes(self, key: str) -> Optional[bytes]:
        """
        Download raw bytes — used for ZIP creation and text preview.
        Priority: R2 → B2 → MinIO
        """
        for client, bucket, label in [
            (self.r2,    self.r2_bucket,    "R2"),
            (self.b2,    self.b2_bucket,    "B2"),
            (self.minio, self.minio_bucket, "MinIO"),
        ]:
            if not client:
                continue
            try:
                resp = client.get_object(Bucket=bucket, Key=key)
                data = resp['Body'].read()
                logger.info(f"Downloaded {len(data):,} bytes from {label}: {key}")
                return data
            except ClientError:
                continue
            except Exception as e:
                logger.warning(f"{label} download error: {e}")
                continue
        return None

    def delete(self, key: str) -> bool:
        """
        Delete from all backends.
        Called only when reference_count reaches 0 (dedup-safe).
        """
        deleted = False
        for client, bucket, label in [
            (self.r2,    self.r2_bucket,    "R2"),
            (self.b2,    self.b2_bucket,    "B2"),
            (self.minio, self.minio_bucket, "MinIO"),
        ]:
            if not client:
                continue
            try:
                client.delete_object(Bucket=bucket, Key=key)
                logger.info(f"Deleted from {label}: {key}")
                deleted = True
            except Exception as e:
                logger.warning(f"{label} delete failed: {e}")
        return deleted

    def is_available(self) -> bool:
        """True if at least one backend is configured."""
        return bool(self.r2 or self.b2 or self.minio)


# ── Singleton ──────────────────────────────────────────────────────────────

_storage_service: Optional[StorageService] = None


def get_storage_service() -> StorageService:
    global _storage_service
    if _storage_service is None:
        _storage_service = StorageService()
    return _storage_service
