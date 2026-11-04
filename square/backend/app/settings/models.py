from sqlalchemy import false, func

from app.extensions import db
from app.modules import module_enabled


class SiteSettings(db.Model):
    """A single-row table (always id=1) for association-wide, admin-editable settings —
    today just the public Contact page's details, which used to be hardcoded in the frontend.
    Not a generic key-value store on purpose: this project prefers explicit typed columns
    (see every other domain model), and a new setting is a one-line column + migration away.
    """

    __tablename__ = "site_settings"

    id = db.Column(db.Integer, primary_key=True)
    contact_email = db.Column(db.String(255), nullable=False, default="")
    contact_phone = db.Column(db.String(50), nullable=False, default="")
    contact_address = db.Column(db.String(300), nullable=False, default="")
    # The frontend's temporary go-live gate (see frontend/src/router/index.ts) reads this at
    # runtime via the public GET /api/settings — flipping it here takes effect for every
    # visitor immediately, with no frontend rebuild/redeploy needed (unlike a Vite env var,
    # which is baked into the built JS bundle at build time and can't change afterward).
    # The square's time zone (IANA name, rootsquares W6-R54): decides what "the event day" means (refund cut-off). bca-oslo hardcoded Europe/Oslo.
    timezone = db.Column(db.String(64), nullable=False, default="Europe/Oslo", server_default="Europe/Oslo")
    maintenance_mode = db.Column(db.Boolean, nullable=False, default=True)
    # A comma-separated list of event slugs (e.g. "mahalaya-2026,saraswati-2027") that stay
    # reachable while maintenance_mode is on, read by the same frontend gate — matches the
    # comma-separated convention Config.FRONTEND_ORIGIN already uses elsewhere in this codebase,
    # split into a list at the point of use (frontend/src/router/index.ts) rather than a second
    # table, since this is still just one admin-editable settings field. An empty string means
    # no event page is allowlisted. Originally a single slug (`maintenance_allowed_event_slug`,
    # renamed here) — that used to be a hardcoded string literal in router/index.ts, which would
    # have silently broken the gate if that event were ever re-slugged before the gate came off.
    maintenance_allowed_event_slugs = db.Column(db.String(1000), nullable=False, default="")
    # A comma-separated list of fixed page keys (see MAINTENANCE_PAGE_KEYS in
    # app/settings/admin_routes.py — "home", "events", "heritage", etc.) that also stay
    # reachable while maintenance_mode is on, alongside the event slugs above. Deliberately a
    # small closed set rather than free-text paths like maintenance_allowed_event_slugs, since
    # these are the app's own fixed top-level routes, not admin-created content — an unknown key
    # is rejected at the API layer rather than silently doing nothing. An empty string means no
    # main page is allowlisted (same "off by default" safety as maintenance_allowed_event_slugs).
    maintenance_allowed_page_paths = db.Column(db.String(500), nullable=False, default="")
    # Comma-separated page keys (same fixed set) that are switched OFF entirely while maintenance
    # mode is on — hidden from everyone, admins included (they land on the under-construction page
    # like anyone else). A page listed here wins over maintenance_allowed_page_paths. Together the
    # two columns give three states per page: hidden / admin-only (unlisted) / published (listed).
    maintenance_hidden_page_paths = db.Column(db.String(500), nullable=False, default="")
    # Public URL of the Heritage page's hero photo (object storage). Uploaded from Admin -> Content ->
    # Heritage image; null until the first upload (the page shows a placeholder).
    heritage_image_url = db.Column(db.String(500), nullable=True)
    # Site-wide typeface for description text (event/news/gallery/magazine descriptions), one of
    # DESCRIPTION_STYLES in app/settings/admin_routes.py. The frontend applies it as
    # <html data-desc-style="...">; "karla" is the original body-font look.
    description_style = db.Column(db.String(20), nullable=False, default="karla", server_default="karla")
    # Admin switch: customers may choose "Vipps App" payment (with its convenience fee) only while
    # this is on AND the VIPPS_* credentials are configured (app.payments.vipps.is_public()).
    # Off by default so rollout starts with the admin-only 1 kr test payment.
    vipps_app_public = db.Column(db.Boolean, nullable=False, default=False, server_default=false())
    # Admin switches for the manual-approval payment methods (see app/payments/methods.py). Vipps QR and Cash both start off:
    # Vipps QR is offered only while it is on AND the square has its own Vipps number (rootsquares W6-R38; bca-oslo hardcoded its own).
    vipps_qr_enabled = db.Column(db.Boolean, nullable=False, default=False, server_default=false())
    vipps_number = db.Column(db.String(20), nullable=True)
    # The picture of the square's own Vipps QR code; either it or the number makes Vipps QR usable (W16-R8).
    vipps_qr_image_url = db.Column(db.String(500), nullable=True)
    cash_enabled = db.Column(db.Boolean, nullable=False, default=False, server_default=false())
    # What a cash payer is told (shown at ticket checkout / in the order email, and when a member
    # chooses Cash for a membership). An event can override the ticket note with its own `cash_note`.
    # The square's own legal texts (rootsquares W6-R51), plain text with line breaks; empty = not published yet (the public pages say so).
    privacy_text = db.Column(db.Text, nullable=False, default="", server_default="")
    terms_text = db.Column(db.Text, nullable=False, default="", server_default="")
    # The About (Heritage) page text of the square (rootsquares W6-R58): plain text with line breaks; empty = the page says nothing has been added yet.
    about_text = db.Column(db.Text, nullable=False, default="", server_default="")
    # The square's own words on its home page, header and footer (rootsquares W6-R64): one JSON object, keys listed in HOME_CONTENT_FIELDS
    # (app/settings/admin_routes.py). bca-oslo wrote its own headline, Bengali line and numbers into the page; empty keys fall back to neutral text.
    home_content = db.Column(db.JSON, nullable=False, default=dict, server_default="{}")
    cash_ticket_note = db.Column(db.Text, nullable=False, default="", server_default="")
    cash_membership_note = db.Column(db.Text, nullable=False, default="", server_default="")
    # Donations (wave 14): suggested gifts in whole currency units, comma separated ("100,250,500"; empty = only a free amount), and the square's own words.
    # Bank transfer (wave 14): the square's own account details, each optional. Offered only while it is switched on and holder + an account number or IBAN are set.
    bank_transfer_enabled = db.Column(db.Boolean, nullable=False, default=False, server_default=false())
    bank_account_holder = db.Column(db.String(200), nullable=False, default="", server_default="")
    bank_name = db.Column(db.String(200), nullable=False, default="", server_default="")
    bank_account_number = db.Column(db.String(60), nullable=False, default="", server_default="")
    bank_iban = db.Column(db.String(60), nullable=False, default="", server_default="")
    bank_bic = db.Column(db.String(30), nullable=False, default="", server_default="")
    bank_transfer_note = db.Column(db.Text, nullable=False, default="", server_default="")
    donation_amounts = db.Column(db.String(200), nullable=False, default="", server_default="")
    donation_intro = db.Column(db.Text, nullable=False, default="", server_default="")
    donation_thanks = db.Column(db.Text, nullable=False, default="", server_default="")
    # The sentence in the footer of a News (update) and a Service message; empty = the standard wording (W15-R10). The unsubscribe link stays whatever is typed.
    message_footer_update = db.Column(db.Text, nullable=False, default="", server_default="")
    message_footer_service = db.Column(db.Text, nullable=False, default="", server_default="")
    # Payment fees per method (see app/payments/fees.py). Convenience fee = what the customer is
    # charged on top of the price. Processing fee = what the provider takes from us (an estimate:
    # percent of the amount charged + a fixed part in øre). Defaults keep today's behaviour.
    vipps_qr_convenience_percent = db.Column(db.Numeric(5, 2), nullable=False, default=0, server_default="0")
    vipps_qr_processing_percent = db.Column(db.Numeric(5, 2), nullable=False, default=0, server_default="0")
    vipps_qr_processing_fixed_ore = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    vipps_app_convenience_percent = db.Column(db.Numeric(5, 2), nullable=False, default=5, server_default="5")
    vipps_app_processing_percent = db.Column(db.Numeric(5, 2), nullable=False, default=2.99, server_default="2.99")
    vipps_app_processing_fixed_ore = db.Column(db.Integer, nullable=False, default=100, server_default="100")
    # Stripe (card): switched on by the admin, offered only while the square has connected its own Stripe account (app/payments/stripe_gateway.py).
    stripe_enabled = db.Column(db.Boolean, nullable=False, default=False, server_default=false())
    stripe_convenience_percent = db.Column(db.Numeric(5, 2), nullable=False, default=0, server_default="0")
    stripe_processing_percent = db.Column(db.Numeric(5, 2), nullable=False, default=0, server_default="0")
    stripe_processing_fixed_ore = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    cash_convenience_percent = db.Column(db.Numeric(5, 2), nullable=False, default=0, server_default="0")
    cash_processing_percent = db.Column(db.Numeric(5, 2), nullable=False, default=0, server_default="0")
    cash_processing_fixed_ore = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:
        return f"<SiteSettings id={self.id}>"


def vipps_qr_available(settings: SiteSettings) -> bool:
    """Vipps QR is offered only while the square has the Payments module (W8-R30), it is switched on AND the square has set its own Vipps number or QR picture."""
    return bool(module_enabled("payments") and settings.vipps_qr_enabled and vipps_qr_has_details(settings))


def vipps_qr_has_details(settings: SiteSettings) -> bool:
    return bool((settings.vipps_number or "").strip() or settings.vipps_qr_image_url)


def bank_transfer_available(settings: SiteSettings) -> bool:
    """Bank transfer is offered only while the square has the Payments module, it is switched on AND the square has given an account holder and an account number or IBAN."""
    return bool(
        module_enabled("payments")
        and settings.bank_transfer_enabled
        and (settings.bank_account_holder or "").strip()
        and ((settings.bank_account_number or "").strip() or (settings.bank_iban or "").strip())
    )


def get_site_settings() -> SiteSettings:
    """The only accessor — never query SiteSettings directly. Lazily creates the singleton
    row with empty defaults if it's ever missing (e.g. a fresh test database that hasn't run
    the seeding migration), so a missing row is a soft default, not a 500.
    """
    settings = db.session.get(SiteSettings, 1)
    if settings is None:
        settings = SiteSettings(id=1)
        db.session.add(settings)
        db.session.commit()
    return settings
