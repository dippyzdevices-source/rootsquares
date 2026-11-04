"""Tests for events (2 tests), e.g. event has expected defaults; event requires a unique slug."""
from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app import create_app
from app.events.models import Event
from app.extensions import db


def test_event_has_expected_defaults():
    app = create_app("testing")
    with app.app_context():
        db.create_all()

        event = Event(
            title="Durga Puja 2026",
            slug="durga-puja-2026",
            event_type="festival",
            start_datetime=datetime(2026, 10, 16, 18, 0, tzinfo=timezone.utc),
        )
        db.session.add(event)
        db.session.commit()

        saved = Event.query.filter_by(slug="durga-puja-2026").one()
        assert saved.status == "scheduled"
        assert saved.published is False
        assert saved.created_at is not None

        db.drop_all()


def test_event_requires_a_unique_slug():
    app = create_app("testing")
    with app.app_context():
        db.create_all()

        db.session.add(
            Event(
                title="Mahalaya 2026",
                slug="shared-slug",
                event_type="cultural",
                start_datetime=datetime(2026, 10, 2, tzinfo=timezone.utc),
            )
        )
        db.session.commit()

        db.session.add(
            Event(
                title="Another Event",
                slug="shared-slug",
                event_type="cultural",
                start_datetime=datetime(2026, 10, 3, tzinfo=timezone.utc),
            )
        )
        with pytest.raises(IntegrityError):
            db.session.commit()

        db.session.rollback()
        db.drop_all()
