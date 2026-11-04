"""Tests for event sub name (3 tests), e.g. sub name round trips through admin and public detail and can be cleare; event description style override round trips validates and is in the l; ticket layout defaults to sections round trips and rejects unknown val."""
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


def _new_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
    return app


def test_sub_name_round_trips_through_admin_and_public_detail_and_can_be_cleared():
    app = _new_app()
    with app.app_context():
        _, token = make_user_and_token(role="admin")
        headers = auth_header(token)
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            created = client.post(
                "/api/admin/events", json={**PAYLOAD, "sub_name": "  মহালয়া ২০২৬ "}, headers=headers
            )
            assert created.status_code == 201
            assert created.get_json()["sub_name"] == "মহালয়া ২০২৬"
            event_id = created.get_json()["id"]

            assert client.get("/api/events/mahalaya-2026").get_json()["sub_name"] == "মহালয়া ২০২৬"

            cleared = client.patch(f"/api/admin/events/{event_id}", json={"sub_name": None}, headers=headers)
            assert cleared.get_json()["sub_name"] is None
            assert client.get("/api/events/mahalaya-2026").get_json()["sub_name"] is None

            too_long = client.patch(
                f"/api/admin/events/{event_id}", json={"sub_name": "x" * 201}, headers=headers
            )
            assert too_long.status_code == 400
        db.drop_all()


def test_event_description_style_override_round_trips_validates_and_is_in_the_list_summary():
    app = _new_app()
    with app.app_context():
        _, token = make_user_and_token(role="admin")
        headers = auth_header(token)
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            created = client.post("/api/admin/events", json=PAYLOAD, headers=headers)
            event_id = created.get_json()["id"]
            assert created.get_json()["description_style"] is None

            set_ = client.patch(f"/api/admin/events/{event_id}", json={"description_style": "source"}, headers=headers)
            assert set_.get_json()["description_style"] == "source"
            assert client.get("/api/events/mahalaya-2026").get_json()["description_style"] == "source"
            assert client.get("/api/events").get_json()["items"][0]["description_style"] == "source"

            bad = client.patch(f"/api/admin/events/{event_id}", json={"description_style": "papyrus"}, headers=headers)
            assert bad.status_code == 400 and "description_style" in bad.get_json()["errors"]

            cleared = client.patch(f"/api/admin/events/{event_id}", json={"description_style": None}, headers=headers)
            assert cleared.get_json()["description_style"] is None
        db.drop_all()


def test_ticket_layout_defaults_to_sections_round_trips_and_rejects_unknown_values():
    app = _new_app()
    with app.app_context():
        _, token = make_user_and_token(role="admin")
        headers = auth_header(token)
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            created = client.post("/api/admin/events", json=PAYLOAD, headers=headers)
            assert created.get_json()["ticket_layout"] == "sections"
            event_id = created.get_json()["id"]

            changed = client.patch(f"/api/admin/events/{event_id}", json={"ticket_layout": "tabs"}, headers=headers)
            assert changed.get_json()["ticket_layout"] == "tabs"
            assert client.get("/api/events/mahalaya-2026").get_json()["ticket_layout"] == "tabs"

            bad = client.patch(f"/api/admin/events/{event_id}", json={"ticket_layout": "carousel"}, headers=headers)
            assert bad.status_code == 400
        db.drop_all()
