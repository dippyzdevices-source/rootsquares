"""Money in the square's own currency, NOK by default (rootsquares W6-R47). bca-oslo printed every amount as "kr" and stored every payment as NOK."""

from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from flask import g
from sqlalchemy import create_engine, text

from app import create_app
from app.common.money import format_money
from app.common.site import site_currency
from app.tenancy import Tenant, TenantDirectory

SQUARE = Tenant(slug="s", name="S", theme_id="paper-brick", domain="s.rootsquares.com", db_url="sqlite://", auth_provider="supabase", auth_url="https://a.supabase.co", auth_public_key="pk")


@pytest.mark.parametrize(
    ("minor", "currency", "expected"),
    [(25000, "NOK", "250.00 kr"), (25000, "SEK", "250.00 kr"), (25000, "DKK", "250.00 kr"), (25000, "EUR", "€250.00"), (25000, "GBP", "£250.00"), (25000, "USD", "$250.00"), (25000, "JPY", "250.00 JPY"), (None, "NOK", "0.00 kr")],
)
def test_amounts_are_written_in_the_currency(minor, currency, expected):
    assert format_money(minor, currency) == expected


def test_whole_amounts_can_drop_the_decimals_and_group_thousands():
    assert format_money(123400, "NOK", whole_if_round=True) == "1 234 kr"
    assert format_money(123450, "NOK", whole_if_round=True) == "1234.50 kr"


def test_the_site_currency_is_the_squares_own_else_nok():
    app = create_app("testing")
    assert site_currency() == "NOK"  # outside any request
    with app.test_request_context():
        assert site_currency() == "NOK"  # single tenant, default
        g.tenant = replace(SQUARE, currency="SEK")
        assert site_currency() == "SEK"


def test_a_squares_currency_comes_from_the_platform_database_and_an_older_one_without_the_column_counts_as_nok(tmp_path):
    def platform(with_currency: bool) -> TenantDirectory:
        url = f"sqlite:///{tmp_path / ('p1.db' if with_currency else 'p2.db')}"
        engine = create_engine(url)
        extra = ", currency text" if with_currency else ""
        with engine.begin() as conn:
            conn.execute(text(f"create table squares (slug text, name text, theme_id text, domain text, status text, suspended_at text, db_connection text, provider_secrets text{extra})"))
        directory = TenantDirectory(url, "", "rootsquares.com", True)
        from tests.test_tenancy import _enc

        values = {"slug": "sq", "name": "Sq", "theme": "paper-brick", "domain": "sq.rootsquares.com", "url": _enc("sqlite://"), "sec": _enc("{}")}
        columns = "(slug, name, theme_id, domain, status, db_connection, provider_secrets" + (", currency)" if with_currency else ")")
        marks = ":slug, :name, :theme, :domain, 'ready', :url, :sec" + (", 'DKK'" if with_currency else "")
        with engine.begin() as conn:
            conn.execute(text(f"insert into squares {columns} values ({marks})"), values)
        return directory

    app = create_app("testing")
    with app.app_context():
        assert platform(True).lookup("sq.localhost").currency == "DKK"
        assert platform(False).lookup("sq.localhost").currency == "NOK"


def test_emails_write_amounts_in_the_squares_currency():
    from app.email.templates import render_order_received_email

    item = SimpleNamespace(ticket_type=SimpleNamespace(name="Adult"), quantity=1, subtotal=10000)
    order = SimpleNamespace(customer_name="Priya", order_number="X-1", items=[item], total_amount=10000)
    app = create_app("testing")
    with app.test_request_context():
        g.tenant = replace(SQUARE, currency="EUR")
        html, text_body, _ = render_order_received_email(order=order, event=None, order_url="https://x.example/o", vipps_number="54321")
    assert "€100.00" in html and "€100.00" in text_body and " kr" not in text_body


def test_vipps_app_is_offered_only_in_nok():
    from app.payments import vipps

    app = create_app("testing")
    with app.test_request_context(), patch.object(vipps, "is_enabled", return_value=True):
        from app.extensions import db
        from app.settings.models import get_site_settings

        db.create_all()
        get_site_settings().vipps_app_public = True
        db.session.commit()
        assert vipps.is_public() is True  # single tenant: NOK
        g.tenant = replace(SQUARE, currency="NOK")
        assert vipps.is_public() is True
        g.tenant = replace(SQUARE, currency="SEK")
        assert vipps.is_public() is False  # Vipps takes NOK only
