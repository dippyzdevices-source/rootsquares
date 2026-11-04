"""Object storage (ADR 028): one generic S3-compatible client, so Supabase Storage (local/test), Neon Object Storage (production) and later
AWS S3 or Cloudflare R2 are a configuration change. Adapted from the bca-oslo reference (backend/app/storage/service.py).

Difference from the reference: a missing endpoint selects the in-memory fake only outside production (Settings refuses to boot in production
without storage), so uploads can never silently land in memory on a live server."""

from __future__ import annotations

import boto3
from botocore.client import Config

from app.shared.config import Settings

PRESIGN_SECONDS = 3600


class S3CompatibleStorage:
    def __init__(
        self, *, bucket: str, public: bool, endpoint_url: str, access_key: str, secret_key: str, region: str = "auto", public_base_url: str = ""
    ) -> None:
        self._bucket = bucket
        self._public = public
        self._public_base_url = public_base_url.rstrip("/")
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            config=Config(s3={"addressing_style": "path"}),  # Supabase and Neon need path-style URLs, not boto3's virtual-hosted default
        )

    def upload(self, key: str, data: bytes, content_type: str) -> None:
        self._client.put_object(Bucket=self._bucket, Key=key, Body=data, ContentType=content_type)

    def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=key)

    def check(self) -> None:
        """Raises when the bucket cannot be reached with these keys (used by the owner console health page)."""
        self._client.head_bucket(Bucket=self._bucket)

    def url_for(self, key: str) -> str:
        if self._public:
            return f"{self._public_base_url}/{key}"
        return str(self._client.generate_presigned_url("get_object", Params={"Bucket": self._bucket, "Key": key}, ExpiresIn=PRESIGN_SECONDS))

    def key_from_url(self, url: str) -> str | None:
        if not self._public:
            return None  # a presigned URL is not reversible
        prefix = f"{self._public_base_url}/"
        return url.removeprefix(prefix) if url.startswith(prefix) else None


class FakeStorage:
    """In-memory storage for tests and for local work without a bucket. No network."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def upload(self, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = data

    def delete(self, key: str) -> None:
        self.objects.pop(key, None)

    def url_for(self, key: str) -> str:
        return f"fake://storage/{key}"

    def key_from_url(self, url: str) -> str | None:
        prefix = "fake://storage/"
        return url.removeprefix(prefix) if url.startswith(prefix) else None


def build_storage(settings: Settings) -> tuple[S3CompatibleStorage | FakeStorage, S3CompatibleStorage | FakeStorage]:
    """(public, private). Fakes when no endpoint is set; Settings has already refused that in production."""
    if not settings.STORAGE_S3_ENDPOINT_URL:
        return FakeStorage(), FakeStorage()
    public = S3CompatibleStorage(
        bucket=settings.STORAGE_PUBLIC_BUCKET,
        public=True,
        endpoint_url=settings.STORAGE_S3_ENDPOINT_URL,
        access_key=settings.STORAGE_S3_ACCESS_KEY,
        secret_key=settings.STORAGE_S3_SECRET_KEY,
        region=settings.STORAGE_S3_REGION,
        public_base_url=settings.STORAGE_PUBLIC_BASE_URL,
    )
    private = S3CompatibleStorage(
        bucket=settings.STORAGE_PRIVATE_BUCKET,
        public=False,
        endpoint_url=settings.STORAGE_S3_ENDPOINT_URL,
        access_key=settings.STORAGE_S3_ACCESS_KEY,
        secret_key=settings.STORAGE_S3_SECRET_KEY,
        region=settings.STORAGE_S3_REGION,
    )
    return public, private
