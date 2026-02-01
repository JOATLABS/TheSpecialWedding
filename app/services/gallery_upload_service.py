import os
import boto3
import qrcode
import logging
from urllib.parse import urlparse
from io import BytesIO
from botocore.exceptions import ClientError
from botocore.config import Config
from fastapi import HTTPException, UploadFile
from datetime import datetime
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

# Get MEDIA_DOMAIN from environment - no fallback
MEDIA_DOMAIN = os.getenv("MEDIA_DOMAIN")
if not MEDIA_DOMAIN:
    logger.warning("MEDIA_DOMAIN environment variable is not set")


class GalleryUploadService:
    def __init__(self):
        self.bucket_name = os.getenv("S3_BUCKET_NAME")
        self.s3 = boto3.client(
            "s3",
            endpoint_url=os.getenv("S3_ENDPOINT_URL"),
            aws_access_key_id=os.getenv("S3_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("S3_SECRET_ACCESS_KEY"),
            config=Config(signature_version='s3v4'),
        )

    def create_presigned_url(self, filename: str, expires_in: int = 300):
        """Legacy method - creates presigned URL without wedding_slug (deprecated)"""
        try:
            key = f"gallery/{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{filename}"
            url = self.s3.generate_presigned_url(
                ClientMethod="put_object",
                Params={"Bucket": self.bucket_name, "Key": key},
                ExpiresIn=expires_in
            )
            return {"upload_url": url, "key": key}
        except ClientError as e:
            raise HTTPException(status_code=500, detail=f"Error creating upload URL: {str(e)}")

    def create_presigned_url_with_wedding(self, filename: str, wedding_slug: str, folder: str = "gallery", expires_in: int = 300):
        """Creates presigned URL with wedding_slug in the key for proper authorization"""
        try:
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            key = f"{folder}/{wedding_slug}/{timestamp}_{filename}"
            url = self.s3.generate_presigned_url(
                ClientMethod="put_object",
                Params={"Bucket": self.bucket_name, "Key": key},
                ExpiresIn=expires_in
            )
            return {"upload_url": url, "key": key}
        except ClientError as e:
            raise HTTPException(status_code=500, detail=f"Error creating upload URL: {str(e)}")

    def get_file_url(self, key: str):
        try:
            url = self.s3.generate_presigned_url(
                ClientMethod="get_object",
                Params={"Bucket": self.bucket_name, "Key": key},
                ExpiresIn=3600
            )
            return {"file_url": url}
        except ClientError as e:
            raise HTTPException(status_code=500, detail=f"Error generating file URL: {str(e)}")

    def delete_file(self, key: str):
        try:
            self.s3.delete_object(Bucket=self.bucket_name, Key=key)
            return {"message": "File deleted successfully"}
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            logger.error(f"S3 delete error ({error_code}): {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error deleting file: {str(e)}")

    def list_uploaded_files(self, prefix: str = "gallery/"):
        try:
            response = self.s3.list_objects_v2(Bucket=self.bucket_name, Prefix=prefix)
            if 'Contents' not in response:
                return []

            # Use custom domain for public access instead of presigned URLs
            files = [
                {
                    "key": obj["Key"],
                    "url": f"{MEDIA_DOMAIN}/{obj['Key']}" if MEDIA_DOMAIN else obj["Key"]
                }
                for obj in response["Contents"]
            ]
            return sorted(files, key=lambda x: x["key"], reverse=True)
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            logger.error(f"S3 list error ({error_code}): {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error listing files: {str(e)}")

    def generate_qr_code(self, url: str):
        try:
            # Security: Validate scheme and that the URL belongs to our domain
            parsed_url = urlparse(url)
            if parsed_url.scheme.lower() not in ("http", "https"):
                raise HTTPException(status_code=400, detail="Invalid URL scheme")
            allowed_domains = []

            frontend_url = os.getenv("FRONTEND_URL")
            if frontend_url:
                allowed_domains.append(urlparse(frontend_url).netloc)

            if MEDIA_DOMAIN:
                # MEDIA_DOMAIN might contain protocol
                if "://" in MEDIA_DOMAIN:
                    allowed_domains.append(urlparse(MEDIA_DOMAIN).netloc)
                else:
                    allowed_domains.append(MEDIA_DOMAIN)

            # Check if domain is allowed (reject external domains)
            if not parsed_url.netloc or parsed_url.netloc not in allowed_domains:
                raise HTTPException(status_code=400, detail="Invalid URL domain")

            qr = qrcode.make(url)
            buffer = BytesIO()
            qr.save(buffer)
            buffer.seek(0)
            return StreamingResponse(buffer, media_type="image/png")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error generating QR code: {str(e)}")

    def upload_file_direct(self, file: UploadFile, wedding_slug: str, folder: str = "gallery"):
        try:
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            filename = os.path.basename(str(file.filename))
            key = f"{folder}/{wedding_slug}/{timestamp}_{filename}"

            self.s3.upload_fileobj(file.file, self.bucket_name, key)
            return {"message": "File uploaded successfully", "key": key}
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            logger.error(f"S3 upload error ({error_code}): {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error uploading file: {str(e)}")

