import boto3
import os
from typing import Optional



class StorageService:
    def __init__(self):
        self.enabled = all([
            os.getenv("S3_KEY"),
            os.getenv("S3_SECRET"),
            os.getenv("S3_ENDPOINT"),
            os.getenv("S3_BUCKET")
        ])
        if self.enabled:
            self.s3 = boto3.client(
                's3',
                region_name=os.getenv("S3_REGION", "nyc3"),
                endpoint_url=os.getenv("S3_ENDPOINT"),
                aws_access_key_id=os.getenv("S3_KEY"),
                aws_secret_access_key=os.getenv("S3_SECRET"),
                config=boto3.session.Config(signature_version='s3v4') # Important for some S3 providers
            )
            self.bucket = os.getenv("S3_BUCKET")
            self.cdn_url = os.getenv("S3_CDN_URL", f"{os.getenv('S3_ENDPOINT')}/{self.bucket}").rstrip('/')

    def generate_presigned_url(self, filename: str, content_type: str, expires_in: int = 3600) -> Optional[dict]:
        if not self.enabled:
            return None
        
        url = self.s3.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': self.bucket,
                'Key': filename,
                'ContentType': content_type,
                'ACL': 'public-read'
            },
            ExpiresIn=expires_in
        )
        return {
            "upload_url": url,
            "public_url": f"{self.cdn_url}/{filename}"
        }

    def upload(self, file_content: bytes, filename: str, content_type: str) -> Optional[str]:
        if not self.enabled:
            return None
        
        self.s3.put_object(
            Bucket=self.bucket,
            Key=filename,
            Body=file_content,
            ACL='public-read',
            ContentType=content_type
        )
        return f"{self.cdn_url}/{filename}"
