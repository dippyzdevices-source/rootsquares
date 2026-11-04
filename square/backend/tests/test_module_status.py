"""What a module holds and has pending, for the platform (rootsquares W8-R27)."""

from datetime import datetime, timedelta, timezone

from app import create_app
from app.config import TestingConfig
from app.extensions import db
from app.modules import MODULE_KEYS
from app.module_status import MODULE_STATUS
from app.newsletter.models import NewsletterIssue, Subscriber
from app.testimonials.models import Testimonial
from unittest.mock import patch

KEY = "test-internal-key"


def _app(key=KEY):
    with patch.object(TestingConfig, "PLATFORM_INTERNAL_KEY", key), patch.object(TestingConfig, "PLATFORM_DATABASE_URL", ""):
        app = create_app("testing")
    with app.app_context():
        db.create_all()
    return app


def test_every_module_has_a_status_function() -> None:
    assert list(MODULE_STATUS) == list(MODULE_KEYS)


def test_nobody_without_the_key_learns_that_the_address_exists() -> None:
    client = _app().test_client()
    assert client.get("/api/internal/modules/status").status_code == 404
    assert client.get("/api/internal/modules/status", headers={"X-Internal-Key": "wrong"}).status_code == 404
    assert _app("").test_client().get("/api/internal/modules/status", headers={"X-Internal-Key": ""}).status_code == 404  # no key configured: off


def test_empty_square_holds_nothing_and_has_nothing_pending() -> None:
    items = _app().test_client().get("/api/internal/modules/status", headers={"X-Internal-Key": KEY}).get_json()["items"]
    assert [i["key"] for i in items] == list(MODULE_KEYS)
    assert all(i["holds_data"] is False and i["pending"] == [] for i in items)  # a module that never held data shows nothing


def test_old_newsletter_history_and_waiting_testimonial_are_reported_without_numbers() -> None:
    app = _app()
    with app.app_context():
        db.session.add(NewsletterIssue(subject="Autumn", body_html="<p>x</p>", status="scheduled", scheduled_for=datetime.now(timezone.utc) + timedelta(days=3)))
        db.session.add(Subscriber(email="a@example.org", status="subscribed"))
        db.session.add(Testimonial(quote="Lovely", author_name="A", status="pending"))
        db.session.commit()
    answer = app.test_client().get("/api/internal/modules/status", headers={"X-Internal-Key": KEY})
    items = {i["key"]: i for i in answer.get_json()["items"]}
    assert items["newsletter"]["holds_data"] is True and items["gallery"]["holds_data"] is False
    assert items["newsletter"]["pending"] == []  # newsletters are Messages now: a scheduled one is reported by the Messages module
    assert items["testimonials"]["pending"] == ["Testimonials are waiting for approval."]
    # nothing but yes/no and sentences: no counts, no labels of what is held, no names or addresses
    assert set(items["newsletter"]) == {"key", "holds_data", "pending", "on"}
    assert "a@example.org" not in answer.get_data(as_text=True) and "Lovely" not in answer.get_data(as_text=True)
    assert not any(ch.isdigit() for i in items.values() for p in i["pending"] for ch in p)
