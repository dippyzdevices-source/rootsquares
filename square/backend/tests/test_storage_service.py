"""Tests for storage service (13 tests), e.g. fake storage round trips uploaded data; fake storage delete removes the object; fake storage delete is a no op for a missing key."""
from unittest.mock import MagicMock

from app.storage.service import FakeStorageService, S3CompatibleStorage


def test_fake_storage_round_trips_uploaded_data():
    storage = FakeStorageService()

    storage.upload("gallery/1/photo.jpg", b"fake-bytes", "image/jpeg")

    assert storage.objects["gallery/1/photo.jpg"] == b"fake-bytes"


def test_fake_storage_delete_removes_the_object():
    storage = FakeStorageService()
    storage.upload("gallery/1/photo.jpg", b"fake-bytes", "image/jpeg")

    storage.delete("gallery/1/photo.jpg")

    assert "gallery/1/photo.jpg" not in storage.objects


def test_fake_storage_delete_is_a_no_op_for_a_missing_key():
    storage = FakeStorageService()

    storage.delete("does/not/exist.jpg")  # must not raise


def test_fake_storage_url_for_returns_a_stable_fake_url():
    storage = FakeStorageService()

    assert storage.url_for("gallery/1/photo.jpg") == "fake://storage/gallery/1/photo.jpg"


def test_public_bucket_url_for_builds_from_the_public_base_url():
    storage = S3CompatibleStorage(
        bucket="bca-public",
        public=True,
        endpoint_url="https://example.supabase.co/storage/v1/s3",
        access_key="key",
        secret_key="secret",
        public_base_url="https://example.supabase.co/storage/v1/object/public/bca-public",
    )

    url = storage.url_for("gallery/1/photo.jpg")

    assert url == "https://example.supabase.co/storage/v1/object/public/bca-public/gallery/1/photo.jpg"


def test_private_bucket_url_for_returns_a_presigned_url():
    storage = S3CompatibleStorage(
        bucket="bca-private",
        public=False,
        endpoint_url="https://example.supabase.co/storage/v1/s3",
        access_key="key",
        secret_key="secret",
    )

    url = storage.url_for("tickets/1/ticket.pdf")

    # A real presigned URL from a local signing operation — no network call is made.
    assert url.startswith("https://example.supabase.co/storage/v1/s3/bca-private/tickets/1/ticket.pdf")
    assert "X-Amz-Signature" in url


def test_upload_calls_put_object_with_the_right_arguments():
    storage = S3CompatibleStorage(
        bucket="bca-public",
        public=True,
        endpoint_url="https://example.supabase.co/storage/v1/s3",
        access_key="key",
        secret_key="secret",
        public_base_url="https://example.supabase.co/storage/v1/object/public/bca-public",
    )
    storage._client = MagicMock()

    storage.upload("gallery/1/photo.jpg", b"fake-bytes", "image/jpeg")

    storage._client.put_object.assert_called_once_with(
        Bucket="bca-public", Key="gallery/1/photo.jpg", Body=b"fake-bytes", ContentType="image/jpeg"
    )


def test_public_bucket_key_from_url_reverses_url_for():
    storage = S3CompatibleStorage(
        bucket="bca-public",
        public=True,
        endpoint_url="https://example.supabase.co/storage/v1/s3",
        access_key="key",
        secret_key="secret",
        public_base_url="https://example.supabase.co/storage/v1/object/public/bca-public",
    )

    url = storage.url_for("gallery/1/photo.jpg")

    assert storage.key_from_url(url) == "gallery/1/photo.jpg"


def test_public_bucket_key_from_url_returns_none_for_an_unrecognized_url():
    storage = S3CompatibleStorage(
        bucket="bca-public",
        public=True,
        endpoint_url="https://example.supabase.co/storage/v1/s3",
        access_key="key",
        secret_key="secret",
        public_base_url="https://example.supabase.co/storage/v1/object/public/bca-public",
    )

    # e.g. a URL baked in under a since-switched storage provider (Supabase -> Neon) — safe
    # to just skip deleting rather than derive a bogus key from a mismatched prefix.
    assert storage.key_from_url("https://a-different-host.example.com/bca-public/foo.jpg") is None


def test_private_bucket_key_from_url_returns_none():
    # Presigned URLs aren't stable/reversible, and nothing needs to reverse one today.
    storage = S3CompatibleStorage(
        bucket="bca-private",
        public=False,
        endpoint_url="https://example.supabase.co/storage/v1/s3",
        access_key="key",
        secret_key="secret",
    )

    presigned = storage.url_for("tickets/1/ticket.pdf")

    assert storage.key_from_url(presigned) is None


def test_fake_storage_key_from_url_reverses_url_for():
    storage = FakeStorageService()

    assert storage.key_from_url("fake://storage/gallery/1/photo.jpg") == "gallery/1/photo.jpg"


def test_fake_storage_key_from_url_returns_none_for_an_unrecognized_url():
    storage = FakeStorageService()

    assert storage.key_from_url("https://example.com/photo.jpg") is None


def test_delete_calls_delete_object_with_the_right_arguments():
    storage = S3CompatibleStorage(
        bucket="bca-public",
        public=True,
        endpoint_url="https://example.supabase.co/storage/v1/s3",
        access_key="key",
        secret_key="secret",
    )
    storage._client = MagicMock()

    storage.delete("gallery/1/photo.jpg")

    storage._client.delete_object.assert_called_once_with(Bucket="bca-public", Key="gallery/1/photo.jpg")
