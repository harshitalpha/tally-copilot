"""S3-compatible adapter — works for AWS S3, Supabase Storage, Cloudflare R2,
Backblaze B2, DigitalOcean Spaces, MinIO. Only the endpoint URL changes.
"""


class S3CompatibleStore:
    def __init__(self, endpoint_url: str, access_key: str, secret_key: str,
                 bucket: str, region: str = "us-east-1"):
        import boto3
        from botocore.client import Config
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            config=Config(signature_version="s3v4"),
        )
        self.bucket = bucket
        self.endpoint = endpoint_url

    def upload(self, key: str, content: bytes, content_type: str) -> None:
        self._client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=content,
            ContentType=content_type,
        )

    def download(self, key: str) -> bytes:
        r = self._client.get_object(Bucket=self.bucket, Key=key)
        return r["Body"].read()

    def signed_url(self, key: str, ttl_seconds: int = 3600) -> str:
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=ttl_seconds,
        )

    def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self.bucket, Key=key)

    def health_check(self) -> tuple[bool, str]:
        try:
            self._client.head_bucket(Bucket=self.bucket)
            return True, f"bucket '{self.bucket}' reachable at {self.endpoint}"
        except Exception as e:
            return False, str(e)[:200]
