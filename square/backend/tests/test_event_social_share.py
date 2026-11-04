"""Tests for event social share (2 tests), e.g. social urls round trip validate and qr endpoint; ticket limits round trip validate and show on the public event."""
from unittest.mock import patch

from app import create_app
from app.extensions import db
from tests.auth_helpers import FakeJWKClient, auth_header, make_user_and_token

PAYLOAD = {
    "title": "Mahalaya 2026",
    "slug": "mahalaya-2026",
    "event_type": "festival",
    "start_datetime": "2099-10-10T16:00:00+00:00",
    "published": True,
}


def test_social_urls_round_trip_validate_and_qr_endpoint():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        _, token = make_user_and_token(role="admin")
        headers = auth_header(token)
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            created = client.post(
                "/api/admin/events",
                json={**PAYLOAD, "facebook_url": "https://facebook.com/events/1", "instagram_url": None},
                headers=headers,
            )
            assert created.status_code == 201
            event_id = created.get_json()["id"]
            assert created.get_json()["facebook_url"] == "https://facebook.com/events/1"
            assert created.get_json()["instagram_url"] is None

            detail = client.get("/api/events/mahalaya-2026").get_json()
            assert detail["facebook_url"] == "https://facebook.com/events/1"
            assert detail["instagram_url"] is None

            bad = client.patch(f"/api/admin/events/{event_id}", json={"instagram_url": "javascript:x"}, headers=headers)
            assert bad.status_code == 400

            qr = client.get("/api/events/mahalaya-2026/qr").get_json()
            assert qr["url"].endswith("/events/mahalaya-2026")
            assert qr["qr"].startswith("data:image/png;base64,")
            assert client.get("/api/events/nope/qr").status_code == 404
        db.drop_all()


def test_ticket_limits_round_trip_validate_and_show_on_the_public_event():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        _, token = make_user_and_token(role="admin")
        headers = auth_header(token)
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            created = client.post(
                "/api/admin/events",
                json={**PAYLOAD, "max_tickets_per_email": 4, "coupon_max_adult": 2},
                headers=headers,
            ).get_json()
            assert (created["max_tickets_per_email"], created["coupon_max_adult"], created["coupon_max_child"]) == (4, 2, None)
            public = client.get("/api/events/mahalaya-2026").get_json()
            assert (public["max_tickets_per_email"], public["coupon_max_adult"], public["coupon_max_child"]) == (4, 2, None)
            for bad in (0, -1, "3", 1.5, True):
                r = client.patch(f"/api/admin/events/{created['id']}", json={"coupon_max_child": bad}, headers=headers)
                assert r.status_code == 400 and "coupon_max_child" in r.get_json()["errors"]
            cleared = client.patch(f"/api/admin/events/{created['id']}", json={"max_tickets_per_email": None}, headers=headers)
            assert cleared.get_json()["max_tickets_per_email"] is None
        db.drop_all()
