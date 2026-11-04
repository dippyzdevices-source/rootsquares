r"""What it is:   The demo data seeder for any square.
What it does: Fills one square's database with fictional test data for every scenario a tester needs; --remove takes it out again.
How to run:   From square/backend: python scripts/seed_square.py <slug> [--remove [--yes]].
Read before:  docs/setup/30-demo-data.md and square_db.py upgrade <slug>.
Read after:   docs/hand-tests/demo-data-test-guide.md.

Fill ONE square's database with test data that covers every scenario a manual tester needs (rootsquares W17-R8; not in bca-oslo).

    python scripts/seed_square.py <slug>                  e.g. python scripts/seed_square.py first-org
    python scripts/seed_square.py <slug> --remove         show what removing the demo data would delete (nothing is deleted)
    python scripts/seed_square.py <slug> --remove --yes   delete the demo data

The square is found in the platform database like `square_db.py upgrade <slug>` does it (PLATFORM_DATABASE_URL, FERNET_KEY in square/backend/.env), so
this works for any square the platform has made. The square's migrations must be up to date first (`square_db.py upgrade <slug>`).

What it makes (every name is fictional, every e-mail ends in @seed.example.com, every event slug starts with `demo-`):
  events      live (tickets on sale), draft (not public), expired (already held), free (no tickets), cancelled
  tickets     several types incl. members only, sold out, sales not open yet, a coupon
  orders      paid, pending online, waiting for approval (QR), cash, failed, cancelled, rejected, refunded, with a coupon
  check-in    used and unused tickets on the expired event, valid tickets on the live one
  members     active, pending, expired and cancelled memberships, paid and unpaid periods, a family
  also        donations (paid, pending, anonymous), expenses, news (published, draft, scheduled, archived), sponsors, testimonials, helpers on tasks

Seeding is purely additive: it never changes or deletes an existing row, except that a membership type still priced at 0 gets a sample price. It refuses to
run twice on the same square (the demo events are its marker). Nothing is sent: no e-mail, no payment, no storage. Run it only on a test square.

`--remove` deletes only what the seeder made: the `demo-` events with their ticket types, coupons, orders, tickets, payments and expenses; the members with an
`@seed.example.com` e-mail with their memberships, periods, family and payments; the donations with that e-mail; the news with a `demo-` address; and the
sponsors and testimonials with the seeded names. Without `--yes` it deletes nothing and only reports. Real rows, and the sample prices of the membership
types, stay.
"""

from __future__ import annotations

import os
import secrets
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

MARKER_SLUG = "demo-autumn-festival"
DOMAIN = "seed.example.com"

NAMES = [
    "Asha Verma", "Bjorn Hansen", "Chloe Martin", "Dev Patel", "Elin Berg", "Farid Khan", "Greta Olsen", "Hugo Larsen", "Ines Costa", "Jonas Dahl",
    "Kavya Nair", "Lars Nilsen", "Maya Singh", "Nils Eriksen", "Olivia Moe", "Pranav Rao", "Quinn Foster", "Rina Das", "Sven Aas", "Tara Menon",
    "Uma Iyer", "Viktor Lund", "Wilma Strand", "Xavier Roy", "Yasmin Ali", "Zoe Brandt",
]


def _email(name: str) -> str:
    return f"{name.lower().replace(' ', '.')}@{DOMAIN}"


def seed_all(currency: str = "NOK") -> dict[str, int]:
    """Writes the test data into the database the current app context points at; returns the number of rows made, by kind."""
    from app.accounting.models import Expense
    from app.auth.models import User
    from app.coupons.models import Coupon
    from app.donations.models import Donation
    from app.events.models import Event, EventSession, EventTaskAssignment
    from app.extensions import db
    from app.members.models import FamilyMember, Member
    from app.memberships.models import Membership, MembershipType
    from app.memberships.service import generate_periods_for_membership
    from app.news.models import News
    from app.orders.models import Order, OrderItem
    from app.common.site import order_prefix
    from app.payments.models import Payment, PaymentAllocation
    from app.sponsors.models import Sponsor
    from app.testimonials.models import Testimonial
    from app.tickets.models import Ticket, TicketType

    if Event.query.filter_by(slug=MARKER_SLUG).first() is not None:
        raise SystemExit("This square already has the demo data (the event 'Autumn Festival' exists). Nothing was changed.")

    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    admin = User.query.filter_by(role="admin").first()
    admin_id = admin.id if admin else None
    counts: dict[str, int] = {}

    def count(kind: str, n: int = 1) -> None:
        counts[kind] = counts.get(kind, 0) + n

    # ---- membership types: give a price to the ones still at 0 so periods are not free ----------------------------------------------------
    for name, price in {"individual": 300, "family": 500, "student": 150, "senior": 150}.items():
        mt = db.session.get(MembershipType, name)
        if mt is not None and mt.price == 0 and not mt.contact_for_price:
            mt.price = price
    db.session.commit()

    # ---- events -----------------------------------------------------------------------------------------------------------------------------
    def make_event(title: str, slug: str, etype: str, start: datetime, **kw) -> Event:
        e = Event(
            title=title,
            slug=slug,
            short_description=f"{title}: a fictional event for testing.",
            description=f"{title}. Made by the demo data script; change or delete it freely.",
            event_type=etype,
            start_datetime=start,
            end_datetime=start + timedelta(hours=4),
            venue="Community Hall",
            address="Main Street 1",
            created_by=admin_id,
            **kw,
        )
        db.session.add(e)
        db.session.flush()
        for i, t in enumerate(["Doors open", "Programme", "Food and mingling"]):
            db.session.add(EventSession(event_id=e.id, day_label="Day 1", time=(start + timedelta(hours=i)).time(), title=t, sort_order=i))
        count("events")
        return e

    live = make_event("Autumn Festival (live)", MARKER_SLUG, "festival", now + timedelta(days=21), status="scheduled", published=True, capacity=200, sales_close_at=now + timedelta(days=19), max_tickets_per_email=6)
    draft = make_event("Winter Concert (draft, not public)", "demo-winter-concert", "cultural", now + timedelta(days=60), status="scheduled", published=False, capacity=150)
    expired = make_event("Summer Picnic (expired, already held)", "demo-summer-picnic", "community", now - timedelta(days=45), status="completed", published=True, capacity=120)
    free = make_event("Open Community Meetup (free, no tickets)", "demo-community-meetup", "community", now + timedelta(days=7), status="scheduled", published=True)
    cancelled = make_event("Craft Workshop (cancelled)", "demo-craft-workshop", "other", now + timedelta(days=14), status="cancelled", published=True)
    db.session.commit()

    # ---- ticket types ---------------------------------------------------------------------------------------------------------------------------
    def make_type(event: Event, name: str, price: int, capacity: int | None, **kw) -> TicketType:
        t = TicketType(event_id=event.id, name=name, price=price * 100, capacity=capacity, created_by=admin_id, **kw)
        db.session.add(t)
        count("ticket_types")
        return t

    adult = make_type(live, "Adult", 200, 100, age_category="adult", sort_order=0)
    child = make_type(live, "Child", 100, 50, age_category="child", sort_order=1)
    member_only = make_type(live, "Member", 150, 40, members_only=True, age_category="adult", sort_order=2)
    sold_out = make_type(live, "Early bird (sold out)", 120, 4, age_category="adult", sort_order=3)
    not_open = make_type(live, "VIP table (sales open later)", 500, 10, sale_start=now + timedelta(days=5), sort_order=4)
    make_type(draft, "General", 250, 150)
    p_adult = make_type(expired, "Adult", 180, 80, age_category="adult")
    p_child = make_type(expired, "Child", 90, 40, age_category="child")
    make_type(cancelled, "Workshop seat", 300, 12)
    db.session.flush()

    db.session.add(Coupon(event_id=live.id, code="WELCOME20", discount_percent=20, is_active=True, max_redemptions=10, created_by=admin_id))
    db.session.add(Coupon(event_id=live.id, code="OLDCODE", discount_percent=50, is_active=False, created_by=admin_id))
    count("coupons", 2)

    # ---- orders, payments, tickets -------------------------------------------------------------------------------------------------------------
    prefix = order_prefix()
    people = iter(NAMES * 3)

    def make_order(event: Event, lines: list[tuple[TicketType, int]], *, payment_status: str, order_status: str, provider: str, days_ago: int, coupon: tuple[str, int] | None = None, ticket_status: str = "valid", checked_in: int = 0, cancel_note: str | None = None) -> Order:
        name = next(people)
        created = now - timedelta(days=days_ago)
        gross = sum(t.price * q for t, q in lines)
        discount = gross * coupon[1] // 100 if coupon else 0
        order = Order(order_number="PENDING", event_id=event.id, customer_name=name, customer_email=_email(name), customer_phone="+4740000000", total_amount=gross - discount, coupon_code=coupon[0] if coupon else None, discount_amount=discount, payment_status=payment_status, order_status=order_status, created_at=created, updated_at=created)
        if coupon:
            order.coupon_id = Coupon.query.filter_by(event_id=event.id, code=coupon[0]).first().id
        if cancel_note:
            if payment_status == "rejected":
                order.rejected_by_user_id, order.rejected_at, order.rejection_reason = admin_id, created, cancel_note
            else:
                order.cancelled_by_user_id, order.cancelled_at, order.cancellation_reason = admin_id, created, cancel_note
        db.session.add(order)
        db.session.flush()
        order.order_number = f"{prefix}-{created.year}-{order.id:06d}"
        items = []
        for t, q in lines:
            item = OrderItem(order_id=order.id, ticket_type_id=t.id, quantity=q, unit_price=t.price, subtotal=t.price * q)
            db.session.add(item)
            items.append(item)
        db.session.flush()
        pay_status = {"paid": "paid", "refunded": "refunded", "failed": "failed", "cancelled": "cancelled", "rejected": "failed"}.get(payment_status, "pending")
        payment = Payment(payment_type="event_ticket", order_id=order.id, provider=provider, amount=order.total_amount, currency=currency, status=pay_status, paid_at=created if pay_status in ("paid", "refunded") else None, created_at=created, updated_at=created)
        db.session.add(payment)
        db.session.flush()
        payment.payment_reference = f"PAY-{created.year}-{payment.id:06d}"
        count("orders")
        count("payments")
        if payment_status in ("paid", "refunded", "cancelled") and order_status in ("confirmed", "cancelled"):
            used_left = checked_in
            for item in items:
                for _ in range(item.quantity):
                    used = used_left > 0 and ticket_status == "valid"
                    used_left -= 1 if used else 0
                    db.session.add(Ticket(order_item_id=item.id, ticket_code=secrets.token_urlsafe(16), status="used" if used else ticket_status, checked_in_at=event.start_datetime + timedelta(minutes=20) if used else None, checked_in_by_user_id=admin_id if used else None, created_at=created))
                    count("tickets")
        return order

    # live event: one of every state
    make_order(live, [(adult, 2), (child, 1)], payment_status="paid", order_status="confirmed", provider="vipps_app", days_ago=6)
    make_order(live, [(adult, 1)], payment_status="paid", order_status="confirmed", provider="stripe", days_ago=5, coupon=("WELCOME20", 20))
    make_order(live, [(member_only, 2)], payment_status="paid", order_status="confirmed", provider="vipps_qr", days_ago=4)
    make_order(live, [(sold_out, 4)], payment_status="paid", order_status="confirmed", provider="vipps_app", days_ago=8)  # fills the sold-out type
    make_order(live, [(adult, 2)], payment_status="pending", order_status="pending", provider="vipps_app", days_ago=1)
    make_order(live, [(adult, 3)], payment_status="pending_verification", order_status="pending", provider="vipps_qr", days_ago=2)
    make_order(live, [(child, 2), (adult, 2)], payment_status="pending", order_status="pending", provider="cash", days_ago=2)
    make_order(live, [(adult, 1)], payment_status="failed", order_status="pending", provider="stripe", days_ago=3)
    make_order(live, [(adult, 2)], payment_status="cancelled", order_status="cancelled", provider="vipps_app", days_ago=7, ticket_status="void", cancel_note="Cancelled by an admin at the buyer's request.")
    make_order(live, [(adult, 1)], payment_status="rejected", order_status="cancelled", provider="vipps_qr", days_ago=3, cancel_note="No matching Vipps payment was found.")
    make_order(live, [(child, 1)], payment_status="refunded", order_status="cancelled", provider="stripe", days_ago=9, ticket_status="void")
    # expired event: paid orders, some tickets checked in, some never used, one cancelled
    make_order(expired, [(p_adult, 3), (p_child, 2)], payment_status="paid", order_status="confirmed", provider="vipps_app", days_ago=70, checked_in=4)
    make_order(expired, [(p_adult, 2)], payment_status="paid", order_status="confirmed", provider="stripe", days_ago=65, checked_in=2)
    make_order(expired, [(p_adult, 4)], payment_status="paid", order_status="confirmed", provider="cash", days_ago=60)  # bought, never came
    make_order(expired, [(p_child, 2)], payment_status="cancelled", order_status="cancelled", provider="vipps_app", days_ago=55, ticket_status="void", cancel_note="Buyer could not come.")
    db.session.commit()

    # ---- members, memberships, periods, payments ------------------------------------------------------------------------------------------------
    plan = [
        ("individual", "active", True), ("individual", "active", False), ("family", "active", True), ("student", "active", True), ("senior", "active", False),
        ("individual", "pending", False), ("family", "pending", False), ("individual", "expired", False), ("student", "expired", True), ("senior", "cancelled", False),
    ]
    members: list[Member] = []
    for i, (mtype, status, pay) in enumerate(plan):
        name = NAMES[i + 10]
        m = Member(name=name, email=_email(name), phone=f"+4741{i:06d}", address=f"{i + 1} Storgata")
        db.session.add(m)
        db.session.flush()
        members.append(m)
        start = date(now.year - (1 if status == "expired" else 0), 1, 15)
        ms = Membership(member_id=m.id, membership_type=mtype, status=status, start_date=start, end_date=date(start.year, 12, 31) if status in ("active", "expired") else None)
        db.session.add(ms)
        db.session.flush()
        periods = generate_periods_for_membership(ms)
        count("members")
        count("memberships")
        count("membership_periods", len(periods))
        if pay and periods and status != "pending":
            p = periods[0]
            p.status, p.paid_at = "paid", now - timedelta(days=30)
            payment = Payment(payment_type="membership", provider="vipps_app", amount=p.amount, currency=currency, status="paid", paid_at=now - timedelta(days=30), created_at=now - timedelta(days=30), updated_at=now - timedelta(days=30))
            db.session.add(payment)
            db.session.flush()
            payment.payment_reference = f"PAY-{payment.created_at.year}-{payment.id:06d}"
            db.session.add(PaymentAllocation(payment_id=payment.id, membership_period_id=p.id, amount=p.amount))
            count("payments")
    parent = members[2]  # the family membership: a partner and a child on the roster
    db.session.add(FamilyMember(member_id=parent.id, name="Mira Family", relationship_type="spouse", age=38, sort_order=0))
    db.session.add(FamilyMember(member_id=parent.id, name="Kiran Family", relationship_type="child", age=9, sort_order=1))
    count("family_members", 2)
    db.session.commit()

    # ---- helpers on tasks (Volunteering) ---------------------------------------------------------------------------------------------------------
    for member, category in ((members[0], "food"), (members[1], "decoration"), (members[3], "cultural")):
        db.session.add(EventTaskAssignment(event_id=live.id, member_id=member.id, category=category))
        count("task_assignments")

    # ---- donations -------------------------------------------------------------------------------------------------------------------------------
    donors = [("Asha Verma", 50000, "paid", False, "Keep up the good work!"), ("Anonymous friend", 100000, "paid", True, None), ("Bjorn Hansen", 25000, "pending", False, None), ("Chloe Martin", 75000, "paid", False, "For the youth programme")]
    for i, (donor, amount, status, anon, message) in enumerate(donors):
        created = now - timedelta(days=10 + i)
        d = Donation(reference="PENDING", donor_name=donor, donor_email=_email(donor.replace("Anonymous friend", "Anon Friend")), anonymous=anon, message=message, amount=amount, currency=currency, status=status, paid_at=created if status == "paid" else None, created_at=created)
        db.session.add(d)
        db.session.flush()
        d.reference = f"DON-{created.year}-{d.id:06d}"
        pay = Payment(payment_type="donation", donation_id=d.id, provider="vipps_app", amount=amount, currency=currency, status="paid" if status == "paid" else "pending", paid_at=d.paid_at, created_at=created, updated_at=created)
        db.session.add(pay)
        db.session.flush()
        pay.payment_reference = f"PAY-{created.year}-{pay.id:06d}"
        count("donations")
        count("payments")

    # ---- expenses (one event, one for the general book) ------------------------------------------------------------------------------------------
    for event, day, desc, cat, amount in ((expired.id, -44, "Hall rent", "venue", 450000), (expired.id, -44, "Catering", "food", 620000), (live.id, 0, "Decoration material", "decoration", 80000), (None, -20, "Printing flyers", "printing", 35000), (None, -10, "Website and domain", "other", 120000)):
        db.session.add(Expense(event_id=event, date=(now + timedelta(days=day)).date(), description=desc, category=cat, amount=amount, vendor="Demo Supplier", created_by=admin_id))
        count("expenses")

    # ---- news -----------------------------------------------------------------------------------------------------------------------------------
    for title, status, when in (("Autumn Festival tickets are on sale", "published", -5), ("Picnic photos and thanks", "published", -40), ("Draft: volunteer call for winter", "draft", None), ("Scheduled: winter concert announcement", "published", 10), ("Last year in review", "archived", -300)):
        published_at = now + timedelta(days=when) if when is not None else None
        db.session.add(News(title=title, slug="demo-" + title.lower().replace(":", "").replace(" ", "-"), summary=f"{title}: a fictional news item.", content=f"{title}\n\nMade by the demo data script.", status=status, published_at=published_at))
        count("news")

    # ---- sponsors and testimonials ---------------------------------------------------------------------------------------------------------------
    for i, (name, active) in enumerate((("Fjord Coffee Roasters", True), ("Nordlys Print", True), ("Old Supplier AS (hidden)", False))):
        db.session.add(Sponsor(name=name, website_url="https://example.com", display_order=i, is_active=active))
        count("sponsors")
    for i, (quote, author, status) in enumerate((("The best evening we have had all year.", "Asha V.", "approved"), ("Warm, welcoming and well run.", "Bjorn H.", "approved"), ("Waiting for the committee to read this one.", "Chloe M.", "pending"))):
        db.session.add(Testimonial(quote=quote, author_name=author, author_context="Guest", sort_order=i, is_active=True, status=status))
        count("testimonials")

    db.session.commit()
    _ = (draft, free, cancelled, not_open)  # events and types that only need to exist
    return counts


SEED_SPONSORS = ("Fjord Coffee Roasters", "Nordlys Print", "Old Supplier AS (hidden)")
SEED_TESTIMONIALS = (("The best evening we have had all year.", "Asha V."), ("Warm, welcoming and well run.", "Bjorn H."), ("Waiting for the committee to read this one.", "Chloe M."))


def remove_all(apply: bool) -> dict[str, int]:
    """Deletes the rows `seed_all` made (and only those) and returns the number per kind. With apply=False everything is rolled back: a dry run that still
    meets every database constraint, so a clean dry run means the real one will go through."""
    from app.accounting.models import Expense
    from app.checkin.models import EventVolunteer
    from app.coupons.models import Coupon
    from app.donations.models import Donation
    from app.events.models import Event, EventBanner, EventSession, EventTaskAssignment
    from app.extensions import db
    from app.members.models import FamilyMember, Member
    from app.memberships.models import Membership, MembershipPeriod, MembershipTypeChange
    from app.news.models import News
    from app.orders.models import Order, OrderItem
    from app.payments.models import Payment, PaymentAllocation
    from app.sponsors.models import Sponsor
    from app.testimonials.models import Testimonial
    from app.tickets.models import Ticket, TicketType

    counts: dict[str, int] = {}

    def gone(kind: str, query) -> None:
        counts[kind] = counts.get(kind, 0) + query.delete(synchronize_session=False)

    try:
        events = [e.id for e in Event.query.filter(Event.slug.like("demo-%")).all()]
        orders = [o.id for o in Order.query.filter(Order.event_id.in_(events)).all()] if events else []
        items = [i.id for i in OrderItem.query.filter(OrderItem.order_id.in_(orders)).all()] if orders else []
        members = [m.id for m in Member.query.filter(Member.email.like(f"%@{DOMAIN}")).all()]
        memberships = [m.id for m in Membership.query.filter(Membership.member_id.in_(members)).all()] if members else []
        periods = [p.id for p in MembershipPeriod.query.filter(MembershipPeriod.membership_id.in_(memberships)).all()] if memberships else []
        donations = [d.id for d in Donation.query.filter(Donation.donor_email.like(f"%@{DOMAIN}")).all()]

        if items:
            gone("tickets", Ticket.query.filter(Ticket.order_item_id.in_(items)))
            gone("order_items", OrderItem.query.filter(OrderItem.id.in_(items)))
        if orders:
            gone("payments", Payment.query.filter(Payment.order_id.in_(orders)))
            gone("orders", Order.query.filter(Order.id.in_(orders)))
        if periods:
            allocated = [a.payment_id for a in PaymentAllocation.query.filter(PaymentAllocation.membership_period_id.in_(periods)).all()]
            gone("payment_allocations", PaymentAllocation.query.filter(PaymentAllocation.membership_period_id.in_(periods)))
            if allocated:
                gone("payments", Payment.query.filter(Payment.id.in_(allocated)))
        if donations:
            gone("payments", Payment.query.filter(Payment.donation_id.in_(donations)))
            gone("donations", Donation.query.filter(Donation.id.in_(donations)))
        if events:
            gone("coupons", Coupon.query.filter(Coupon.event_id.in_(events)))
            gone("ticket_types", TicketType.query.filter(TicketType.event_id.in_(events)))
            gone("expenses", Expense.query.filter(Expense.event_id.in_(events)))
            gone("task_assignments", EventTaskAssignment.query.filter(EventTaskAssignment.event_id.in_(events)))
            gone("event_sessions", EventSession.query.filter(EventSession.event_id.in_(events)))
            gone("event_banners", EventBanner.query.filter(EventBanner.event_id.in_(events)))
            gone("event_volunteers", EventVolunteer.query.filter(EventVolunteer.event_id.in_(events)))
        gone("expenses", Expense.query.filter(Expense.event_id.is_(None), Expense.vendor == "Demo Supplier"))
        if events:
            gone("events", Event.query.filter(Event.id.in_(events)))
        if memberships:
            gone("membership_periods", MembershipPeriod.query.filter(MembershipPeriod.membership_id.in_(memberships)))
            gone("membership_type_changes", MembershipTypeChange.query.filter(MembershipTypeChange.membership_id.in_(memberships)))
            gone("memberships", Membership.query.filter(Membership.id.in_(memberships)))
        if members:
            gone("family_members", FamilyMember.query.filter(FamilyMember.member_id.in_(members)))
            gone("task_assignments", EventTaskAssignment.query.filter(EventTaskAssignment.member_id.in_(members)))
            gone("members", Member.query.filter(Member.id.in_(members)))
        gone("news", News.query.filter(News.slug.like("demo-%")))
        gone("sponsors", Sponsor.query.filter(Sponsor.name.in_(SEED_SPONSORS)))
        for quote, author in SEED_TESTIMONIALS:
            gone("testimonials", Testimonial.query.filter_by(quote=quote, author_name=author, author_context="Guest"))
        if apply:
            db.session.commit()
        else:
            db.session.rollback()
    except Exception:
        db.session.rollback()
        raise
    return counts


def _seed_in_this_process() -> int:
    """The child process: DATABASE_URL already holds the square's connection string, so the app is built on that database (single-square mode)."""
    from app import create_app

    app = create_app()
    if os.environ.get("SEED_MODE") == "remove":
        with app.app_context():
            apply = os.environ.get("SEED_APPLY") == "1"
            print(f"{'Removing' if apply else 'Dry run, nothing is deleted:'} the demo data of square {os.environ.get('SEED_SLUG', '')!r} ({os.environ.get('SEED_NAME', '')})")
            counts = remove_all(apply)
        print("Deleted:" if apply else "Would delete:")
        for kind, n in counts.items():
            print(f"  {kind}: {n}")
        if not apply:
            print("Add --yes to delete these rows.")
        return 0
    with app.app_context():
        print(f"Seeding square {os.environ.get('SEED_SLUG', '')!r} ({os.environ.get('SEED_NAME', '')}) ...")
        counts = seed_all(os.environ.get("SEED_CURRENCY", "NOK"))
    print("Done. Rows made:")
    for kind, n in counts.items():
        print(f"  {kind}: {n}")
    return 0


def main(argv: list[str]) -> int:
    if argv[1:2] == ["--run"]:
        return _seed_in_this_process()
    flags = {a for a in argv[2:]}
    if len(argv) < 2 or argv[1].startswith("-") or not flags <= {"--remove", "--yes"} or ("--yes" in flags and "--remove" not in flags):
        print(__doc__)
        return 2
    import subprocess

    from dotenv import load_dotenv

    load_dotenv(BACKEND / (os.environ.get("ENV_FILE", "").strip() or ".env.local"))  # W26-R51
    from app.config import get_config
    from app.tenancy import TenantDirectory

    config = get_config()
    if not config.PLATFORM_DATABASE_URL:
        print("PLATFORM_DATABASE_URL is not set in square/backend/.env")
        return 1
    directory = TenantDirectory(config.PLATFORM_DATABASE_URL, config.FERNET_KEY, config.SQUARE_DOMAIN_SUFFIX, allow_localhost=True)
    tenant = directory.lookup(f"{argv[1]}.localhost")
    if tenant is None:
        print(f"No ready square called {argv[1]!r} (or its keys cannot be decrypted).")
        return 1
    # The app reads its database setting when it is first imported, so the seeding runs in a child process whose environment already holds this
    # square's connection string (single-square mode: PLATFORM_DATABASE_URL empty). The string only travels through that environment, never printed.
    env = {**os.environ, "DATABASE_URL": tenant.db_url, "PLATFORM_DATABASE_URL": "", "SEED_SLUG": tenant.slug, "SEED_NAME": tenant.name, "SEED_CURRENCY": tenant.currency, "SEED_MODE": "remove" if "--remove" in flags else "seed", "SEED_APPLY": "1" if "--yes" in flags else "0"}
    return subprocess.run([sys.executable, str(Path(__file__).resolve()), "--run"], cwd=BACKEND, env=env).returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv))
