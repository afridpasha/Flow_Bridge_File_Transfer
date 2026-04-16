"""
Cloudflare R2 Object Storage Service
Replaces MongoDB GridFS with content-addressable storage
"""
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
import hashlib
import os
from datetime import datetime, timedelta
import mimetypes

class R2Service:
    """
    Cloudflare R2 Storage Service
    - Content-addressable storage (SHA-256 keys)
    - Automatic deduplication
    - Presigned URLs for direct downloads
    - Zero egress fees
    """
    
    def __init__(self):
        account_id = os.getenv('R2_ACCOUNT_ID')
        if not account_id:
            raise ValueError("R2_ACCOUNT_ID environment variable not set")
        
        self.client = boto3.client(
            's3',
            endpoint_url=f'https://{account_id}.r2.cloudflarestorage.com',
            aws_access_key_id=os.getenv('R2_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('R2_SECRET_ACCESS_KEY'),
            config=Config(signature_version='s3v4'),
            region_name='auto'
        )
        self.bucket = os.getenv('R2_BUCKET_FILES', 'flowbridge-files')
        # R2 buckets must be created in the Cloudflare dashboard — do not auto-create
        self._verify_bucket_accessible()
    
    def _verify_bucket_accessible(self):
        """Verify bucket exists and is accessible (read-only check)."""
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except ClientError as e:
            print(f"✗ R2 bucket '{self.bucket}' not accessible: {e}. Create it in the Cloudflare dashboard.")
    
    def compute_sha256(self, file_data):
        """
        Compute SHA-256 hash for content-addressable storage
        
        Args:
            file_data: bytes or file-like object
        
        Returns:
            str: SHA-256 hash in hexadecimal
        """
        if isinstance(file_data, bytes):
            return hashlib.sha256(file_data).hexdigest()
        else:
            # For file-like objects, read in chunks
            sha256 = hashlib.sha256()
            for chunk in iter(lambda: file_data.read(65536), b''):
                sha256.update(chunk)
            file_data.seek(0)  # Reset file pointer
            return sha256.hexdigest()
    
    def generate_r2_key(self, sha256_hash):
        """
        Generate R2 key using content-addressable format
        Format: files/{first_2_chars}/{rest_of_hash}
        
        Example: files/ab/cd1234ef567890...
        
        Benefits:
        - Distributes files across prefixes (better performance)
        - Enables global deduplication
        - Immutable keys (files never change)
        """
        return f"files/{sha256_hash[:2]}/{sha256_hash[2:]}"
    
    def file_exists(self, r2_key):
        """Check if file exists in R2"""
        try:
            self.client.head_object(Bucket=self.bucket, Key=r2_key)
            return True
        except ClientError:
            return False
    
    def upload_file(self, file_data, filename, content_type=None, user_id=None):
        """
        Upload file to R2 with content-addressable key
        
        Args:
            file_data: bytes or file-like object
            filename: original filename
            content_type: MIME type (auto-detected if None)
            user_id: user who uploaded (for metadata)
        
        Returns:
            tuple: (r2_key, sha256_hash, already_existed)
        """
        # Compute SHA-256 hash
        sha256_hash = self.compute_sha256(file_data)
        r2_key = self.generate_r2_key(sha256_hash)
        
        # Check if file already exists (deduplication)
        if self.file_exists(r2_key):
            print(f"✓ File already exists (deduplicated): {r2_key}")
            return r2_key, sha256_hash, True
        
        # Auto-detect content type if not provided
        if not content_type:
            content_type, _ = mimetypes.guess_type(filename)
            if not content_type:
                content_type = 'application/octet-stream'
        
        # Prepare metadata
        metadata = {
            'original-filename': filename,
            'sha256': sha256_hash,
            'uploaded-at': datetime.utcnow().isoformat()
        }
        if user_id:
            metadata['uploaded-by'] = str(user_id)
        
        # Upload to R2
        try:
            self.client.put_object(
                Bucket=self.bucket,
                Key=r2_key,
                Body=file_data,
                ContentType=content_type,
                Metadata=metadata
            )
            print(f"✓ Uploaded to R2: {r2_key}")
            return r2_key, sha256_hash, False
        except Exception as e:
            print(f"✗ Upload failed: {e}")
            raise
    
    def generate_presigned_url(self, r2_key, expiry=900, filename=None):
        """
        Generate presigned download URL
        
        Args:
            r2_key: R2 object key
            expiry: URL expiry in seconds (default 15 minutes)
            filename: Optional filename for Content-Disposition header
        
        Returns:
            str: Presigned URL valid for {expiry} seconds
        """
        params = {
            'Bucket': self.bucket,
            'Key': r2_key
        }
        
        # Add Content-Disposition for download with custom filename
        if filename:
            params['ResponseContentDisposition'] = f'attachment; filename="{filename}"'
        
        try:
            url = self.client.generate_presigned_url(
                'get_object',
                Params=params,
                ExpiresIn=expiry
            )
            return url
        except Exception as e:
            print(f"✗ Failed to generate presigned URL: {e}")
            raise
    
    def delete_file(self, r2_key):
        """
        Delete file from R2
        
        Note: Only delete when reference_count reaches 0
        (multiple users may reference same file via deduplication)
        """
        try:
            self.client.delete_object(Bucket=self.bucket, Key=r2_key)
            print(f"✓ Deleted from R2: {r2_key}")
            return True
        except Exception as e:
            print(f"✗ Delete failed: {e}")
            return False
    
    def get_file_metadata(self, r2_key):
        """Get file metadata from R2"""
        try:
            response = self.client.head_object(Bucket=self.bucket, Key=r2_key)
            return {
                'content_type': response.get('ContentType'),
                'size': response.get('ContentLength'),
                'last_modified': response.get('LastModified'),
                'metadata': response.get('Metadata', {})
            }
        except ClientError:
            return None
    
    def list_files(self, prefix='files/', max_keys=1000):
        """List files in R2 (for admin/debugging)"""
        try:
            response = self.client.list_objects_v2(
                Bucket=self.bucket,
                Prefix=prefix,
                MaxKeys=max_keys
            )
            return response.get('Contents', [])
        except Exception as e:
            print(f"✗ List failed: {e}")
            return []
    
    def get_storage_stats(self):
        """Get storage statistics"""
        try:
            objects = self.list_files(max_keys=10000)
            total_size = sum(obj['Size'] for obj in objects)
            return {
                'total_files': len(objects),
                'total_size_bytes': total_size,
                'total_size_mb': round(total_size / (1024 * 1024), 2),
                'total_size_gb': round(total_size / (1024 * 1024 * 1024), 2)
            }
        except Exception as e:
            print(f"✗ Stats failed: {e}")
            return None


# NOTE: This file is superseded by services/storage_service.py
# Do not use get_r2_service() — use get_storage_service() instead
