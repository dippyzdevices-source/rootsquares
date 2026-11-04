"""Tests for phone rule (5 tests), e.g. norway is bca oslos rule; other countries; unknown country falls back to norway and message names the country."""
import pytest

from app.common.phone import SUPPORTED_COUNTRIES, is_valid_phone, phone_rule


@pytest.mark.parametrize(
    "phone,ok",
    [("+47 412 34 567", True), ("41234567", True), ("004741234567", True), ("4741234567", True), ("4123456", False), ("+46 70 123 45 67", False), ("", False)],
)
def test_norway_is_bca_oslos_rule(phone, ok):
    assert is_valid_phone(phone, phone_rule("NO")) is ok


@pytest.mark.parametrize(
    "country,phone,ok",
    [
        ("GB", "+44 7700 900123", True),
        ("GB", "07700 900123", True),
        ("GB", "+47 41234567", False),
        ("US", "(212) 555-0100", True),
        ("US", "+1 212 555 0100", True),
        ("US", "212 555", False),
        ("IN", "+91 98765 43210", True),
        ("BD", "01712345678", True),
        ("SE", "+46 70 123 45 67", True),
    ],
)
def test_other_countries(country, phone, ok):
    assert is_valid_phone(phone, phone_rule(country)) is ok


def test_unknown_country_falls_back_to_norway_and_message_names_the_country():
    assert phone_rule("XX").country == "NO" and phone_rule(None).country == "NO"
    assert "United Kingdom" in phone_rule("gb").message() and "+44" in phone_rule("GB").message()
    assert "NO" in SUPPORTED_COUNTRIES


def test_site_phone_rule_follows_the_tenant(monkeypatch):
    from app.common import site

    class T:
        phone_country = "GB"

    monkeypatch.setattr(site, "current_tenant", lambda: T())
    assert site.site_phone_rule().country == "GB"


def test_only_a_web_address_counts_as_a_logo():
    """rootsquares W6-R53: a platform on the in-memory fake storage has fake:// addresses, which no browser can load."""
    from app.tenancy import _web_url

    assert _web_url("https://x.supabase.co/storage/v1/object/public/public/a.png") == "https://x.supabase.co/storage/v1/object/public/public/a.png"
    assert _web_url("fake://storage/square-logos/a.png") == "" and _web_url(None) == "" and _web_url(" ") == ""
