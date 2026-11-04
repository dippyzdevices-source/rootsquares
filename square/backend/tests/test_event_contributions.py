"""Tests for event contributions (6 tests), e.g. contributions are admin only; create list update delete a contribution; validation rejects bad input."""
from unittest.mock import patch

from app import create_app
from app.accounting.models import EventContribution
from app.extensions import db
from tests.auth_helpers import FakeJWKClient, auth_header, make_user_and_token
from tests.test_admin_accounting_routes import _add_event, _add_order

JWKS = "app.auth.jwt_verification._get_jwks_client"


def _new_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
    return app


def _headers(role="admin"):
    _, token = make_user_and_token(role=role)
    return auth_header(token)


def _payload(**kw):
    p = {"kind": "donation", "name": "Anita Roy", "amount": 50000, "date": "2026-10-01"}
    p.update(kw)
    return p


def test_contributions_are_admin_only():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        url = f"/api/admin/accounting/events/{event.id}/contributions"
        assert app.test_client().get(url).status_code == 401
        with patch(JWKS, return_value=FakeJWKClient()):
            assert app.test_client().get(url, headers=_headers("member")).status_code == 403
        db.drop_all()


def test_create_list_update_delete_a_contribution():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        url = f"/api/admin/accounting/events/{event.id}/contributions"
        headers = _headers()
        with patch(JWKS, return_value=FakeJWKClient()):
            client = app.test_client()
            created = client.post(url, json=_payload(), headers=headers)
            assert created.status_code == 201
            cid = created.get_json()["id"]
            client.post(url, json=_payload(kind="sponsorship", name="Acme AS", amount=100000), headers=headers)

            assert client.get(url, headers=headers).get_json()["total"] == 2
            only = client.get(url + "?kind=sponsorship", headers=headers).get_json()
            assert [i["name"] for i in only["items"]] == ["Acme AS"]
            assert client.get(url + "?q=anita", headers=headers).get_json()["total"] == 1

            patched = client.patch(f"/api/admin/accounting/contributions/{cid}", json={"amount": 60000}, headers=headers)
            assert patched.get_json()["amount"] == 60000
            assert client.delete(f"/api/admin/accounting/contributions/{cid}", headers=headers).status_code == 204
            assert client.get(url, headers=headers).get_json()["total"] == 1
        db.drop_all()


def test_validation_rejects_bad_input():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        url = f"/api/admin/accounting/events/{event.id}/contributions"
        with patch(JWKS, return_value=FakeJWKClient()):
            client = app.test_client()
            headers = _headers()
            assert client.post(url, json={}, headers=headers).status_code == 400
            bad = client.post(url, json=_payload(kind="gift", amount=0, email="nope", date="x"), headers=headers)
            assert set(bad.get_json()["errors"]) == {"kind", "amount", "email", "date"}
        db.drop_all()


def test_a_donor_can_be_anonymous_but_a_sponsor_must_be_named():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        url = f"/api/admin/accounting/events/{event.id}/contributions"
        with patch(JWKS, return_value=FakeJWKClient()):
            client = app.test_client()
            headers = _headers()
            anon = client.post(url, json=_payload(name=""), headers=headers)
            assert anon.status_code == 201 and anon.get_json()["name"] == "Anonymous"
            assert client.post(url, json=_payload(kind="sponsorship", name=""), headers=headers).status_code == 400
            sponsor = client.post(url, json=_payload(kind="sponsorship", name="Acme AS"), headers=headers).get_json()
            assert client.patch(f"/api/admin/accounting/contributions/{sponsor['id']}", json={"name": " "}, headers=headers).status_code == 400
        db.drop_all()


def test_paid_contributions_are_added_to_the_collection_and_shown_per_kind():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        _add_order(event, amount=1000, payment_status="paid")
        for kind, amount, status in (("donation", 500, "paid"), ("sponsorship", 2000, "paid"), ("donation", 9999, "pending")):
            db.session.add(EventContribution(event_id=event.id, kind=kind, name="X", amount=amount, date=_d(), status=status))
        db.session.commit()
        with patch(JWKS, return_value=FakeJWKClient()):
            summary = app.test_client().get(f"/api/admin/accounting/events/{event.id}", headers=_headers()).get_json()
        assert summary["donations_total"] == 500
        assert summary["sponsorships_total"] == 2000
        assert summary["collection_total"] == 1000 + 500 + 2000
        assert summary["net_total"] == summary["collection_total"] - summary["expenses_total"]
        db.drop_all()


def test_report_and_export_include_contributions():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        db.session.add(EventContribution(event_id=event.id, kind="sponsorship", name="Acme AS", amount=2000, date=_d()))
        db.session.commit()
        with patch(JWKS, return_value=FakeJWKClient()):
            client = app.test_client()
            headers = _headers()
            pdf = client.get(f"/api/admin/accounting/events/{event.id}/report", headers=headers)
            assert pdf.status_code == 200 and pdf.data.startswith(b"%PDF")
            xlsx = client.get(f"/api/admin/accounting/events/{event.id}/collections/export", headers=headers)
            assert xlsx.status_code == 200
            import io

            from openpyxl import load_workbook

            wb = load_workbook(io.BytesIO(xlsx.data))
            assert "Donations & sponsors" in wb.sheetnames
            assert any("Acme AS" in (cell or "") for row in wb["Donations & sponsors"].iter_rows(values_only=True) for cell in row if isinstance(cell, str))
        db.drop_all()


def _d():
    from datetime import date

    return date(2026, 10, 1)
