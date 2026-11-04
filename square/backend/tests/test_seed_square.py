"""The demo data script (W17-R8): it fills a square with every scenario, once."""

import pytest

from app import create_app
from app.events.models import Event
from app.extensions import db
from app.orders.models import Order
from app.tickets.models import Ticket
from scripts.seed_square import MARKER_SLUG, seed_all


def test_seeds_every_scenario_and_refuses_to_run_twice():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        counts = seed_all("NOK")
        live = Event.query.filter_by(slug=MARKER_SLUG).one()
        assert live.published and live.status == "scheduled"
        assert {e.slug: (e.published, e.status) for e in Event.query.all()}["demo-winter-concert"] == (False, "scheduled")  # the draft
        assert Event.query.filter_by(status="completed").count() == 1 and Event.query.filter_by(status="cancelled").count() == 1
        assert {o.payment_status for o in Order.query.all()} >= {"paid", "pending", "pending_verification", "failed", "cancelled", "rejected", "refunded"}
        assert {t.status for t in Ticket.query.all()} == {"valid", "used", "void"}
        assert counts["events"] == 5 and counts["orders"] == 15 and counts["members"] == 10
        with pytest.raises(SystemExit):
            seed_all("NOK")
        assert Event.query.count() == 5  # the second run changed nothing
        db.drop_all()


def test_remove_takes_only_the_demo_rows_and_a_dry_run_deletes_nothing():
    from app.donations.models import Donation
    from app.members.models import Member
    from app.news.models import News
    from app.payments.models import Payment
    from scripts.seed_square import remove_all

    app = create_app("testing")
    with app.app_context():
        db.create_all()
        db.session.add(News(title="Real news", slug="real-news", summary="s", content="c", status="draft"))
        db.session.add(Member(name="Real Member", email="real@club.org"))
        db.session.commit()
        made = seed_all("NOK")
        before = (Event.query.count(), Order.query.count(), Ticket.query.count(), Payment.query.count(), Member.query.count(), Donation.query.count(), News.query.count())
        dry = remove_all(apply=False)
        assert dry["events"] == 5 and dry["orders"] == 15 and dry["tickets"] == 26 and dry["payments"] == made["payments"] and dry["members"] == 10
        assert (Event.query.count(), Order.query.count(), Ticket.query.count(), Payment.query.count(), Member.query.count(), Donation.query.count(), News.query.count()) == before  # a dry run deletes nothing
        done = remove_all(apply=True)
        assert done == dry
        assert (Event.query.count(), Order.query.count(), Ticket.query.count(), Payment.query.count(), Donation.query.count()) == (0, 0, 0, 0, 0)
        assert [m.name for m in Member.query.all()] == ["Real Member"] and [n.slug for n in News.query.all()] == ["real-news"]  # real rows stay
        assert sum(remove_all(apply=True).values()) == 0  # nothing left to remove
        seed_all("NOK")  # and the square can be seeded again
        assert Event.query.count() == 5
        db.drop_all()
