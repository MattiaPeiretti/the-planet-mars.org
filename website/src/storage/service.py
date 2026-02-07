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
                aws_secret_access_key=os.getenv("S3_SECRET")
            )
            self.bucket = os.getenv("S3_BUCKET")

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
        return f"{os.getenv('S3_ENDPOINT')}/{self.bucket}/{filename}"
