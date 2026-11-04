"""A served square uses its OWN storage and sends mail under its own name (rootsquares W6-R43). bca-oslo had one server-wide bucket and one sender."""

from unittest.mock import MagicMock, patch

import pytest
from flask import g

from app import create_app
from app.email.service import ResendEmailService, get_email_service, sender_for
from app.storage.service import FakeStorageService, SupabaseProjectStorage, get_private_storage, get_public_storage
from app.tenancy import Tenant

SQUARE = Tenant(
    slug="first-org",
    name="First Org",
    theme_id="paper-brick",
    domain="first-org.rootsquares.com",
    db_url="sqlite://",
    auth_provider="supabase",
    auth_url="https://abc.supabase.co",
    auth_public_key="pk",
    storage_url="https://abc.supabase.co",
    storage_key="SECRET-SERVICE-KEY",
)


def _response(status=200, payload=None):
    response = MagicMock(status_code=status)
    response.json.return_value = payload or {}
    response.raise_for_status.side_effect = None if status < 400 else RuntimeError(f"HTTP {status}")
    return response


def test_the_tenant_never_shows_its_service_key_in_logs():
    assert "SECRET-SERVICE-KEY" not in repr(SQUARE)


def test_public_storage_uploads_deletes_and_gives_stable_urls():
    storage = SupabaseProjectStorage(project_url="https://abc.supabase.co/", service_key="K", bucket="public", public=True)
    with patch("app.storage.service.requests.post", return_value=_response()) as post, patch("app.storage.service.requests.delete", return_value=_response()) as delete:
        storage.upload("gallery/1/a photo.jpg", b"bytes", "image/jpeg")
        storage.delete("gallery/1/a photo.jpg")
    url, kwargs = post.call_args.args[0], post.call_args.kwargs
    assert url == "https://abc.supabase.co/storage/v1/object/public/gallery/1/a%20photo.jpg"
    assert kwargs["data"] == b"bytes" and kwargs["headers"]["Authorization"] == "Bearer K" and kwargs["headers"]["x-upsert"] == "true"
    assert delete.call_args.args[0] == url
    shown = storage.url_for("gallery/1/a photo.jpg")
    assert shown == "https://abc.supabase.co/storage/v1/object/public/public/gallery/1/a%20photo.jpg"
    assert storage.key_from_url(shown) == "gallery/1/a photo.jpg" and storage.key_from_url("https://other.example/x.jpg") is None


def test_deleting_a_file_that_is_already_gone_is_fine_but_other_errors_are_not():
    storage = SupabaseProjectStorage(project_url="https://abc.supabase.co", service_key="K", bucket="public", public=True)
    with patch("app.storage.service.requests.delete", return_value=_response(404)):
        storage.delete("x.jpg")
    with patch("app.storage.service.requests.delete", return_value=_response(500)), pytest.raises(RuntimeError):
        storage.delete("x.jpg")


def test_private_storage_gives_signed_time_limited_urls_that_cannot_be_reversed():
    storage = SupabaseProjectStorage(project_url="https://abc.supabase.co", service_key="K", bucket="private", public=False)
    with patch("app.storage.service.requests.post", return_value=_response(payload={"signedURL": "/object/sign/private/r.pdf?token=T"})) as post:
        url = storage.url_for("receipts/r.pdf")
    assert url == "https://abc.supabase.co/storage/v1/object/sign/private/r.pdf?token=T"
    assert post.call_args.kwargs["json"] == {"expiresIn": 3600}
    assert storage.key_from_url(url) is None


def test_the_accessors_use_the_served_squares_own_buckets_and_the_server_wide_ones_otherwise():
    app = create_app("testing")
    with app.test_request_context():
        assert isinstance(get_public_storage(), FakeStorageService)  # no square: the server-wide storage
        g.tenant = SQUARE
        public, private = get_public_storage(), get_private_storage()
        assert isinstance(public, SupabaseProjectStorage) and isinstance(private, SupabaseProjectStorage)
        assert public.url_for("a.jpg").startswith("https://abc.supabase.co/storage/v1/object/public/public/")
        assert get_public_storage() is public  # one client per square, kept


def test_the_sender_shows_the_squares_name_in_front_of_the_one_verified_address():
    assert sender_for("First Org", "BCA Oslo <noreply@mail.example.org>") == "First Org <noreply@mail.example.org>"
    assert sender_for("Club, the \"best\"\nOne", "x <noreply@mail.example.org>").endswith("<noreply@mail.example.org>")
    assert "\n" not in sender_for("A\nB", "x <noreply@mail.example.org>")
    assert sender_for("", "BCA Oslo <noreply@mail.example.org>") == "BCA Oslo <noreply@mail.example.org>"
    assert sender_for("First Org", "not an address") == "not an address"


def test_a_served_squares_mail_goes_out_under_its_own_name():
    app = create_app("testing")
    app.config.update(RESEND_API_KEY="re_key", EMAIL_FROM="BCA Oslo <noreply@mail.example.org>")
    app.extensions["email_service"] = ResendEmailService(api_key="re_key", from_address="BCA Oslo <noreply@mail.example.org>")
    with app.test_request_context():
        assert get_email_service() is app.extensions["email_service"]  # no square: the configured sender
        g.tenant = SQUARE
        service = get_email_service()
        assert isinstance(service, ResendEmailService) and service._from_address == "First Org <noreply@mail.example.org>"


def test_links_in_emails_point_at_the_host_of_the_served_square():
    from app.common.urls import frontend_base_url

    app = create_app("testing")
    app.config["FRONTEND_ORIGIN"] = "https://bca-oslo.org,http://localhost:5173"
    with app.test_request_context(base_url="https://first-org.rootsquares.com"):
        assert frontend_base_url() == "https://bca-oslo.org"  # no square: the configured origin
        g.tenant = SQUARE
        assert frontend_base_url() == "https://first-org.rootsquares.com"
    with app.test_request_context(base_url="http://first-org.localhost:5274"):
        g.tenant = SQUARE
        assert frontend_base_url() == "http://first-org.localhost:5274"



def test_a_neon_square_uses_its_own_s3_compatible_storage():
    from dataclasses import replace

    from app.storage.service import S3CompatibleStorage

    neon = replace(
        SQUARE,
        auth_provider="neon",
        storage_url="",
        storage_key="",
        s3_endpoint="https://br-1.storage.c-1.eu-central-1.aws.neon.tech",
        s3_region="eu-central-1",
        s3_access_key="nak_1",
        s3_secret_key="nsk_1",
    )
    app = create_app("testing")
    with app.test_request_context():
        g.tenant = neon
        public, private = get_public_storage(), get_private_storage()
        assert isinstance(public, S3CompatibleStorage) and isinstance(private, S3CompatibleStorage)
        assert public.url_for("a/b.jpg") == "https://br-1.storage.c-1.eu-central-1.aws.neon.tech/public/a/b.jpg"  # a public_read object: <endpoint>/<bucket>/<key>
        assert public.key_from_url("https://br-1.storage.c-1.eu-central-1.aws.neon.tech/public/a/b.jpg") == "a/b.jpg"
        assert "X-Amz-Signature" in private.url_for("a.pdf")  # a private object is read through a signed link
        assert get_public_storage() is public
