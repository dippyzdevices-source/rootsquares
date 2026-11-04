"""Tests for admin members routes (26 tests), e.g. admin routes reject requests with no token; admin routes reject a non admin role; admin list members includes latest membership."""
from datetime import date
from unittest.mock import patch

from app import create_app
from app.extensions import db
from app.members.models import Member
from app.memberships.models import Membership
from tests.auth_helpers import FakeJWKClient, auth_header, make_user_and_token


def _new_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
    return app


def _admin_headers():
    _, token = make_user_and_token(role="admin")
    return auth_header(token)


def _make_member(name="Priya Das", email="priya@example.com", with_membership=False):
    user, _ = make_user_and_token(email=email)
    member = Member(user_id=user.id, name=name)
    db.session.add(member)
    db.session.commit()
    if with_membership:
        _add_membership(member)
    return member


def _add_membership(member):
    # The Members list shows people who hold (or held) a membership of any status.
    db.session.add(Membership(member_id=member.id, membership_type="individual", status="active", start_date=date(2026, 1, 1)))
    db.session.commit()


def test_admin_routes_reject_requests_with_no_token():
    app = _new_app()
    with app.app_context():
        response = app.test_client().get("/api/admin/members")
        assert response.status_code == 401
        db.drop_all()


def test_admin_routes_reject_a_non_admin_role():
    app = _new_app()
    with app.app_context():
        _, token = make_user_and_token(role="member")
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get("/api/admin/members", headers=auth_header(token))
        assert response.status_code == 403
        db.drop_all()


def test_admin_list_members_includes_latest_membership():
    app = _new_app()
    with app.app_context():
        member = _make_member()
        db.session.add(
            Membership(
                member_id=member.id,
                membership_type="individual",
                status="active",
                start_date=date(2026, 1, 1),
            )
        )
        db.session.commit()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get("/api/admin/members", headers=_admin_headers())

        assert response.status_code == 200
        items = response.get_json()["items"]
        assert len(items) == 1
        assert items[0]["name"] == "Priya Das"
        assert items[0]["email"] == "priya@example.com"
        latest = items[0]["latest_membership"]
        assert (latest["membership_type"], latest["status"]) == ("individual", "active")
        db.drop_all()


def test_admin_list_members_filters_by_search_query():
    app = _new_app()
    with app.app_context():
        _make_member(name="Priya Das", email="priya@example.com", with_membership=True)
        _make_member(name="Rohan Sen", email="rohan@example.com", with_membership=True)

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get(
                "/api/admin/members?q=rohan", headers=_admin_headers()
            )

        items = response.get_json()["items"]
        assert len(items) == 1
        assert items[0]["name"] == "Rohan Sen"
        db.drop_all()


def test_admin_list_members_filters_by_linked_user_role():
    app = _new_app()
    with app.app_context():
        volunteer_user, _ = make_user_and_token(role="volunteer", email="volunteer@example.com")
        db.session.add(Member(user_id=volunteer_user.id, name="Vera Volunteer"))
        _make_member(name="Priya Das", email="priya@example.com")  # plain "member" role
        db.session.add(Member(name="Imported, No Login"))  # user_id is None entirely
        db.session.commit()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get(
                "/api/admin/members?role=volunteer", headers=_admin_headers()
            )

        items = response.get_json()["items"]
        assert len(items) == 1
        assert items[0]["name"] == "Vera Volunteer"
        db.drop_all()


def test_admin_get_member_returns_404_for_unknown_id():
    app = _new_app()
    with app.app_context():
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get("/api/admin/members/999", headers=_admin_headers())
        assert response.status_code == 404
        db.drop_all()


def test_admin_get_member_returns_full_detail_with_membership_history():
    app = _new_app()
    with app.app_context():
        member = _make_member()
        db.session.add(
            Membership(
                member_id=member.id,
                membership_type="individual",
                status="expired",
                start_date=date(2025, 1, 1),
                end_date=date(2025, 12, 31),
            )
        )
        db.session.add(
            Membership(
                member_id=member.id,
                membership_type="individual",
                status="active",
                start_date=date(2026, 1, 1),
            )
        )
        db.session.commit()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get(
                f"/api/admin/members/{member.id}", headers=_admin_headers()
            )

        assert response.status_code == 200
        data = response.get_json()
        assert data["email"] == "priya@example.com"
        assert len(data["memberships"]) == 2
        assert data["memberships"][0]["status"] == "active"
        db.drop_all()


def test_admin_update_member_edits_profile_fields():
    app = _new_app()
    with app.app_context():
        member = _make_member()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().patch(
                f"/api/admin/members/{member.id}",
                json={"address": "Oslo, Norway"},
                headers=_admin_headers(),
            )

        assert response.status_code == 200
        assert response.get_json()["address"] == "Oslo, Norway"
        db.drop_all()


def test_admin_update_member_rejects_a_blank_name():
    app = _new_app()
    with app.app_context():
        member = _make_member()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().patch(
                f"/api/admin/members/{member.id}",
                json={"name": "  "},
                headers=_admin_headers(),
            )

        assert response.status_code == 400
        assert "name" in response.get_json()["errors"]
        db.drop_all()


def test_admin_update_member_returns_404_for_unknown_id():
    app = _new_app()
    with app.app_context():
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().patch(
                "/api/admin/members/999", json={"address": "Oslo"}, headers=_admin_headers()
            )
        assert response.status_code == 404
        db.drop_all()


def test_admin_list_members_includes_an_unlinked_imported_member():
    app = _new_app()
    with app.app_context():
        imported = Member(name="Imported Person", email="imported@example.com")
        db.session.add(imported)
        db.session.commit()
        _add_membership(imported)

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get("/api/admin/members", headers=_admin_headers())

        data = response.get_json()
        assert len(data["items"]) == 1
        assert data["items"][0]["email"] == "imported@example.com"
        assert data["items"][0]["linked"] is False
        db.drop_all()


def test_admin_list_members_searches_by_email_for_unlinked_members():
    app = _new_app()
    with app.app_context():
        imported = Member(name="Imported Person", email="imported@example.com")
        db.session.add(imported)
        db.session.commit()
        _add_membership(imported)

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get(
                "/api/admin/members?q=imported@example.com", headers=_admin_headers()
            )

        assert len(response.get_json()["items"]) == 1
        db.drop_all()


def test_admin_get_member_detail_for_an_unlinked_imported_member():
    app = _new_app()
    with app.app_context():
        member = Member(name="Imported Person", email="imported@example.com", phone="+4712345678")
        db.session.add(member)
        db.session.commit()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get(
                f"/api/admin/members/{member.id}", headers=_admin_headers()
            )

        data = response.get_json()
        assert data["email"] == "imported@example.com"
        assert data["phone"] == "+4712345678"
        assert data["linked"] is False
        db.drop_all()


def test_admin_create_family_member_success():
    app = _new_app()
    with app.app_context():
        member = _make_member()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                f"/api/admin/members/{member.id}/family",
                json={"name": "Rohan", "relationship_type": "child", "age": 8},
                headers=headers,
            )

        assert response.status_code == 201
        data = response.get_json()
        assert data["name"] == "Rohan"
        assert data["relationship_type"] == "child"
        assert data["age"] == 8
        db.drop_all()


def test_admin_create_family_member_returns_404_for_unknown_member():
    app = _new_app()
    with app.app_context():
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/members/999/family",
                json={"name": "Rohan", "relationship_type": "child"},
                headers=headers,
            )
        assert response.status_code == 404
        db.drop_all()


def test_admin_create_family_member_rejects_an_invalid_relationship():
    app = _new_app()
    with app.app_context():
        member = _make_member()
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                f"/api/admin/members/{member.id}/family",
                json={"name": "Rohan", "relationship_type": "friend"},
                headers=headers,
            )
        assert response.status_code == 400
        assert "relationship_type" in response.get_json()["errors"]
        db.drop_all()


def test_admin_get_member_detail_includes_family_members():
    app = _new_app()
    with app.app_context():
        from app.members.models import FamilyMember

        member = _make_member()
        db.session.add(FamilyMember(member_id=member.id, name="Anita", relationship_type="spouse"))
        db.session.commit()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get(f"/api/admin/members/{member.id}", headers=headers)

        family = response.get_json()["family_members"]
        assert len(family) == 1
        assert family[0]["name"] == "Anita"
        db.drop_all()


def test_admin_update_family_member_success():
    app = _new_app()
    with app.app_context():
        from app.members.models import FamilyMember

        member = _make_member()
        family_member = FamilyMember(member_id=member.id, name="Anita", relationship_type="spouse")
        db.session.add(family_member)
        db.session.commit()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().patch(
                f"/api/admin/members/{member.id}/family/{family_member.id}",
                json={"age": 34},
                headers=headers,
            )

        assert response.status_code == 200
        assert response.get_json()["age"] == 34
        db.drop_all()


def test_admin_update_family_member_returns_404_for_a_different_member():
    app = _new_app()
    with app.app_context():
        from app.members.models import FamilyMember

        member_a = _make_member(name="A", email="a@example.com")
        member_b = _make_member(name="B", email="b@example.com")
        family_member = FamilyMember(member_id=member_a.id, name="Anita", relationship_type="spouse")
        db.session.add(family_member)
        db.session.commit()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().patch(
                f"/api/admin/members/{member_b.id}/family/{family_member.id}",
                json={"age": 34},
                headers=headers,
            )

        assert response.status_code == 404
        db.drop_all()


def test_admin_delete_family_member_success():
    app = _new_app()
    with app.app_context():
        from app.members.models import FamilyMember

        member = _make_member()
        family_member = FamilyMember(member_id=member.id, name="Anita", relationship_type="spouse")
        db.session.add(family_member)
        db.session.commit()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            response = client.delete(
                f"/api/admin/members/{member.id}/family/{family_member.id}", headers=headers
            )
            assert response.status_code == 204

            detail = client.get(f"/api/admin/members/{member.id}", headers=headers)

        assert detail.get_json()["family_members"] == []
        db.drop_all()


def test_deleting_a_member_cascades_to_their_family_members():
    app = _new_app()
    with app.app_context():
        from app.members.models import FamilyMember

        member = _make_member()
        db.session.add(FamilyMember(member_id=member.id, name="Anita", relationship_type="spouse"))
        db.session.commit()

        db.session.delete(member)
        db.session.commit()

        assert FamilyMember.query.count() == 0
        db.drop_all()


def test_export_members_returns_an_xlsx_file():
    from io import BytesIO

    from openpyxl import load_workbook

    app = _new_app()
    with app.app_context():
        _make_member(name="Priya Das", email="priya@example.com", with_membership=True)

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get(
                "/api/admin/members/export", headers=_admin_headers()
            )

        assert response.status_code == 200
        assert "spreadsheetml" in response.content_type
        assert "attachment" in response.headers["Content-Disposition"]

        workbook = load_workbook(BytesIO(response.data))
        rows = list(workbook.active.iter_rows(values_only=True))
        assert rows[0][0] == "Name"
        assert rows[1][0] == "Priya Das"
        assert rows[1][1] == "priya@example.com"
        db.drop_all()


def test_list_members_filters_by_the_latest_memberships_type_and_combines_with_status():
    from datetime import date

    from app.members.models import Member
    from app.memberships.models import Membership, MembershipType

    app = _new_app()
    with app.app_context():
        for name in ("adult", "child"):
            db.session.add(MembershipType(name=name, price=100, billing_frequency="yearly"))
        db.session.commit()
        rows = [
            ("Priya Das", "adult", "active"),
            ("Arjun Sen", "child", "active"),
            ("Mina Roy", "adult", "expired"),
            ("No Membership", None, None),
        ]
        for name, mtype, status in rows:
            member = Member(name=name)
            db.session.add(member)
            db.session.commit()
            if mtype:
                db.session.add(Membership(member_id=member.id, membership_type=mtype, status=status,
                                          start_date=date(2026, 1, 1)))
        db.session.commit()
        headers = _admin_headers()

        def names(query):
            with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
                response = app.test_client().get(f"/api/admin/members?{query}", headers=headers)
            assert response.status_code == 200
            return {m["name"] for m in response.get_json()["items"]}

        assert names("membership_type=adult") == {"Priya Das", "Mina Roy"}
        assert names("membership_type=child") == {"Arjun Sen"}
        assert names("membership_type=adult&status=active") == {"Priya Das"}
        # someone with no membership of any status is not listed under Members (they are under Users)
        assert names("") == {"Priya Das", "Arjun Sen", "Mina Roy"}
        db.drop_all()


def test_export_members_uses_the_same_search_as_the_list():
    from io import BytesIO

    from openpyxl import load_workbook

    app = _new_app()
    with app.app_context():
        _make_member(name="Priya Das", email="priya@example.com", with_membership=True)
        _make_member(name="Rohan Sen", email="rohan@example.com", with_membership=True)

        def exported(query):
            with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
                response = app.test_client().get(f"/api/admin/members/export{query}", headers=_admin_headers())
            assert response.status_code == 200
            return [r[0] for r in list(load_workbook(BytesIO(response.data)).active.iter_rows(values_only=True))[1:]]

        assert exported("") == ["Priya Das", "Rohan Sen"]
        assert exported("?q=rohan") == ["Rohan Sen"]
        assert exported("?q=nobody") == []
        db.drop_all()


def test_list_leaves_out_people_with_no_membership_but_a_role_lookup_keeps_them():
    app = _new_app()
    with app.app_context():
        _make_member(name="Only Signed In", email="signed@example.com")  # saved a profile, never a membership
        holder = _make_member(name="Holds One", email="holds@example.com", with_membership=True)
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            headers = _admin_headers()
            names = [m["name"] for m in client.get("/api/admin/members", headers=headers).get_json()["items"]]
            assert names == ["Holds One"]
            # their member page is still reachable (e.g. from Members -> Users) to give them a membership
            assert client.get(f"/api/admin/members/{holder.id + 0}", headers=headers).status_code == 200
            by_role = client.get("/api/admin/members?role=member", headers=headers).get_json()["items"]
            assert {m["name"] for m in by_role} >= {"Only Signed In", "Holds One"}
        db.drop_all()


def test_admin_can_resend_a_welcome_email_to_a_member_with_an_email():
    app = _new_app()
    with app.app_context():
        linked = _make_member(name="Linked One", email="linked@example.com", with_membership=True)
        imported = Member(name="Imported", email="imported@example.com")  # never signed in
        no_email = Member(name="No Email")
        db.session.add_all([imported, no_email])
        db.session.commit()
        sent = app.extensions["email_service"].sent_emails
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            headers = _admin_headers()
            assert client.post(f"/api/admin/members/{linked.id}/welcome-email", headers=headers).get_json()["sent_to"] == "linked@example.com"
            assert client.post(f"/api/admin/members/{imported.id}/welcome-email", headers=headers).status_code == 200
            assert [m["to"] for m in sent[-2:]] == ["linked@example.com", "imported@example.com"]
            assert client.post(f"/api/admin/members/{no_email.id}/welcome-email", headers=headers).status_code == 400
            assert client.post("/api/admin/members/9999/welcome-email", headers=headers).status_code == 404
        db.drop_all()
