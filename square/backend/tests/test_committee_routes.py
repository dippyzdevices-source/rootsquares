"""Tests for committee routes (3 tests), e.g. list committee returns only active members ordered by display order; list committee returns only public safe fields; list committee is empty when no members."""
from app import create_app
from app.extensions import db


def _new_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
    return app


def test_list_committee_returns_only_active_members_ordered_by_display_order():
    from app.committee.models import CommitteeMember

    app = _new_app()
    with app.app_context():
        db.session.add_all(
            [
                CommitteeMember(name="B Person", role="Treasurer", display_order=2, is_active=True),
                CommitteeMember(name="A Person", role="President", display_order=1, is_active=True),
                CommitteeMember(name="Hidden Person", role="Secretary", display_order=0, is_active=False),
            ]
        )
        db.session.commit()

        response = app.test_client().get("/api/committee")

        assert response.status_code == 200
        items = response.get_json()["items"]
        assert [i["name"] for i in items] == ["A Person", "B Person"]
        db.drop_all()


def test_list_committee_returns_only_public_safe_fields():
    from app.committee.models import CommitteeMember

    app = _new_app()
    with app.app_context():
        member = CommitteeMember(
            name="Priya Das",
            role="President",
            address="123 Main St",
            email="priya@bcaoslo.no",
            phone="+47 401 22 318",
            member_since=1994,
            quote="Somebody has to unlock the hall at seven.",
            is_active=True,
        )
        db.session.add(member)
        db.session.commit()

        response = app.test_client().get("/api/committee")

        item = response.get_json()["items"][0]
        assert set(item.keys()) == {
            "id", "name", "sub_name", "role", "portrait_url", "address", "email", "phone", "member_since", "quote", "published",
        }
        assert item["email"] == "priya@bcaoslo.no"
        assert item["phone"] == "+47 401 22 318"
        assert item["member_since"] == 1994
        assert item["quote"] == "Somebody has to unlock the hall at seven."
        assert "is_active" not in item
        assert "created_at" not in item
        db.drop_all()


def test_list_committee_is_empty_when_no_members():
    app = _new_app()
    with app.app_context():
        response = app.test_client().get("/api/committee")
        assert response.status_code == 200
        assert response.get_json()["items"] == []
        db.drop_all()
