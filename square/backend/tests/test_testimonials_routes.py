"""Tests for testimonials routes (9 tests), e.g. list testimonials only returns active ones; list testimonials orders by sort order; list testimonials includes expected fields."""
from app import create_app
from app.extensions import db
from app.testimonials.models import Testimonial


def _new_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
    return app


def _add_testimonial(**overrides):
    defaults = {"quote": "BCA Oslo feels like family.", "author_name": "Priya Das"}
    defaults.update(overrides)
    testimonial = Testimonial(**defaults)
    db.session.add(testimonial)
    db.session.commit()
    return testimonial


def test_list_testimonials_only_returns_active_ones():
    app = _new_app()
    with app.app_context():
        _add_testimonial(author_name="Active", is_active=True)
        _add_testimonial(author_name="Inactive", is_active=False)

        response = app.test_client().get("/api/testimonials")
        names = {item["author_name"] for item in response.get_json()["items"]}

        assert names == {"Active"}
        db.drop_all()


def test_list_testimonials_orders_by_sort_order():
    app = _new_app()
    with app.app_context():
        _add_testimonial(author_name="Second", sort_order=2)
        _add_testimonial(author_name="First", sort_order=1)

        response = app.test_client().get("/api/testimonials")
        names = [item["author_name"] for item in response.get_json()["items"]]

        assert names == ["First", "Second"]
        db.drop_all()


def test_list_testimonials_includes_expected_fields():
    app = _new_app()
    with app.app_context():
        _add_testimonial(author_context="Member since 2020", photo_url="https://x/p.jpg")

        response = app.test_client().get("/api/testimonials")
        item = response.get_json()["items"][0]

        assert item["quote"] == "BCA Oslo feels like family."
        assert item["author_name"] == "Priya Das"
        assert item["author_context"] == "Member since 2020"
        assert item["photo_url"] == "https://x/p.jpg"
        db.drop_all()


def test_list_testimonials_excludes_pending_ones_even_if_active():
    # is_active alone is not enough — a public submission is never shown until an admin has
    # actually reviewed and approved it, regardless of its is_active flag.
    app = _new_app()
    with app.app_context():
        _add_testimonial(author_name="Awaiting review", status="pending", is_active=True)
        _add_testimonial(author_name="Reviewed", status="approved", is_active=True)

        response = app.test_client().get("/api/testimonials")
        names = {item["author_name"] for item in response.get_json()["items"]}

        assert names == {"Reviewed"}
        db.drop_all()


def test_submit_testimonial_creates_a_pending_inactive_row():
    app = _new_app()
    with app.app_context():
        response = app.test_client().post(
            "/api/testimonials",
            json={
                "quote": "A wonderful community.",
                "author_name": "Rohan Sen",
                "author_context": "Member since 2022",
            },
        )

        assert response.status_code == 201
        data = response.get_json()
        assert data["status"] == "pending"

        testimonial = db.session.get(Testimonial, data["id"])
        assert testimonial.status == "pending"
        assert testimonial.is_active is False
        assert testimonial.quote == "A wonderful community."
        assert testimonial.author_name == "Rohan Sen"
        assert testimonial.author_context == "Member since 2022"
        db.drop_all()


def test_submitted_testimonial_does_not_appear_publicly_until_approved():
    app = _new_app()
    with app.app_context():
        app.test_client().post(
            "/api/testimonials", json={"quote": "Great people.", "author_name": "Anita Roy"}
        )

        response = app.test_client().get("/api/testimonials")

        assert response.get_json()["items"] == []
        db.drop_all()


def test_submit_testimonial_requires_quote_and_author_name():
    app = _new_app()
    with app.app_context():
        response = app.test_client().post("/api/testimonials", json={})

        assert response.status_code == 400
        errors = response.get_json()["errors"]
        assert "quote" in errors
        assert "author_name" in errors
        db.drop_all()


def test_submit_testimonial_rejects_an_overlong_quote():
    app = _new_app()
    with app.app_context():
        response = app.test_client().post(
            "/api/testimonials",
            json={"quote": "x" * 1001, "author_name": "Rohan Sen"},
        )

        assert response.status_code == 400
        assert "quote" in response.get_json()["errors"]
        db.drop_all()


def test_submit_testimonial_allows_omitting_optional_fields():
    app = _new_app()
    with app.app_context():
        response = app.test_client().post(
            "/api/testimonials",
            json={"quote": "Lovely festival.", "author_name": "Priya Das"},
        )

        assert response.status_code == 201
        testimonial = db.session.get(Testimonial, response.get_json()["id"])
        assert testimonial.author_context is None
        assert testimonial.photo_url is None
        db.drop_all()
