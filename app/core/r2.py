
import os
import uuid
import boto3
from fastapi import UploadFile, HTTPException
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError

# R2 Configuration
R2_ENDPOINT_URL = os.environ.get("R2_ENDPOINT_URL")
R2_ACCESS_KEY_ID = os.environ.get("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.environ.get("R2_SECRET_ACCESS_KEY")
R2_BUCKET_NAME = os.environ.get("R2_BUCKET_NAME")

# Security: Allowed file types and size limits
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.txt', '.csv'}
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


def _validate_file(file: UploadFile) -> None:
    """Validate file type and size before upload."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="File must have a filename")

    file_extension = os.path.splitext(file.filename)[1].lower()
    if file_extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{file_extension}' not allowed. Allowed types: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)

    if file_size > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"File size exceeds maximum allowed ({MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB)"
        )


def upload_to_r2(file: UploadFile, user_id: str) -> str:
    """Upload a validated file to R2 storage."""
    _validate_file(file)

    s3 = boto3.client(
        's3',
        endpoint_url=R2_ENDPOINT_URL,
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        config=Config(signature_version='s3v4')
    )

    try:
        file_extension = os.path.splitext(file.filename)[1].lower()
        secure_filename = f"{uuid.uuid4()}{file_extension}"
        object_name = f"user-attachments/{user_id}/{secure_filename}"

        s3.upload_fileobj(
            file.file,
            R2_BUCKET_NAME,
            object_name,
            ExtraArgs={'ContentType': file.content_type}
        )

        return f"{os.environ.get('R2_PUBLIC_URL')}/{object_name}"

    except (BotoCoreError, ClientError):
        raise HTTPException(status_code=500, detail="Failed to upload file")
