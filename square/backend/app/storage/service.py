from abc import ABC, abstractmethod
from urllib.parse import quote, unquote

import boto3
import requests
from botocore.client import Config


class StorageService(ABC):
    @abstractmethod
    def upload(self, key: str, data: bytes, content_type: str) -> None: ...

    @abstractmethod
    def delete(self, key: str) -> None: ...

    @abstractmethod
    def url_for(self, key: str) -> str: ...

    @abstractmethod
    def key_from_url(self, url: str) -> str | None:
        """The inverse of url_for(), for a URL this same service actually produced — lets a
        "replace" upload (event banner, member/committee photo, news banner: every model that
        stores a bare url_for() string instead of a real storage_key column, unlike
        gallery.models.Media/EventBanner) delete its own old object before/after uploading the
        new one. Returns None when the URL doesn't match this service's own public base URL —
        e.g. a bare presigned private URL (not stable/reversible) or a URL baked in under a
        since-switched storage provider — safe to just skip deleting in that case rather than
        derive and delete a bogus key.
        """
        ...


class S3CompatibleStorage(StorageService):
    """A generic S3-compatible StorageService — deliberately not a Supabase-specific SDK, so
    swapping to AWS S3 or Cloudflare R2 later is a config change, not a rewrite.
    """

    def __init__(
        self,
        *,
        bucket: str,
        public: bool,
        endpoint_url: str,
        access_key: str,
        secret_key: str,
        region: str = "auto",
        public_base_url: str = "",
    ):
        self._bucket = bucket
        self._public = public
        self._public_base_url = public_base_url
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            # Supabase (and most non-AWS S3-compatible services) requires path-style
            # addressing (https://<endpoint>/<bucket>/<key>) — boto3 defaults to
            # virtual-hosted-style (https://<bucket>.<endpoint>/<key>), which Supabase
            # doesn't support.
            config=Config(s3={"addressing_style": "path"}),
        )

    def upload(self, key: str, data: bytes, content_type: str) -> None:
        self._client.put_object(Bucket=self._bucket, Key=key, Body=data, ContentType=content_type)

    def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=key)

    def url_for(self, key: str) -> str:
        if self._public:
            return f"{self._public_base_url}/{key}"
        return self._client.generate_presigned_url(
            "get_object", Params={"Bucket": self._bucket, "Key": key}, ExpiresIn=3600
        )

    def key_from_url(self, url: str) -> str | None:
        if not self._public:
            return None
        prefix = f"{self._public_base_url}/"
        return url.removeprefix(prefix) if url.startswith(prefix) else None


class FakeStorageService(StorageService):
    """In-memory StorageService for tests — no network calls, ever."""

    def __init__(self):
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


class SupabaseProjectStorage(StorageService):
    """A square's OWN Supabase Storage (rootsquares W6-R43; not in bca-oslo, which has one server-wide bucket). Uses the Storage HTTP API with the
    project's service key, because the S3 keys of a project can only be made by hand in its dashboard. Buckets are the `public` and `private`
    ones the platform creates for every square. Public files have a stable URL; private files get a signed, time-limited one."""

    SIGNED_SECONDS = 3600

    def __init__(self, *, project_url: str, service_key: str, bucket: str, public: bool) -> None:
        self._base = project_url.rstrip("/") + "/storage/v1"
        self._bucket = bucket
        self._public = public
        self._headers = {"Authorization": f"Bearer {service_key}", "apikey": service_key}

    def _object_url(self, key: str) -> str:
        return f"{self._base}/object/{self._bucket}/{quote(key, safe='/')}"

    def upload(self, key: str, data: bytes, content_type: str) -> None:
        response = requests.post(self._object_url(key), data=data, headers={**self._headers, "Content-Type": content_type, "x-upsert": "true"}, timeout=30)
        response.raise_for_status()

    def delete(self, key: str) -> None:
        response = requests.delete(self._object_url(key), headers=self._headers, timeout=30)
        if response.status_code != 404:  # already gone is fine
            response.raise_for_status()

    def _public_prefix(self) -> str:
        return f"{self._base}/object/public/{self._bucket}/"

    def url_for(self, key: str) -> str:
        if self._public:
            return self._public_prefix() + quote(key, safe="/")
        response = requests.post(
            f"{self._base}/object/sign/{self._bucket}/{quote(key, safe='/')}", json={"expiresIn": self.SIGNED_SECONDS}, headers=self._headers, timeout=30
        )
        response.raise_for_status()
        return f"{self._base}{response.json()['signedURL']}"

    def key_from_url(self, url: str) -> str | None:
        if not self._public or not url.startswith(self._public_prefix()):
            return None  # a signed private URL cannot be reversed
        return unquote(url.removeprefix(self._public_prefix()))


_tenant_storage: dict[tuple[str, str, int, str], "StorageService"] = {}


def _storage(kind: str) -> "StorageService":
    """The served square's own storage when it has one, else the server-wide one (single tenant, bca-oslo style)."""
    from flask import current_app

    from app.tenancy import current_tenant

    tenant = current_tenant()
    if tenant is not None and tenant.s3_endpoint and tenant.s3_access_key and tenant.s3_secret_key:  # a Neon square: its own S3 compatible storage
        key = (tenant.slug, tenant.s3_endpoint, hash(tenant.s3_secret_key), kind)
        if key not in _tenant_storage:
            _tenant_storage[key] = S3CompatibleStorage(
                bucket=kind,
                public=kind == "public",
                endpoint_url=tenant.s3_endpoint,
                access_key=tenant.s3_access_key,
                secret_key=tenant.s3_secret_key,
                region=tenant.s3_region or "auto",
                public_base_url=f"{tenant.s3_endpoint}/{kind}",  # a public_read object is served at <endpoint>/<bucket>/<key>
            )
        return _tenant_storage[key]
    if tenant is not None and tenant.storage_url and tenant.storage_key:
        key = (tenant.slug, tenant.storage_url, hash(tenant.storage_key), kind)  # a rotated service key makes a new client
        if key not in _tenant_storage:
            _tenant_storage[key] = SupabaseProjectStorage(project_url=tenant.storage_url, service_key=tenant.storage_key, bucket=kind, public=kind == "public")
        return _tenant_storage[key]
    return current_app.extensions[f"{kind}_storage"]


def get_public_storage() -> "StorageService":
    return _storage("public")


def get_private_storage() -> "StorageService":
    return _storage("private")
