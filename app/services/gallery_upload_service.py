import os
import boto3
import qrcode
from io import BytesIO
from botocore.exceptions import ClientError
from fastapi import HTTPException, UploadFile
from datetime import datetime
from fastapi.responses import StreamingResponse

class GalleryUploadService:
    def __init__(self):
        self.bucket_name = os.getenv("S3_BUCKET_NAME")
        self.s3 = boto3.client(
            "s3",
            endpoint_url=os.getenv("S3_ENDPOINT_URL"),
            aws_access_key_id=os.getenv("S3_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("S3_SECRET_ACCESS_KEY"),
        )

    def create_presigned_url(self, filename: str, expires_in: int = 300):
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
            raise HTTPException(status_code=500, detail=f"Error deleting file: {str(e)}")

    def list_uploaded_files(self, prefix: str = "gallery/"):
        try:
            response = self.s3.list_objects_v2(Bucket=self.bucket_name, Prefix=prefix)
            if 'Contents' not in response:
                return []
            files = [
                {
                    "key": obj["Key"],
                    "url": self.s3.generate_presigned_url(
                        ClientMethod="get_object",
                        Params={"Bucket": self.bucket_name, "Key": obj["Key"]},
                        ExpiresIn=3600
                    )
                }
                for obj in response["Contents"]
            ]
            return sorted(files, key=lambda x: x["key"], reverse=True)
        except ClientError as e:
            raise HTTPException(status_code=500, detail=f"Error listing files: {str(e)}")

    def generate_qr_code(self, url: str):
        try:
            qr = qrcode.make(url)
            buffer = BytesIO()
            qr.save(buffer)
            buffer.seek(0)
            return StreamingResponse(buffer, media_type="image/png")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error generating QR code: {str(e)}")

    def upload_file_direct(self, file: UploadFile, wedding_slug: str):
        try:
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            filename = os.path.basename(str(file.filename))
            key = f"gallery/{wedding_slug}/{timestamp}_{filename}"

            self.s3.upload_fileobj(file.file, self.bucket_name, key)
            return {"message": "File uploaded successfully", "key": key}
        except ClientError as e:
            raise HTTPException(status_code=500, detail=f"Error uploading file: {str(e)}")

