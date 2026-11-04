"""Tests for members routes (25 tests), e.g. get my member requires auth; get my member returns 404 before a profile is created; put my member creates then get returns it."""
from unittest.mock import patch

from app import create_app
from app.extensions import db
from tests.auth_helpers import FakeJWKClient, auth_header, make_user_and_token


def _new_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
    return app


def test_get_my_member_requires_auth():
    app = _new_app()
    with app.app_context():
        response = app.test_client().get("/api/members/me")
        assert response.status_code == 401
        db.drop_all()


def test_get_my_member_returns_404_before_a_profile_is_created():
    app = _new_app()
    with app.app_context():
        _, token = make_user_and_token()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get("/api/members/me", headers=auth_header(token))
        assert response.status_code == 404
        db.drop_all()


def test_put_my_member_creates_then_get_returns_it():
    app = _new_app()
    with app.app_context():
        _, token = make_user_and_token()
        headers = auth_header(token)

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            put_response = client.put(
                "/api/members/me",
                json={"name": "Priya Das", "address": "Oslo, Norway"},
                headers=headers,
            )
            assert put_response.status_code == 200
            assert put_response.get_json()["name"] == "Priya Das"

            get_response = client.get("/api/members/me", headers=headers)
            data = get_response.get_json()
            assert data["name"] == "Priya Das"
            assert data["address"] == "Oslo, Norway"

        db.drop_all()


def test_put_my_member_requires_a_name():
    app = _new_app()
    with app.app_context():
        _, token = make_user_and_token()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().put(
                "/api/members/me", json={}, headers=auth_header(token)
            )
        assert response.status_code == 400
        assert "name" in response.get_json()["errors"]
        db.drop_all()


def test_put_my_member_updates_an_existing_profile_without_duplicating():
    app = _new_app()
    with app.app_context():
        _, token = make_user_and_token()
        headers = auth_header(token)

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            client.put("/api/members/me", json={"name": "Priya Das"}, headers=headers)
            response = client.put("/api/members/me", json={"name": "Priya D."}, headers=headers)

        assert response.status_code == 200
        assert response.get_json()["name"] == "Priya D."

        from app.members.models import Member

        assert Member.query.count() == 1

        db.drop_all()


def test_get_my_member_auto_links_an_unlinked_imported_member_by_email():
    from app.members.models import Member

    app = _new_app()
    with app.app_context():
        db.session.add(Member(name="Priya Das", email="priya@example.com", address="Oslo"))
        db.session.commit()

        user, token = make_user_and_token(email="priya@example.com")
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get("/api/members/me", headers=auth_header(token))

        assert response.status_code == 200
        data = response.get_json()
        assert data["name"] == "Priya Das"
        assert data["address"] == "Oslo"

        linked = Member.query.filter_by(email="priya@example.com").one()
        assert linked.user_id == user.id
        assert Member.query.count() == 1  # no duplicate was created
        db.drop_all()


def test_get_my_member_does_not_link_an_already_linked_member_with_a_different_email():
    from app.members.models import Member

    app = _new_app()
    with app.app_context():
        other_user, _ = make_user_and_token(email="other@example.com")
        db.session.add(Member(user_id=other_user.id, name="Other Person", email="other@example.com"))
        db.session.commit()

        _, token = make_user_and_token(email="priya@example.com")
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get("/api/members/me", headers=auth_header(token))

        assert response.status_code == 404
        db.drop_all()


def test_upload_my_photo_requires_auth():
    app = _new_app()
    with app.app_context():
        response = app.test_client().post("/api/members/me/photo")
        assert response.status_code == 401
        db.drop_all()


def test_upload_my_photo_requires_a_profile_first():
    app = _new_app()
    with app.app_context():
        _, token = make_user_and_token()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/members/me/photo", headers=auth_header(token)
            )
        assert response.status_code == 400
        db.drop_all()


def test_upload_my_photo_success():
    from io import BytesIO

    from PIL import Image

    app = _new_app()
    with app.app_context():
        _, token = make_user_and_token()
        headers = auth_header(token)

        image = Image.new("RGB", (400, 400), color="blue")
        buffer = BytesIO()
        image.save(buffer, format="JPEG")
        buffer.seek(0)

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            client.put("/api/members/me", json={"name": "Priya Das"}, headers=headers)
            response = client.post(
                "/api/members/me/photo",
                data={"file": (buffer, "photo.jpg")},
                headers=headers,
                content_type="multipart/form-data",
            )

        assert response.status_code == 200
        data = response.get_json()
        assert data["photo_url"]

        from app.members.models import Member

        member = Member.query.filter_by(name="Priya Das").one()
        assert member.photo_url == data["photo_url"]
        db.drop_all()


def _jpeg_file(name="photo.jpg"):
    from io import BytesIO

    from PIL import Image

    image = Image.new("RGB", (400, 400), color="blue")
    buffer = BytesIO()
    image.save(buffer, format="JPEG")
    buffer.seek(0)
    return (buffer, name)


def test_replacing_my_photo_deletes_the_old_one_from_storage():
    app = _new_app()
    with app.app_context():
        _, token = make_user_and_token()
        headers = auth_header(token)

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            client.put("/api/members/me", json={"name": "Priya Das"}, headers=headers)

            first = client.post(
                "/api/members/me/photo",
                data={"file": _jpeg_file("first.jpg")},
                headers=headers,
                content_type="multipart/form-data",
            )
            storage = app.extensions["public_storage"]
            old_key = storage.key_from_url(first.get_json()["photo_url"])
            assert old_key in storage.objects

            second = client.post(
                "/api/members/me/photo",
                data={"file": _jpeg_file("second.jpg")},
                headers=headers,
                content_type="multipart/form-data",
            )

        assert second.status_code == 200
        new_key = storage.key_from_url(second.get_json()["photo_url"])
        assert old_key not in storage.objects
        assert new_key in storage.objects
        db.drop_all()


def test_upload_my_photo_rejects_a_non_image_file():
    app = _new_app()
    with app.app_context():
        _, token = make_user_and_token()
        headers = auth_header(token)
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            client.put("/api/members/me", json={"name": "Priya Das"}, headers=headers)
            response = client.post(
                "/api/members/me/photo",
                data={"file": (b"not an image", "photo.jpg")},
                headers=headers,
                content_type="multipart/form-data",
            )
        assert response.status_code == 400
        assert "file" in response.get_json()["errors"]
        db.drop_all()


def test_create_my_family_member_requires_profile_first():
    app = _new_app()
    with app.app_context():
        _, token = make_user_and_token()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/members/me/family",
                json={"name": "Anita", "relationship_type": "spouse"},
                headers=auth_header(token),
            )
        assert response.status_code == 400
        db.drop_all()


def test_create_my_family_member_requires_name_and_relationship():
    app = _new_app()
    with app.app_context():
        _, token = make_user_and_token()
        headers = auth_header(token)
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            client.put("/api/members/me", json={"name": "Priya Das"}, headers=headers)
            response = client.post("/api/members/me/family", json={}, headers=headers)

        assert response.status_code == 400
        assert set(response.get_json()["errors"]) == {"name", "relationship_type"}
        db.drop_all()


def test_create_my_family_member_rejects_an_invalid_relationship():
    app = _new_app()
    with app.app_context():
        _, token = make_user_and_token()
        headers = auth_header(token)
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            client.put("/api/members/me", json={"name": "Priya Das"}, headers=headers)
            response = client.post(
                "/api/members/me/family",
                json={"name": "Anita", "relationship_type": "friend"},
                headers=headers,
            )

        assert response.status_code == 400
        assert "relationship_type" in response.get_json()["errors"]
        db.drop_all()


def test_create_my_family_member_success_and_appears_on_get():
    app = _new_app()
    with app.app_context():
        _, token = make_user_and_token()
        headers = auth_header(token)
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            client.put("/api/members/me", json={"name": "Priya Das"}, headers=headers)
            create_response = client.post(
                "/api/members/me/family",
                json={"name": "Anita", "relationship_type": "spouse", "age": 34},
                headers=headers,
            )
            assert create_response.status_code == 201

            get_response = client.get("/api/members/me", headers=headers)

        family = get_response.get_json()["family_members"]
        assert len(family) == 1
        assert family[0]["name"] == "Anita"
        assert family[0]["relationship_type"] == "spouse"
        assert family[0]["age"] == 34
        db.drop_all()


def test_update_my_family_member_success():
    app = _new_app()
    with app.app_context():
        _, token = make_user_and_token()
        headers = auth_header(token)
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            client.put("/api/members/me", json={"name": "Priya Das"}, headers=headers)
            created = client.post(
                "/api/members/me/family",
                json={"name": "Anita", "relationship_type": "spouse"},
                headers=headers,
            ).get_json()

            response = client.patch(
                f"/api/members/me/family/{created['id']}", json={"age": 35}, headers=headers
            )

        assert response.status_code == 200
        assert response.get_json()["age"] == 35
        db.drop_all()


def test_update_my_family_member_returns_404_for_someone_elses_entry():
    app = _new_app()
    with app.app_context():
        _, owner_token = make_user_and_token(email="owner@example.com")
        owner_headers = auth_header(owner_token)
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            client.put("/api/members/me", json={"name": "Owner"}, headers=owner_headers)
            created = client.post(
                "/api/members/me/family",
                json={"name": "Anita", "relationship_type": "spouse"},
                headers=owner_headers,
            ).get_json()

            _, other_token = make_user_and_token(email="other@example.com")
            other_headers = auth_header(other_token)
            client.put("/api/members/me", json={"name": "Other"}, headers=other_headers)
            response = client.patch(
                f"/api/members/me/family/{created['id']}", json={"age": 40}, headers=other_headers
            )

        assert response.status_code == 404
        db.drop_all()


def test_delete_my_family_member_success():
    app = _new_app()
    with app.app_context():
        _, token = make_user_and_token()
        headers = auth_header(token)
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            client.put("/api/members/me", json={"name": "Priya Das"}, headers=headers)
            created = client.post(
                "/api/members/me/family",
                json={"name": "Anita", "relationship_type": "spouse"},
                headers=headers,
            ).get_json()

            response = client.delete(f"/api/members/me/family/{created['id']}", headers=headers)
            assert response.status_code == 204

            get_response = client.get("/api/members/me", headers=headers)

        assert get_response.get_json()["family_members"] == []
        db.drop_all()


def test_export_my_data_requires_auth():
    app = _new_app()
    with app.app_context():
        response = app.test_client().get("/api/members/me/export")
        assert response.status_code == 401
        db.drop_all()


def test_export_my_data_includes_account_and_profile():
    app = _new_app()
    with app.app_context():
        user, token = make_user_and_token(email="priya@example.com")
        headers = auth_header(token)

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            client.put("/api/members/me", json={"name": "Priya Das"}, headers=headers)
            response = client.get("/api/members/me/export", headers=headers)

        assert response.status_code == 200
        data = response.get_json()
        assert data["account"]["email"] == "priya@example.com"
        assert data["profile"]["name"] == "Priya Das"
        assert data["memberships"] == []
        assert data["orders"] == []
        db.drop_all()


def test_export_my_data_works_with_no_member_profile_yet():
    app = _new_app()
    with app.app_context():
        _, token = make_user_and_token()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get(
                "/api/members/me/export", headers=auth_header(token)
            )
        assert response.status_code == 200
        assert response.get_json()["profile"] is None
        db.drop_all()


def test_export_my_data_includes_own_orders_and_memberships_only():
    from datetime import date, datetime, timedelta, timezone

    from app.events.models import Event
    from app.memberships.models import Membership
    from app.orders.models import Order

    app = _new_app()
    with app.app_context():
        user, token = make_user_and_token(email="priya@example.com")
        headers = auth_header(token)

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            client.put("/api/members/me", json={"name": "Priya Das"}, headers=headers)

        from app.members.models import Member

        event = Event(title="Durga Puja 2026", slug="durga-puja-2026", event_type="festival",
                      start_datetime=datetime.now(timezone.utc) + timedelta(days=10))
        db.session.add(event)
        db.session.commit()

        member = Member.query.filter_by(user_id=user.id).first()
        db.session.add(
            Membership(member_id=member.id, membership_type="individual", status="active",
                       start_date=date(2026, 1, 1))
        )
        db.session.add(
            Order(order_number="BCA-2026-000001", event_id=event.id, user_id=user.id,
                  customer_name="Priya Das", customer_email="priya@example.com",
                  total_amount=15000)
        )
        # An unrelated user's order must never appear in this export.
        other_user, _ = make_user_and_token(email="other@example.com")
        db.session.add(
            Order(order_number="BCA-2026-000002", event_id=event.id, user_id=other_user.id,
                  customer_name="Other Person", customer_email="other@example.com",
                  total_amount=5000)
        )
        db.session.commit()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get("/api/members/me/export", headers=headers)

        data = response.get_json()
        assert len(data["memberships"]) == 1
        assert len(data["orders"]) == 1
        assert data["orders"][0]["order_number"] == "BCA-2026-000001"
        db.drop_all()


def test_get_my_task_assignments_returns_only_my_own_ordered_by_event_start():
    from datetime import datetime, timedelta, timezone

    from app.events.models import Event, EventTaskAssignment
    from app.members.models import Member

    app = _new_app()
    with app.app_context():
        user, token = make_user_and_token(email="priya@example.com")
        headers = auth_header(token)

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            app.test_client().put("/api/members/me", json={"name": "Priya Das"}, headers=headers)

        member = Member.query.filter_by(user_id=user.id).first()

        past_event = Event(
            title="Saraswati Puja 2025", slug="saraswati-puja-2025", event_type="festival",
            start_datetime=datetime.now(timezone.utc) - timedelta(days=30),
        )
        future_event = Event(
            title="Durga Puja 2026", slug="durga-puja-2026", event_type="festival",
            start_datetime=datetime.now(timezone.utc) + timedelta(days=10),
        )
        db.session.add_all([past_event, future_event])
        db.session.commit()

        db.session.add(EventTaskAssignment(event_id=future_event.id, member_id=member.id, category="food"))
        db.session.add(EventTaskAssignment(event_id=past_event.id, member_id=member.id, category="decoration"))

        # An unrelated member's assignment must never appear in this list.
        other_user, _ = make_user_and_token(email="other@example.com")
        other_member = Member(user_id=other_user.id, name="Other Person")
        db.session.add(other_member)
        db.session.commit()
        db.session.add(EventTaskAssignment(event_id=future_event.id, member_id=other_member.id, category="music_entertainment"))
        db.session.commit()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get("/api/members/me/task-assignments", headers=headers)

        assert response.status_code == 200
        items = response.get_json()["items"]
        assert len(items) == 2
        assert items[0]["event_title"] == "Saraswati Puja 2025"
        assert items[0]["category"] == "decoration"
        assert items[1]["event_title"] == "Durga Puja 2026"
        assert items[1]["category"] == "food"
        db.drop_all()


def test_get_my_task_assignments_returns_empty_list_before_a_profile_exists():
    app = _new_app()
    with app.app_context():
        _, token = make_user_and_token(email="new@example.com")
        headers = auth_header(token)

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get("/api/members/me/task-assignments", headers=headers)

        assert response.status_code == 200
        assert response.get_json()["items"] == []
        db.drop_all()
