
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

def upload_to_r2(file: UploadFile, user_id: str) -> str:
    s3 = boto3.client(
        's3',
        endpoint_url=R2_ENDPOINT_URL,
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        config=Config(signature_version='s3v4')
    )

    try:
        file_extension = os.path.splitext(file.filename)[1]
        secure_filename = f"{uuid.uuid4()}{file_extension}"
        object_name = f"user-attachments/{user_id}/{secure_filename}"

        s3.upload_fileobj(
            file.file,
            R2_BUCKET_NAME,
            object_name,
            ExtraArgs={'ContentType': file.content_type}
        )

        return f"{os.environ.get('R2_PUBLIC_URL')}/{object_name}"

    except (BotoCoreError, ClientError) as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload file to R2: {e}")
