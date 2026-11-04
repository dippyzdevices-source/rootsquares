"""Test-only starting point (rootsquares W6-R38).

A real square starts with Vipps QR OFF and no Vipps number (bca-oslo hardcoded its own number, so payments would have gone to BCA). Most of the
inherited tests are about checkout and orders and assume Vipps QR is available, so the site-settings row they create starts as a square that has
switched Vipps QR on with the number 12345. A test that sets `vipps_qr_enabled` or `vipps_number` itself is left alone.
"""

from sqlalchemy import event

from app.settings.models import SiteSettings

TEST_VIPPS_NUMBER = "12345"


@event.listens_for(SiteSettings, "before_insert")
def _square_with_vipps_qr_for_tests(mapper, connection, target):
    if target.vipps_qr_enabled is None and target.vipps_number is None:
        target.vipps_qr_enabled = True
        target.vipps_number = TEST_VIPPS_NUMBER
