"""MinIO Object Storage Service — replaces Cloudflare R2.

Drop-in S3-compatible replacement. Only difference from R2:
  - endpoint_url points to your MinIO server (OCI VM or localhost:9000)
  - s3={'addressing_style': 'path'} required (MinIO uses path-style URLs)
  - Two clients: internal (server ops) + public (presigned URL generation)
"""
import logging
import os
from typing import Optional

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class MinIOService:
    """MinIO storage service using S3-compatible API."""

    def __init__(self):
        self.access_key = os.environ.get('MINIO_ACCESS_KEY', '')
        self.secret_key = os.environ.get('MINIO_SECRET_KEY', '')
        self.bucket_name = os.environ.get('MINIO_BUCKET_FILES', 'flowbridge-files')

        # Internal endpoint: used for upload/download/delete (server-to-server)
        internal_endpoint = os.environ.get('MINIO_ENDPOINT_URL', 'http://localhost:9000')
        # Public endpoint: used for presigned URL generation (clients download directly)
        public_endpoint = os.environ.get('MINIO_PUBLIC_ENDPOINT_URL', internal_endpoint)

        if not all([self.access_key, self.secret_key]):
            logger.warning("MinIO credentials not configured — file storage unavailable")
            self.client = None
            self._presign_client = None
            return

        _s3_cfg = BotoConfig(
            signature_version='s3v4',
            s3={'addressing_style': 'path'},   # Required for MinIO
            retries={'max_attempts': 3, 'mode': 'adaptive'}
        )

        self.client = boto3.client(
            's3',
            endpoint_url=internal_endpoint,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name='us-east-1',   # MinIO ignores region
            config=_s3_cfg,
        )

        # Separate client for presigned URLs so they point to the public URL
        self._presign_client = boto3.client(
            's3',
            endpoint_url=public_endpoint,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name='us-east-1',
            config=_s3_cfg,
        )

        logger.info(f"✅ MinIO client initialized — bucket: {self.bucket_name} | internal: {internal_endpoint} | public: {public_endpoint}")

    # ── Core operations ────────────────────────────────────────────────

    def upload_file(self, file_data: bytes, object_key: str,
                    content_type: str = 'application/octet-stream') -> bool:
        if not self.client:
            raise RuntimeError("MinIO client not initialized")
        try:
            self.client.put_object(
                Bucket=self.bucket_name,
                Key=object_key,
                Body=file_data,
                ContentType=content_type,
                Metadata={'uploaded_by': 'flowbridge'},
            )
            logger.info(f"✅ Uploaded to MinIO: {object_key} ({len(file_data):,} bytes)")
            return True
        except ClientError as e:
            logger.error(f"❌ MinIO upload failed: {e}")
            return False

    def download_file(self, object_key: str) -> Optional[bytes]:
        if not self.client:
            raise RuntimeError("MinIO client not initialized")
        try:
            response = self.client.get_object(Bucket=self.bucket_name, Key=object_key)
            data = response['Body'].read()
            logger.info(f"✅ Downloaded from MinIO: {object_key} ({len(data):,} bytes)")
            return data
        except ClientError as e:
            logger.error(f"❌ MinIO download failed: {e}")
            return None

    def delete_file(self, object_key: str) -> bool:
        if not self.client:
            raise RuntimeError("MinIO client not initialized")
        try:
            self.client.delete_object(Bucket=self.bucket_name, Key=object_key)
            logger.info(f"✅ Deleted from MinIO: {object_key}")
            return True
        except ClientError as e:
            logger.error(f"❌ MinIO delete failed: {e}")
            return False

    def file_exists(self, object_key: str) -> bool:
        if not self.client:
            return False
        try:
            self.client.head_object(Bucket=self.bucket_name, Key=object_key)
            return True
        except ClientError:
            return False

    def generate_presigned_url(self, object_key: str,
                                expiry_seconds: int = 900,
                                filename: str = None) -> Optional[str]:
        """Generate presigned GET URL for direct client download (15 min default)."""
        if not self._presign_client:
            raise RuntimeError("MinIO client not initialized")
        try:
            params = {'Bucket': self.bucket_name, 'Key': object_key}
            if filename:
                params['ResponseContentDisposition'] = f'attachment; filename="{filename}"'
            url = self._presign_client.generate_presigned_url(
                'get_object',
                Params=params,
                ExpiresIn=expiry_seconds,
            )
            logger.info(f"✅ Presigned URL generated for {object_key} (expires {expiry_seconds}s)")
            return url
        except ClientError as e:
            logger.error(f"❌ Presigned URL generation failed: {e}")
            return None

    def get_file_size(self, object_key: str) -> Optional[int]:
        if not self.client:
            return None
        try:
            response = self.client.head_object(Bucket=self.bucket_name, Key=object_key)
            return response['ContentLength']
        except ClientError:
            return None

    def is_available(self) -> bool:
        """Check if MinIO is available and configured."""
        return self.client is not None


# ── Singleton ──────────────────────────────────────────────────────────

_minio_service: Optional[MinIOService] = None


def get_minio_service() -> MinIOService:
    """Get or create MinIO service singleton."""
    global _minio_service
    if _minio_service is None:
        _minio_service = MinIOService()
    return _minio_service
