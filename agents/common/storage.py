"""
Google Cloud Storage / Firebase Storage Helper Utility.
Enables cloud persistence for generated videos, images, expense reports, and registration sheets.
"""

import mimetypes
import os
import urllib.parse
from typing import Optional


def get_default_bucket_name() -> str:
    """Resolves the default Firebase/GCS bucket name from environment."""
    if os.getenv("GCS_BUCKET_NAME"):
        return os.environ["GCS_BUCKET_NAME"]

    project_id = (
        os.getenv("FIREBASE_PROJECT_ID")
        or os.getenv("GOOGLE_CLOUD_PROJECT")
        or os.getenv("GCP_PROJECT_ID")
        or "gdg-agents-6b59a"
    )
    return f"{project_id}.firebasestorage.app"


def upload_bytes_to_storage(
    data: bytes,
    destination_blob_name: str,
    content_type: Optional[str] = None,
    bucket_name: Optional[str] = None,
) -> Optional[str]:
    """Uploads in-memory bytes to GCS / Firebase Storage and returns public URL.

    Args:
        data: Raw file bytes.
        destination_blob_name: Target path in bucket (e.g. 'videos/intro.mp4').
        content_type: MIME type of the file.
        bucket_name: Optional custom bucket name override.

    Returns:
        Public download URL or None if storage is unreachable.
    """
    try:
        from google.cloud import storage

        target_bucket = bucket_name or get_default_bucket_name()
        client = storage.Client()
        bucket = client.bucket(target_bucket)
        blob = bucket.blob(destination_blob_name)

        if not content_type:
            content_type = mimetypes.guess_type(destination_blob_name)[0] or "application/octet-stream"

        filename = os.path.basename(destination_blob_name)
        blob.content_disposition = f'attachment; filename="{filename}"'
        blob.upload_from_string(data, content_type=content_type)
        print(f"☁️ [Cloud Storage] Successfully uploaded '{destination_blob_name}' to gs://{target_bucket}")

        # Construct direct Google Cloud Storage public URL
        public_url = f"https://storage.googleapis.com/{target_bucket}/{destination_blob_name}"
        return public_url
    except Exception as e:
        print(f"⚠️ [Cloud Storage Notice] Upload skipped/failed ({e}). Working in local filesystem mode.")
        return None


def upload_file_to_storage(
    local_path: str,
    destination_blob_name: Optional[str] = None,
    content_type: Optional[str] = None,
    bucket_name: Optional[str] = None,
) -> Optional[str]:
    """Uploads a local file to GCS / Firebase Storage and returns public URL.

    Args:
        local_path: Absolute or relative path to local file.
        destination_blob_name: Target path in bucket (default: filename).
        content_type: MIME type of the file.
        bucket_name: Optional custom bucket name override.

    Returns:
        Public download URL or None if storage is unreachable.
    """
    if not os.path.exists(local_path):
        return None

    if not destination_blob_name:
        destination_blob_name = os.path.basename(local_path)

    try:
        with open(local_path, "rb") as f:
            data = f.read()
        return upload_bytes_to_storage(
            data=data,
            destination_blob_name=destination_blob_name,
            content_type=content_type,
            bucket_name=bucket_name,
        )
    except Exception as e:
        print(f"⚠️ [Cloud Storage Notice] Failed to read/upload '{local_path}': {e}")
        return None
