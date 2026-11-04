"""Tests for accounting general (6 tests), e.g. a square without events keeps a general book of expenses and income; event expenses stay out of the general book and the export has both sh; income typed in by hand joins the general book and can be changed and."""
from datetime import date, datetime, timezone
from io import BytesIO
from unittest.mock import patch

from openpyxl import load_workbook

from app import create_app
from app.accounting.models import Expense
from app.donations.models import Donation
from app.extensions import db
from app.payments.models import Payment
from tests.auth_helpers import FakeJWKClient, auth_header, make_user_and_token

NOW = datetime(2026, 5, 10, 12, 0, tzinfo=timezone.utc)


def _new_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
    return app


def _call(app, method, path, **kw):
    _, token = make_user_and_token(role="admin", email="admin@example.com")
    with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
        return getattr(app.test_client(), method)(path, headers=auth_header(token), **kw)


def _money_in():
    db.session.add(Donation(reference="DON-1", donor_name="Asha", donor_email="a@x.org", amount=50000, currency="NOK", status="paid", paid_at=NOW))
    db.session.add(Donation(reference="DON-2", donor_name="Hidden", donor_email="h@x.org", anonymous=True, amount=10000, currency="NOK", status="paid", paid_at=NOW))
    db.session.add(Donation(reference="DON-3", donor_name="Waiting", donor_email="w@x.org", amount=99900, currency="NOK", status="pending"))
    db.session.add(Payment(payment_type="membership", provider="vipps", amount=31000, surcharge_amount=1000, currency="NOK", status="paid", paid_at=NOW, payment_reference="PAY-1"))
    db.session.add(Payment(payment_type="membership", provider="cash", amount=20000, currency="NOK", status="pending", payment_reference="PAY-2"))
    db.session.commit()


def test_a_square_without_events_keeps_a_general_book_of_expenses_and_income():
    app = _new_app()
    with app.app_context():
        _money_in()
        made = _call(app, "post", "/api/admin/accounting/general/expenses", json={"date": "2026-05-02", "description": "Hall rent", "category": "venue", "amount": 25000})
        assert made.status_code == 201 and made.get_json()["event_id"] is None
        assert Expense.query.one().event_id is None
        assert _call(app, "post", "/api/admin/accounting/general/expenses", json={"description": "x"}).status_code == 400

        listed = _call(app, "get", "/api/admin/accounting/general/expenses").get_json()
        assert listed["total"] == 1 and listed["items"][0]["description"] == "Hall rent"

        summary = _call(app, "get", "/api/admin/accounting/general").get_json()
        # paid gifts 500 + 100, membership 310 minus the 10 app fee = 300; pending ones and the fee are not income
        assert summary["income"]["total"] == 90000
        assert {s["source"]: (s["count"], s["total"]) for s in summary["income"]["by_source"]} == {"donation": (2, 60000), "membership": (1, 30000)}
        assert summary["expenses"]["total"] == 25000 and summary["net"] == 65000

        income = _call(app, "get", "/api/admin/accounting/general/income").get_json()["items"]
        assert sorted(r["name"] or "" for r in income) == ["", "Anonymous", "Asha"]

        narrowed = _call(app, "get", "/api/admin/accounting/general?date_from=2026-06-01").get_json()
        assert narrowed["income"]["total"] == 0 and narrowed["expenses"]["total"] == 0
        assert _call(app, "get", "/api/admin/accounting/general?date_from=nonsense").status_code == 400

        # the ordinary routes by expense id work on it too
        expense_id = made.get_json()["id"]
        assert _call(app, "patch", f"/api/admin/accounting/expenses/{expense_id}", json={"amount": 30000}).get_json()["amount"] == 30000
        assert _call(app, "delete", f"/api/admin/accounting/expenses/{expense_id}").status_code == 204
        db.drop_all()


def test_event_expenses_stay_out_of_the_general_book_and_the_export_has_both_sheets():
    from app.events.models import Event

    app = _new_app()
    with app.app_context():
        event = Event(title="Gala", slug="gala", event_type="festival", start_datetime=NOW, published=True)
        db.session.add(event)
        db.session.commit()
        db.session.add(Expense(event_id=event.id, date=date(2026, 5, 1), description="Stage", category="venue", amount=70000))
        db.session.commit()
        _money_in()
        _call(app, "post", "/api/admin/accounting/general/expenses", json={"date": "2026-05-02", "description": "Printing", "category": "venue", "amount": 5000})
        assert _call(app, "get", "/api/admin/accounting/general").get_json()["expenses"]["total"] == 5000
        assert _call(app, "get", f"/api/admin/accounting/events/{event.id}/expenses").get_json()["total"] == 1

        book = _call(app, "get", "/api/admin/accounting/general/export")
        assert book.status_code == 200
        workbook = load_workbook(BytesIO(book.data))
        assert workbook.sheetnames == ["Income", "Expenses"]
        assert [c.value for c in workbook["Expenses"]["B"]][1:3] == ["Printing", None] or workbook["Expenses"]["B2"].value == "Printing"
        db.drop_all()


def test_income_typed_in_by_hand_joins_the_general_book_and_can_be_changed_and_deleted():
    app = _new_app()
    with app.app_context():
        bad = _call(app, "post", "/api/admin/accounting/general/manual-income", json={"description": "Grant"})
        assert bad.status_code == 400 and set(bad.get_json()["errors"]) == {"date", "amount"}
        made = _call(app, "post", "/api/admin/accounting/general/manual-income", json={"date": "2026-05-02", "description": "Hall hire", "amount": 150000, "source_name": "Choir", "notes": "May"})
        assert made.status_code == 201
        income_id = made.get_json()["id"]
        summary = _call(app, "get", "/api/admin/accounting/general").get_json()
        assert summary["income"]["total"] == 150000 and summary["income"]["by_source"][0]["source"] == "manual" and summary["net"] == 150000
        row = _call(app, "get", "/api/admin/accounting/general/income").get_json()["items"][0]
        assert row["id"] == income_id and row["name"] == "Choir" and row["amount"] == 150000
        assert _call(app, "patch", f"/api/admin/accounting/general/manual-income/{income_id}", json={"amount": 175000}).get_json()["amount"] == 175000
        sheet = load_workbook(BytesIO(_call(app, "get", "/api/admin/accounting/general/export").data))["Income"]
        assert [c.value for c in sheet[2]][:5] == ["2026-05-02", "Added by hand", "Hall hire", "Choir", 1750]
        assert _call(app, "delete", f"/api/admin/accounting/general/manual-income/{income_id}").status_code == 204
        assert _call(app, "delete", f"/api/admin/accounting/general/manual-income/{income_id}").status_code == 404
        assert _call(app, "get", "/api/admin/accounting/general").get_json()["income"]["total"] == 0
        db.drop_all()


def test_the_general_book_can_be_downloaded_as_a_pdf_for_a_year():
    app = _new_app()
    with app.app_context():
        _money_in()
        db.session.add(Expense(event_id=None, date=date(2026, 5, 3), description="Printing", category="printing", amount=40000))
        db.session.commit()
        _call(app, "post", "/api/admin/accounting/general/manual-income", json={"date": "2026-05-02", "description": "Hall hire", "amount": 150000, "source_name": "Choir"})
        response = _call(app, "get", "/api/admin/accounting/general/report?date_from=2026-01-01&date_to=2026-12-31")
        assert response.status_code == 200 and response.mimetype == "application/pdf"
        assert response.data.startswith(b"%PDF") and len(response.data) > 2000
        assert "general-accounts-report.pdf" in response.headers["Content-Disposition"]
        assert _call(app, "get", "/api/admin/accounting/general/report?date_from=nope").status_code == 400
        empty = _call(app, "get", "/api/admin/accounting/general/report?date_from=2020-01-01&date_to=2020-12-31")
        assert empty.status_code == 200 and empty.data.startswith(b"%PDF")
        db.drop_all()


def test_a_yearly_budget_per_category_is_compared_with_what_was_spent():
    app = _new_app()
    with app.app_context():
        db.session.add(Expense(event_id=None, date=date(2026, 5, 3), description="Flyers", category="printing", amount=40000))
        db.session.add(Expense(event_id=None, date=date(2025, 5, 3), description="Last year", category="printing", amount=99999))
        db.session.commit()
        url = "/api/admin/accounting/general/budget"
        assert _call(app, "get", url).status_code == 400
        assert _call(app, "put", url, json={"year": 2026, "category": "nope", "amount": 1}).status_code == 400
        assert _call(app, "put", url, json={"year": 2026, "category": "printing", "amount": -5}).status_code == 400
        assert _call(app, "put", url, json={"year": 2026, "category": "printing", "amount": 100000}).status_code == 200
        assert _call(app, "put", url, json={"year": 2026, "category": "printing", "amount": 150000}).status_code == 200  # changes, does not add
        body = _call(app, "get", url + "?year=2026").get_json()
        printing = next(r for r in body["items"] if r["category"] == "printing")
        assert printing == {"category": "printing", "label": printing["label"], "budget": 150000, "spent": 40000, "remaining": 110000}
        assert body["budget_total"] == 150000 and body["spent_total"] == 40000
        assert next(r for r in _call(app, "get", url + "?year=2025").get_json()["items"] if r["category"] == "printing")["budget"] == 0
        pdf = _call(app, "get", "/api/admin/accounting/general/report?date_from=2026-01-01&date_to=2026-12-31")
        assert pdf.status_code == 200 and pdf.data.startswith(b"%PDF")
        assert _call(app, "put", url, json={"year": 2026, "category": "printing", "amount": 0}).status_code == 200  # zero removes it
        assert next(r for r in _call(app, "get", url + "?year=2026").get_json()["items"] if r["category"] == "printing")["budget"] == 0
        db.drop_all()


def test_income_of_a_module_that_is_off_is_not_shown():
    app = _new_app()
    with app.app_context():
        _money_in()
        with patch("app.accounting.general.module_enabled", side_effect=lambda key: key != "donations"):
            summary = _call(app, "get", "/api/admin/accounting/general").get_json()
        assert [s["source"] for s in summary["income"]["by_source"]] == ["membership"]
        db.drop_all()
