# upload_image.py
import boto3
import os
from datetime import datetime

s3 = boto3.client(
    "s3",
    endpoint_url=os.getenv("S3_ENDPOINT_URL"),
    aws_access_key_id=os.getenv("S3_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("S3_SECRET_ACCESS_KEY"),
)

bucket_name = "wedding-gallery"
local_path = "wedding_app_logo_v1.png"
filename = os.path.basename(local_path)
key = f"gallery/{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{filename}"

with open(local_path, "rb") as f:
    s3.upload_fileobj(f, bucket_name, key)

print(f"✅ Uploaded to s3://{bucket_name}/{key}")
