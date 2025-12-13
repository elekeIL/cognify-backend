"""
Cloud Storage Service for Cloudflare R2 (S3-compatible).

Handles file uploads for audio files and documents.
Falls back to local storage if R2 is not configured.
"""

import os
import logging
from pathlib import Path
from typing import Optional, Tuple
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class StorageService:
    """
    Unified storage service that supports both local and cloud (R2/S3) storage.

    If R2 credentials are configured, files are uploaded to the cloud.
    Otherwise, files are stored locally (for development).
    """

    def __init__(self):
        self.use_cloud = self._is_cloud_configured()

        if self.use_cloud:
            self._init_r2_client()
            logger.info("Storage: Using Cloudflare R2 cloud storage")
        else:
            logger.info("Storage: Using local file storage (R2 not configured)")

    def _is_cloud_configured(self) -> bool:
        """Check if R2/S3 credentials are configured."""
        return bool(
            settings.r2_account_id and
            settings.r2_access_key_id and
            settings.r2_secret_access_key and
            settings.r2_bucket_name
        )

    def _init_r2_client(self):
        """Initialize the R2 (S3-compatible) client."""
        self.s3_client = boto3.client(
            's3',
            endpoint_url=f"https://{settings.r2_account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key,
            config=Config(
                signature_version='s3v4',
                retries={'max_attempts': 3, 'mode': 'standard'}
            ),
            region_name='auto'
        )
        self.bucket_name = settings.r2_bucket_name
        self.public_url_base = settings.r2_public_url

    async def upload_file(
        self,
        file_path: str,
        destination_key: str,
        content_type: str = 'application/octet-stream'
    ) -> Tuple[bool, str]:
        """
        Upload a file to storage.

        Args:
            file_path: Local path to the file to upload
            destination_key: The key/path in storage (e.g., 'audio/filename.mp3')
            content_type: MIME type of the file

        Returns:
            Tuple of (success: bool, url_or_path: str)
        """
        if self.use_cloud:
            return await self._upload_to_r2(file_path, destination_key, content_type)
        else:
            return await self._store_locally(file_path, destination_key)

    async def _upload_to_r2(
        self,
        file_path: str,
        destination_key: str,
        content_type: str
    ) -> Tuple[bool, str]:
        """Upload file to Cloudflare R2."""
        try:
            with open(file_path, 'rb') as file_data:
                self.s3_client.put_object(
                    Bucket=self.bucket_name,
                    Key=destination_key,
                    Body=file_data,
                    ContentType=content_type,
                )

            # Generate public URL
            if self.public_url_base:
                public_url = f"{self.public_url_base.rstrip('/')}/{destination_key}"
            else:
                # Fallback to direct R2 URL (requires public bucket)
                public_url = f"https://{self.bucket_name}.{settings.r2_account_id}.r2.cloudflarestorage.com/{destination_key}"

            logger.info(f"Uploaded to R2: {destination_key}")

            # Optionally delete local file after upload
            try:
                os.remove(file_path)
            except Exception:
                pass

            return True, public_url

        except ClientError as e:
            logger.error(f"R2 upload failed: {e}")
            return False, ""
        except Exception as e:
            logger.error(f"Storage upload error: {e}")
            return False, ""

    async def _store_locally(
        self,
        file_path: str,
        destination_key: str
    ) -> Tuple[bool, str]:
        """Store file locally (development mode)."""
        # File is already in place, just return the path for URL generation
        # The destination_key format: 'audio/filename.mp3'
        relative_path = f"uploads/{destination_key}"
        return True, relative_path

    async def delete_file(self, file_key_or_url: str) -> bool:
        """
        Delete a file from storage.

        Args:
            file_key_or_url: Either the R2 key or the full URL/path

        Returns:
            True if deleted successfully
        """
        if self.use_cloud:
            return await self._delete_from_r2(file_key_or_url)
        else:
            return await self._delete_locally(file_key_or_url)

    async def _delete_from_r2(self, file_key_or_url: str) -> bool:
        """Delete file from R2."""
        try:
            # Extract key from URL if needed
            key = file_key_or_url
            if file_key_or_url.startswith('http'):
                # Extract path from URL
                key = file_key_or_url.split('/')[-2] + '/' + file_key_or_url.split('/')[-1]

            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=key
            )
            logger.info(f"Deleted from R2: {key}")
            return True
        except Exception as e:
            logger.error(f"R2 delete failed: {e}")
            return False

    async def _delete_locally(self, file_path: str) -> bool:
        """Delete file from local storage."""
        try:
            # Handle various path formats
            if file_path.startswith('uploads/'):
                full_path = Path(file_path)
            elif file_path.startswith('/'):
                full_path = Path(file_path.lstrip('/'))
            else:
                full_path = Path(f"uploads/{file_path}")

            if full_path.exists():
                os.remove(full_path)
                logger.info(f"Deleted locally: {full_path}")
                return True
            return False
        except Exception as e:
            logger.error(f"Local delete failed: {e}")
            return False

    def get_public_url(self, file_key_or_path: str) -> str:
        """
        Get the public URL for a file.

        Args:
            file_key_or_path: The file key (R2) or path (local)

        Returns:
            Public URL to access the file
        """
        if not file_key_or_path:
            return ""

        # If already a full URL, return as-is
        if file_key_or_path.startswith('http'):
            return file_key_or_path

        if self.use_cloud and self.public_url_base:
            # R2 URL
            key = file_key_or_path
            if key.startswith('uploads/'):
                key = key.replace('uploads/', '')
            return f"{self.public_url_base.rstrip('/')}/{key}"
        else:
            # Local URL via backend static files
            if file_key_or_path.startswith('uploads/audio/'):
                filename = file_key_or_path.split('/')[-1]
                return f"{settings.effective_base_url}/static/audio/{filename}"
            return f"{settings.effective_base_url}/{file_key_or_path}"


# Singleton instance
_storage_service: Optional[StorageService] = None


def get_storage_service() -> StorageService:
    """Get or create the storage service singleton."""
    global _storage_service
    if _storage_service is None:
        _storage_service = StorageService()
    return _storage_service
