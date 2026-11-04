r"""What it is:   An older one-off demo data script (written for the live bca-oslo database).
What it does: Adds realistic demo rows (additive only; never deletes) for manual testing.
How to run:   From square/backend: .venv\Scripts\python.exe -m scripts.seed_demo_data (the -m form is required).
Read before:  docs/setup/30-demo-data.md (prefer seed_square.py).
Read after:   square/backend/scripts/seed_square.py for any square.

One-off script to populate the live database with realistic demo data for manual testing.

Run once from backend/: .venv/Scripts/python.exe -m scripts.seed_demo_data
(the -m form is required so the `app` package resolves — a direct path invocation fails with
ModuleNotFoundError: No module named 'app').

Purely additive — never touches or deletes existing rows (including the real admin User row
and whatever test rows already exist). Does NOT create fake Supabase-authenticated Users or
fake gallery Media (both would require real external accounts/files this script can't fake
safely) — members and order customers are seeded as standalone rows instead, matching this
project's real "Excel-imported roster, not yet linked to a login" and "guest checkout" designs.
"""

import random
import secrets
from datetime import date, datetime, timedelta, timezone

import os
from pathlib import Path

from dotenv import load_dotenv

# The settings file (W26-R51): .env.local in square/backend; ENV_FILE names another one.
load_dotenv(Path(__file__).resolve().parents[1] / (os.environ.get("ENV_FILE", "").strip() or ".env.local"))

from app import create_app  # noqa: E402
from app.auth.models import User  # noqa: E402
from app.events.models import Event, EventSession  # noqa: E402
from app.extensions import db  # noqa: E402
from app.members.models import Member  # noqa: E402
from app.memberships.models import Membership  # noqa: E402
from app.news.models import News  # noqa: E402
from app.orders.models import Order, OrderItem  # noqa: E402
from app.payments.models import Payment  # noqa: E402
from app.tickets.models import Ticket, TicketType  # noqa: E402
from app.imports.models import ImportBatch  # noqa: E402

random.seed(42)

FIRST_NAMES = [
    "Priya", "Arindam", "Ananya", "Sourav", "Debarati", "Rajarshi", "Trina", "Abhijit",
    "Sneha", "Kaustav", "Ishita", "Rohan", "Moushumi", "Subhajit", "Piyali", "Anirban",
    "Ritwik", "Nandini", "Souvik", "Payel", "Rudra", "Sohini", "Amit", "Baishakhi",
    "Debjani", "Tanmoy", "Mousumi", "Arnab", "Ritu", "Sudip", "Poulomi", "Kunal",
    "Shreya", "Indranil", "Barnali", "Sayantan", "Malabika", "Debashish", "Ruma", "Subrata",
]
LAST_NAMES = [
    "Das", "Chatterjee", "Roy", "Ghosh", "Sengupta", "Mukherjee", "Banerjee", "Bose",
    "Dutta", "Sarkar", "Chakraborty", "Basu", "Pal", "Nag", "Dey", "Chowdhury", "Sinha",
    "Mitra", "Adhikari", "Kar", "Bhattacharya", "Guha", "Halder", "Saha", "Bhowmik",
    "Biswas", "Ganguly", "Sen", "Chattopadhyay", "Majumdar", "Ray", "Dasgupta", "Bagchi",
    "Ghoshal", "Sett", "Dhar", "Choudhury", "Karmakar", "Ganguli", "Chanda",
]


def random_name(used: set[str]) -> str:
    while True:
        name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
        if name not in used:
            used.add(name)
            return name


def email_for(name: str, idx: int) -> str:
    slug = name.lower().replace(" ", ".")
    return f"{slug}{idx}@example.com"


def phone() -> str:
    return f"+47 {random.randint(40000000, 99999999)}"


def dt(y: int, m: int, d: int, h: int = 18, mi: int = 0) -> datetime:
    return datetime(y, m, d, h, mi, tzinfo=timezone.utc)


def main() -> None:
    app = create_app()
    with app.app_context():
        admin = User.query.filter_by(role="admin").first()
        if admin is None:
            print("No admin User found — cannot attribute check-ins. Aborting.")
            return

        used_names: set[str] = set()
        counts: dict[str, int] = {}

        # ---- Members + Memberships ----------------------------------------------------
        membership_types = ["individual", "family", "student", "senior", "lifetime"]
        weights = [0.4, 0.3, 0.15, 0.1, 0.05]
        members = []
        for i in range(40):
            name = random_name(used_names)
            member = Member(
                name=name,
                email=email_for(name, i),
                phone=phone(),
                address=f"{random.randint(1, 200)} Storgata, {random.choice(['Oslo', 'Bærum', 'Lørenskog', 'Asker'])}",
            )
            db.session.add(member)
            members.append(member)
        db.session.flush()
        counts["members"] = len(members)

        membership_count = 0
        for member in members:
            mtype = random.choices(membership_types, weights=weights, k=1)[0]
            roll = random.random()
            if mtype == "lifetime":
                status, end_date = "active", None
            elif roll < 0.70:
                status, end_date = "active", None
            elif roll < 0.85:
                status, end_date = "pending", None
            elif roll < 0.95:
                status = "expired"
            else:
                status = "cancelled"
            start_date = date(2026, 9, 10) - timedelta(days=random.randint(10, 900))
            if mtype != "lifetime" and status in ("active", "expired"):
                end_date = start_date + timedelta(days=365)
            elif mtype != "lifetime":
                end_date = None
            created = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
            db.session.add(
                Membership(
                    member_id=member.id,
                    membership_type=mtype,
                    status=status,
                    start_date=start_date,
                    end_date=end_date,
                    created_at=created,
                    updated_at=created,
                )
            )
            membership_count += 1
        counts["memberships"] = membership_count
        db.session.commit()

        # ---- Events + Sessions + Ticket Types -------------------------------------------
        EVENTS = [
            ("Kali Puja & Diwali Celebration 2025", "festival", dt(2025, 11, 1), "Community Hall, Grønland", True, True),
            ("Christmas & New Year Gathering 2025", "community", dt(2025, 12, 20), "BCA Cultural Center", False, True),
            ("Saraswati Puja 2026", "festival", dt(2026, 2, 1, 10, 0), "Community Hall, Grønland", True, True),
            ("International Mother Language Day 2026", "cultural", dt(2026, 2, 21, 17, 0), "Deichman Library, Oslo", False, True),
            ("Poila Boishakh 2026 (Bengali New Year)", "festival", dt(2026, 4, 14, 12, 0), "Community Hall, Grønland", True, True),
            ("Rabindra Jayanti 2026", "cultural", dt(2026, 5, 9, 18, 0), "BCA Cultural Center", False, True),
            ("Nazrul Jayanti 2026", "cultural", dt(2026, 5, 25, 18, 0), "BCA Cultural Center", False, True),
            ("BCA Oslo Summer Picnic 2026", "community", dt(2026, 6, 20, 12, 0), "Frognerparken", False, True),
            ("Annual General Meeting 2026", "other", dt(2026, 7, 12, 17, 0), "BCA Cultural Center", False, True),
            ("Mahalaya 2026", "cultural", dt(2026, 9, 6, 7, 0), "BCA Cultural Center", False, True),
            ("Durga Puja 2026", "festival", dt(2026, 10, 10, 16, 0), "Community Hall, Grønland", True, True),
            ("Kali Puja & Diwali Celebration 2026", "festival", dt(2026, 11, 9, 17, 0), "Community Hall, Grønland", True, True),
            ("Bijoya Sammilani 2026", "community", dt(2026, 11, 22, 17, 0), "BCA Cultural Center", False, True),
            ("Winter Cultural Night 2026", "festival", dt(2026, 12, 19, 18, 0), "Community Hall, Grønland", True, True),
            ("Nabanna Utsav (Harvest Festival) 2026", "cultural", dt(2026, 11, 15, 17, 0), "BCA Cultural Center", False, False),
            ("Saraswati Puja 2027", "festival", dt(2027, 1, 23, 10, 0), "Community Hall, Grønland", True, False),
        ]
        SESSION_TITLES = ["Registration & Welcome", "Cultural Programme", "Prasad / Dinner", "Community Announcements"]

        events_by_slug = {}
        for title, etype, start, venue, ticketed, published in EVENTS:
            slug = (
                title.lower()
                .replace("&", "and")
                .replace("(", "")
                .replace(")", "")
                .replace(",", "")
                .replace(" ", "-")
            )
            event = Event(
                title=title,
                slug=slug,
                short_description=f"{title} — organized by BCA Oslo for the Bengali community in Oslo.",
                description=f"Join us for {title}. A full evening of cultural performances, food, and community fellowship at {venue}.",
                event_type=etype,
                start_datetime=start,
                end_datetime=start + timedelta(hours=4),
                venue=venue,
                address="Oslo, Norway",
                capacity=200 if ticketed else None,
                status="completed" if start < dt(2026, 9, 10) else "scheduled",
                published=published,
                created_at=start - timedelta(days=60),
                updated_at=start - timedelta(days=60),
            )
            db.session.add(event)
            db.session.flush()
            for idx, session_title in enumerate(SESSION_TITLES[: random.randint(2, 4)]):
                db.session.add(
                    EventSession(
                        event_id=event.id,
                        day_label="Day 1",
                        time=(start + timedelta(hours=idx)).time(),
                        title=session_title,
                        sort_order=idx,
                    )
                )
            events_by_slug[slug] = (event, ticketed, start)
        counts["events"] = len(EVENTS)
        db.session.commit()

        # ---- Ticket types for ticketed events --------------------------------------------
        TICKET_TYPE_DEFS = [("Adult", 20000), ("Child", 10000), ("Family Pack", 60000)]
        ticket_types_by_event: dict[int, list[TicketType]] = {}
        for slug, (event, ticketed, start) in events_by_slug.items():
            if not ticketed:
                continue
            types = []
            for name, price in TICKET_TYPE_DEFS:
                tt = TicketType(
                    event_id=event.id,
                    name=name,
                    price=price,
                    capacity=100,
                    created_at=event.created_at,
                    updated_at=event.created_at,
                )
                db.session.add(tt)
                types.append(tt)
            db.session.flush()
            ticket_types_by_event[event.id] = types
        counts["ticket_types"] = sum(len(v) for v in ticket_types_by_event.values())
        db.session.commit()

        # ---- Orders + Tickets + Payments --------------------------------------------------
        order_count = 0
        ticket_count = 0
        payment_count = 0
        now = dt(2026, 9, 10, 12, 0)
        for slug, (event, ticketed, start) in events_by_slug.items():
            if not ticketed or event.id not in ticket_types_by_event:
                continue
            is_past = start < now
            num_orders = random.randint(6, 10)
            for _ in range(num_orders):
                name = random_name(used_names) if random.random() < 0.5 else f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
                order_created = start - timedelta(days=random.randint(3, 45))
                if order_created > now:
                    order_created = now - timedelta(days=random.randint(1, 5))
                order = Order(
                    order_number="PENDING",
                    event_id=event.id,
                    customer_name=name,
                    customer_email=email_for(name, order_count + 1000),
                    customer_phone=phone(),
                    total_amount=0,
                    created_at=order_created,
                    updated_at=order_created,
                )
                db.session.add(order)
                db.session.flush()
                order.order_number = f"BCA-{order.created_at.year}-{order.id:06d}"

                total = 0
                chosen_types = random.sample(ticket_types_by_event[event.id], k=random.randint(1, 2))
                for tt in chosen_types:
                    qty = random.randint(1, 3)
                    subtotal = tt.price * qty
                    total += subtotal
                    db.session.add(
                        OrderItem(
                            order_id=order.id,
                            ticket_type_id=tt.id,
                            quantity=qty,
                            unit_price=tt.price,
                            subtotal=subtotal,
                        )
                    )
                order.total_amount = total

                is_paid = random.random() < (0.85 if is_past else 0.55)
                if is_paid:
                    order.payment_status = "paid"
                    order.order_status = "confirmed"
                    db.session.add(
                        Payment(
                            order_id=order.id,
                            provider="manual",
                            amount=total,
                            status="paid",
                            created_at=order_created,
                            updated_at=order_created,
                        )
                    )
                    payment_count += 1
                    db.session.flush()
                    for item in order.items:
                        for _ in range(item.quantity):
                            checked_in = is_past and random.random() < 0.75
                            db.session.add(
                                Ticket(
                                    order_item_id=item.id,
                                    ticket_code=secrets.token_urlsafe(16),
                                    status="used" if checked_in else "valid",
                                    checked_in_at=(start + timedelta(minutes=random.randint(0, 90)))
                                    if checked_in
                                    else None,
                                    checked_in_by_user_id=admin.id if checked_in else None,
                                    created_at=order_created,
                                )
                            )
                            ticket_count += 1
                order_count += 1
        counts["orders"] = order_count
        counts["tickets"] = ticket_count
        counts["payments"] = payment_count
        db.session.commit()

        # ---- News articles -----------------------------------------------------------
        NEWS_ITEMS = [
            ("Durga Puja 2026 Dates Announced", "published", now - timedelta(days=20)),
            ("Recap: A Joyous Saraswati Puja 2026", "published", now - timedelta(days=200)),
            ("Volunteers Needed for Kali Puja 2026", "published", now - timedelta(days=5)),
            ("AGM 2026 Minutes and Next Steps", "published", now - timedelta(days=60)),
            ("New Membership Types and Pricing Announced", "published", now - timedelta(days=150)),
            ("Poila Boishakh 2026: A Community Celebration", "published", now - timedelta(days=150)),
            ("Call for Cultural Performers: Winter Cultural Night", "published", now - timedelta(days=2)),
            ("BCA Oslo Summer Picnic Recap", "published", now - timedelta(days=80)),
            ("Upcoming: Nabanna Utsav Harvest Festival", "draft", None),
            ("Draft: Saraswati Puja 2027 Planning Notes", "draft", None),
            ("Bijoya Sammilani 2026 — Save the Date", "scheduled", now + timedelta(days=10)),
            ("2025 Year in Review", "archived", now - timedelta(days=300)),
        ]
        for title, status, published_at in NEWS_ITEMS:
            slug = title.lower().replace(":", "").replace(",", "").replace(" ", "-")
            created = published_at if published_at and published_at < now else now - timedelta(days=1)
            db.session.add(
                News(
                    title=title,
                    slug=slug,
                    summary=f"{title} — read more on the BCA Oslo news page.",
                    content=f"{title}\n\nMore details about this update from BCA Oslo will be shared with the community soon.",
                    status=status,
                    published_at=published_at,
                    created_at=created,
                    updated_at=created,
                )
            )
        counts["news"] = len(NEWS_ITEMS)
        db.session.commit()

        # ---- Excel import history (metadata only, no real file) --------------------------
        db.session.add(
            ImportBatch(
                admin_user_id=admin.id,
                filename="member_roster_2026_q1.xlsx",
                total_rows=25,
                members_created=22,
                memberships_created=22,
                failed_rows=3,
                created_at=now - timedelta(days=180),
            )
        )
        db.session.add(
            ImportBatch(
                admin_user_id=admin.id,
                filename="member_roster_2026_q3.xlsx",
                total_rows=18,
                members_created=18,
                memberships_created=18,
                failed_rows=0,
                created_at=now - timedelta(days=15),
            )
        )
        counts["import_batches"] = 2
        db.session.commit()

        print("Seed complete. Rows created:")
        for key, value in counts.items():
            print(f"  {key}: {value}")
        print(
            "\nNot seeded: fake Supabase-authenticated Users (would need real accounts to log "
            "in as), and gallery Media (would need real uploaded files — fake storage keys "
            "would just show broken images). Audit log entries also weren't backfilled for this "
            "historical data — it'll fill up naturally as you use the admin UI going forward, "
            "matching how real historical data (pre-audit-logging) has no trail either."
        )


if __name__ == "__main__":
    main()
