"""Yearly income targets of the general book (W17-R6): a target per income source next to what came in, and the planned net."""

from tests.test_accounting_general import _call, _money_in, _new_app
from app.accounting.models import Expense
from app.extensions import db
from datetime import date

URL = "/api/admin/accounting/general/budget"
PUT = URL + "/income"


def _row(body, source):
    return next(r for r in body["income"] if r["source"] == source)


def test_an_income_target_is_compared_with_what_came_in_and_gives_a_planned_net():
    app = _new_app()
    with app.app_context():
        _money_in()  # 2026: donations 60000, membership 30000 (the app fee is not income)
        db.session.add(Expense(event_id=None, date=date(2026, 5, 3), description="Flyers", category="printing", amount=40000))
        db.session.commit()
        assert _call(app, "put", PUT, json={"year": 2026, "source": "nope", "amount": 1}).status_code == 400
        assert _call(app, "put", PUT, json={"year": 2026, "source": "donation", "amount": -5}).status_code == 400
        assert _call(app, "put", PUT, json={"year": 1999, "source": "donation", "amount": 5}).status_code == 400
        assert _call(app, "put", PUT, json={"year": 2026, "source": "donation", "amount": 100000}).status_code == 200
        assert _call(app, "put", PUT, json={"year": 2026, "source": "donation", "amount": 150000}).status_code == 200  # changes, does not add
        assert _call(app, "put", PUT, json={"year": 2026, "source": "manual", "amount": 20000}).status_code == 200
        assert _call(app, "put", "/api/admin/accounting/general/budget", json={"year": 2026, "category": "printing", "amount": 100000}).status_code == 200
        body = _call(app, "get", URL + "?year=2026").get_json()
        assert _row(body, "donation") == {"source": "donation", "label": "Donations", "target": 150000, "received": 60000, "remaining": 90000}
        assert _row(body, "membership")["target"] == 0 and _row(body, "membership")["received"] == 30000
        assert body["income_target_total"] == 170000 and body["income_received_total"] == 90000
        assert body["planned_net"] == 70000  # 170000 target - 100000 expense budget
        assert _row(_call(app, "get", URL + "?year=2025").get_json(), "donation")["target"] == 0  # another year
        pdf = _call(app, "get", "/api/admin/accounting/general/report?date_from=2026-01-01&date_to=2026-12-31")
        assert pdf.status_code == 200 and pdf.data.startswith(b"%PDF")
        assert _call(app, "put", PUT, json={"year": 2026, "source": "donation", "amount": 0}).status_code == 200  # zero removes it
        assert _row(_call(app, "get", URL + "?year=2026").get_json(), "donation")["target"] == 0
        db.drop_all()



def test_copying_last_year_fills_only_what_the_year_has_not_set():
    app = _new_app()
    with app.app_context():
        b, c = "/api/admin/accounting/general/budget", URL + "/copy"
        assert _call(app, "post", c, json={"year": "x"}).status_code == 400
        for year, category, amount in ((2025, "printing", 100000), (2025, "venue", 50000), (2026, "printing", 70000)):
            assert _call(app, "put", b, json={"year": year, "category": category, "amount": amount}).status_code == 200
        assert _call(app, "put", PUT, json={"year": 2025, "source": "donation", "amount": 200000}).status_code == 200
        done = _call(app, "post", c, json={"year": 2026}).get_json()
        assert done == {"year": 2026, "from_year": 2025, "budgets": 1, "targets": 1}  # printing was already set in 2026
        body = _call(app, "get", URL + "?year=2026").get_json()
        assert next(r for r in body["items"] if r["category"] == "printing")["budget"] == 70000  # not overwritten
        assert next(r for r in body["items"] if r["category"] == "venue")["budget"] == 50000
        assert _row(body, "donation")["target"] == 200000
        again = _call(app, "post", c, json={"year": 2026}).get_json()
        assert again["budgets"] == 0 and again["targets"] == 0  # a second copy changes nothing
        db.drop_all()
