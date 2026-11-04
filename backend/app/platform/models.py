"""Platform database tables: users, organizations, memberships, squares, audit_log. Square data never lives here (ADR 026)."""

from __future__ import annotations

import datetime as dt
import enum
import uuid
from typing import Any

from sqlalchemy import JSON, Boolean, Date, DateTime, Enum, ForeignKey, String, Text, UniqueConstraint, false, func, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.db import Base


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class SquareStatus(enum.StrEnum):
    PROVISIONING = "provisioning"
    READY = "ready"
    FAILED = "failed"


class MembershipRole(enum.StrEnum):
    OWNER = "owner"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)  # null for users who sign in through an auth provider (ADR 028)
    auth_user_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)  # the provider's subject (JWT "sub")
    auth_provider: Mapped[str | None] = mapped_column(String(20), nullable=True)  # "supabase" | "neon"
    name: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    memberships: Mapped[list[Membership]] = relationship(back_populates="user")


class AuthSession(Base):
    """A login of the platform's own cookie login (not provider users). Both cookies carry its id (`sid`); revoking the row ends the login at once,
    whatever the tokens' own expiry says. The refresh token also carries `jti`, which must equal `refresh_jti`; every refresh replaces it, so a
    stolen and replayed refresh token is detected and the whole session is revoked."""

    __tablename__ = "auth_sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    refresh_jti: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_used_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class StaffUser(Base):
    """A person who runs rootsquares (ADR 083). Not a customer account: own password (argon2) and a second step (TOTP), never the identity provider.
    `totp_secret` is Fernet-encrypted; `recovery_codes` is a JSON list of argon2 hashes, each used once; `totp_last_step` stops a code being replayed."""

    __tablename__ = "staff_users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    password_hash: Mapped[str] = mapped_column(String(255))
    totp_secret: Mapped[str | None] = mapped_column(Text, nullable=True)
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    totp_last_step: Mapped[int | None] = mapped_column(nullable=True)
    failed_attempts: Mapped[int] = mapped_column(default=0, server_default="0")  # wrong passwords in a row; the account locks at LOCK_AFTER
    locked_until: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    recovery_codes: Mapped[list[str]] = mapped_column(JSON, default=list)
    disabled_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StaffSession(Base):
    """A staff login (cookie `rs_admin`). It is created when the password is right and counts only once `second_step_at` is set (TOTP or a recovery
    code). Idle and absolute limits are `last_seen_at` and `expires_at`; revoking the row ends the login at once."""

    __tablename__ = "staff_sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    staff_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("staff_users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    second_step_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    second_step_failures: Mapped[int] = mapped_column(default=0, server_default="0")  # wrong codes in this login; at MAX_SECOND_STEP_FAILURES it ends
    ip_tag: Mapped[str | None] = mapped_column(String(64), nullable=True)  # a short hash of the address, never the address


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    billing_country: Mapped[str | None] = mapped_column(String(2), nullable=True)  # ISO 3166 alpha-2: where the owner is, for tax and invoices (W12-R12)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(60), nullable=True)  # the Stripe customer made at the first checkout

    memberships: Mapped[list[Membership]] = relationship(back_populates="organization")
    squares: Mapped[list[Square]] = relationship(back_populates="organization")


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("user_id", "org_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    role: Mapped[MembershipRole] = mapped_column(
        Enum(MembershipRole, name="membership_role", values_callable=lambda e: [m.value for m in e]), default=MembershipRole.OWNER
    )
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship(back_populates="memberships")
    organization: Mapped[Organization] = relationship(back_populates="memberships")


class Square(Base):
    __tablename__ = "squares"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    theme_id: Mapped[str] = mapped_column(String(60))
    theme_overrides: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON {colors, fonts} on top of the theme (W18-R18)
    currency: Mapped[str] = mapped_column(String(3), default="NOK", server_default="NOK")  # ISO 4217; chosen when the square is created (W6-R47)
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)  # public URL of the square's logo in the platform's public bucket (W6-R53)
    logo_dark_url: Mapped[str | None] = mapped_column(String(500), nullable=True)  # the logo for dark backgrounds (footer, dark mode), W6-R65
    phone_country: Mapped[str] = mapped_column(String(2), default="NO", server_default="NO")  # ISO 3166 alpha-2; the phone number rule of its forms (W6-R52)
    launch_package: Mapped[str | None] = mapped_column(String(20), nullable=True)  # roots | square | grove | event | custom; null = before packages (W10-R40)
    voucher_code: Mapped[str | None] = mapped_column(
        String(120), nullable=True
    )  # a code given at creation: lowers the first payment when the trial ends (W14-R30)
    group_type: Mapped[str | None] = mapped_column(String(20), nullable=True)  # the kind of group (starter_sets.py, W14-R10); null = before starter sets
    running_plan: Mapped[str] = mapped_column(String(20), default="live", server_default="live")  # live | keep | event
    # the custom package (W19-R20, ADR 082): launch_package 'custom' with the modules and the one amount per period a platform admin agreed with this square
    custom_modules: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON list of module keys
    custom_amount_minor: Mapped[int | None] = mapped_column(nullable=True)  # USD minor units per period, with the tax the way the listed prices are
    custom_interval: Mapped[str | None] = mapped_column(String(10), nullable=True)  # month | year
    modules: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON list of the modules that are on; null = all (before W8-R9)
    status: Mapped[SquareStatus] = mapped_column(
        Enum(SquareStatus, name="square_status", values_callable=lambda e: [m.value for m in e]),
        default=SquareStatus.PROVISIONING,
    )
    domain: Mapped[str] = mapped_column(String(255), default="")
    db_connection: Mapped[str | None] = mapped_column(Text, nullable=True)  # Fernet-encrypted connection string, never returned by the API
    neon_project_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    provider_project_ref: Mapped[str | None] = mapped_column(String(100), nullable=True)  # the square's own Supabase project (ADR 028)
    provider: Mapped[str | None] = mapped_column(String(20), nullable=True)  # which provisioner made it: local | supabase | neon
    google_login: Mapped[str | None] = mapped_column(String(20), nullable=True)  # requested | enabled (null = requested); switched on by a platform admin
    provider_secrets: Mapped[str | None] = mapped_column(Text, nullable=True)  # Fernet-encrypted JSON: project url, API keys; never returned by the API
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    suspended_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # set by a platform admin: not served publicly
    billing_interval: Mapped[str] = mapped_column(String(5), default="month", server_default="month")  # default billing period (W10-R46)
    # the owner's switch for counting the visits of the square's site (ADR 090, W23-R77): off until the owner turns it on; no number of visits is stored here
    analytics_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    # where the square's contact-form messages and payment notices go, and where replies to its customer mails go (ADR 093, W25-R9);
    # null = the square server uses the square's public contact address
    mail_contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # the square's own sending domain at Resend (ADR 091, W25-R24, Grove): what the owner typed, Resend's id and status,
    # the DNS records it asked for (JSON) and the part before the @
    mail_domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mail_domain_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    mail_domain_status: Mapped[str | None] = mapped_column(String(24), nullable=True)
    mail_domain_records: Mapped[str | None] = mapped_column(Text, nullable=True)
    mail_from_local: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # the owner asks for it and staff set it up (ADR 095, W25-R31): the request, when, a call for IT help, and the last notice sent (ready | failed)
    mail_domain_request: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mail_domain_request_local: Mapped[str | None] = mapped_column(String(64), nullable=True)
    mail_domain_requested_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    mail_domain_help_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    mail_domain_notified: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # the square's own website domain (ADR 098, W26-R4, Grove): what the owner asked for (www.theirassociation.org, pointed with a CNAME at
    # CUSTOM_DOMAIN_TARGET) and, once staff added it on Render, the active domain; `domain` (the default <slug>.<suffix>) keeps working
    site_domain_request: Mapped[str | None] = mapped_column(String(255), nullable=True)
    site_domain_requested_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    site_domain: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    site_domain_help_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # the owner asked for IT help (a one-time fee)
    sleep_state: Mapped[str] = mapped_column(String(10), default="awake", server_default="awake")  # awake | sleeping | waking | failed (W10-R44)
    asleep_since: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # when it fell asleep (W13-R48); cleared on wake
    archived_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # project deleted after 12 months asleep unpaid (W13-R48)
    sleep_contact: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON: the public contact details, copied while it sleeps for the back-soon page
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(60), nullable=True)  # the renewing Stripe subscription of the running plan (W12-R13)
    payment_failed_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )  # a renewal payment failed, not put right yet (W12-R18)
    renewal_cancelled: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())  # cancelled at Stripe: ends when the paid time ends
    pending_running_plan: Mapped[str | None] = mapped_column(String(16), nullable=True)  # a downgrade (Live to Keep) that starts at the next renewal (W18-R34)
    paid_until: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # running plan paid up to here (W10-R42); null = not yet
    # The life of an Event pass (W11, ADR 044): all null for every other square. See app/platform/event_pass.py.
    event_started_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # the day it was paid; the clock starts here
    event_live_until: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # end of the live days; the archive starts here
    event_archive_until: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )  # end of the archive; the square leaves service here
    event_deleted_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # left service (soft delete); purged a few days later
    event_export_confirmed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # the owner said the reports are saved
    event_reminders: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON list of the reminder days already recorded (40, 60, 80, 85)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    organization: Mapped[Organization] = relationship(back_populates="squares")


class PlanPrice(Base):
    """A price, as data (W10-R42): the platform admin can change it any time. Money is integer minor units plus a currency (USD only for now)."""

    __tablename__ = "plan_prices"

    key: Mapped[str] = mapped_column(String(40), primary_key=True)  # launch.roots, running.live.month, ...
    amount_minor: Mapped[int] = mapped_column()
    currency: Mapped[str] = mapped_column(String(3), default="USD", server_default="USD")
    interval: Mapped[str] = mapped_column(String(10))  # one_off | month | year
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BillingOrder(Base):
    """One payment a square owner starts: an upgrade of the launch package (the difference) or a running plan period. The provider (fake now, Stripe later)
    confirms it by webhook; only then is the plan applied (W10-R42). No card data ever reaches this database."""

    __tablename__ = "billing_orders"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    square_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("squares.id", ondelete="CASCADE"), index=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    kind: Mapped[str] = mapped_column(String(20))  # upgrade | running
    launch_package: Mapped[str | None] = mapped_column(String(20), nullable=True)  # the target package of an upgrade
    running_plan: Mapped[str | None] = mapped_column(String(20), nullable=True)  # live | keep, for a running period
    interval: Mapped[str | None] = mapped_column(String(10), nullable=True)  # month | year, for a running period
    amount_minor: Mapped[int] = mapped_column()
    currency: Mapped[str] = mapped_column(String(3), default="USD", server_default="USD")
    status: Mapped[str] = mapped_column(String(12), default="pending", server_default="pending")  # pending | paid | cancelled | failed
    provider: Mapped[str] = mapped_column(String(20))  # fake | stripe
    provider_ref: Mapped[str | None] = mapped_column(String(200), nullable=True)  # the provider's checkout or session id
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    paid_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    card_brand: Mapped[str | None] = mapped_column(String(20), nullable=True)  # visa, mastercard, ...: shown in the payment history (W12-R8)
    card_last4: Mapped[str | None] = mapped_column(String(4), nullable=True)  # the last four digits only; never the number
    # how much of this payment went back so far (W13-R31); all of it = status refunded
    refunded_minor: Mapped[int] = mapped_column(default=0, server_default="0")
    # a voucher used on this order (W14-R27): `list_minor` is the price before it, `amount_minor` stays what is charged
    list_minor: Mapped[int | None] = mapped_column(nullable=True)
    discount_minor: Mapped[int] = mapped_column(default=0, server_default="0")
    voucher_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)  # the main voucher: the partner's one when a partner code is among them
    voucher_code: Mapped[str | None] = mapped_column(String(120), nullable=True)  # every code applied, separated by a space (W15-R19)


class Partner(Base):
    """An affiliate or partner (W14-R27): has vouchers; the report shows what they brought in and the commission owed. Payouts are made by hand."""

    __tablename__ = "partners"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)  # internal, never shown to customers
    commission_percent: Mapped[int] = mapped_column(default=0, server_default="0")
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Voucher(Base):
    """A code that lowers the price of one payment (W14-R27, docs/reference/prices-and-vouchers.md). A use is a paid order that carries `voucher_id`."""

    __tablename__ = "vouchers"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    kind: Mapped[str] = mapped_column(String(10))  # percent | fixed
    value: Mapped[int] = mapped_column()  # percent 1..100, or cents
    applies_to: Mapped[str] = mapped_column(String(12), default="all", server_default="all")  # all | launch | event_pass
    packages: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)  # limit to these launch packages, or any
    valid_from: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_until: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    max_uses: Mapped[int | None] = mapped_column(nullable=True)
    once_per_org: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    new_customers_only: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    stackable: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())  # may be combined with another code (W15-R19)
    partner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("partners.id", ondelete="SET NULL"), nullable=True, index=True)
    note: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BillingOrderVoucher(Base):
    """A voucher an order used (W15-R19). Every applied voucher has a row, with the discount it gave; `billing_orders.voucher_id` stays the main one.
    Orders from before stacking have no rows: their single voucher is read from `voucher_id`."""

    __tablename__ = "billing_order_vouchers"
    __table_args__ = (UniqueConstraint("order_id", "voucher_id", name="uq_order_voucher"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("billing_orders.id", ondelete="CASCADE"), index=True)
    voucher_id: Mapped[uuid.UUID] = mapped_column(index=True)
    code: Mapped[str] = mapped_column(String(40))
    discount_minor: Mapped[int] = mapped_column(default=0, server_default="0")
    position: Mapped[int] = mapped_column(default=0, server_default="0")


class PlatformSetting(Base):
    """A platform-wide setting kept as data, set by a platform admin (W15-R19): today how vouchers combine. No setting row = the default in the code."""

    __tablename__ = "platform_settings"

    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[str] = mapped_column(String(200))
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Prospect(Base):
    """Someone who asked to speak to us about a custom package (W19-R22): name, e-mail and phone as the person typed them, a status and our notes.
    A platform admin works the list in the owner console and may delete a row (the person asked, or the contact is over)."""

    __tablename__ = "prospects"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(200), index=True)
    phone: Mapped[str] = mapped_column(String(40))
    message: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    source: Mapped[str] = mapped_column(String(40), default="pricing_custom", server_default="pricing_custom")
    status: Mapped[str] = mapped_column(String(12), default="new", server_default="new", index=True)  # new | contacted | won | closed
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OpexItem(Base):
    """One running cost of the platform itself (W16-R9, docs/plans/opex-plan.md): hosting, e-mail, tools... `cadence` says how often it is paid;
    the monthly view spreads every line over the months (app/platform/opex.py). Platform admins only; no square data."""

    __tablename__ = "opex_items"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(60), index=True)
    amount_minor: Mapped[int] = mapped_column()
    currency: Mapped[str] = mapped_column(String(3), default="USD", server_default="USD")
    cadence: Mapped[str] = mapped_column(String(10))  # monthly | quarterly | yearly | one_off
    start_on: Mapped[dt.date] = mapped_column(Date)
    end_on: Mapped[dt.date | None] = mapped_column(Date, nullable=True)  # the last month it is paid; empty = still running
    annual_increase_pct: Mapped[int] = mapped_column(default=0, server_default="0")
    vendor: Mapped[str | None] = mapped_column(String(120), nullable=True)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # a variable line (W16-R9 phase 3, e.g. the payment fee) is worked out from the money received: a share of it plus a fixed part for each paid order
    cost_type: Mapped[str] = mapped_column(String(10), default="fixed", server_default="fixed")  # fixed | variable
    variable_bp: Mapped[int] = mapped_column(default=0, server_default="0")  # share of revenue in hundredths of a percent (290 = 2.9 %)
    variable_fixed_minor: Mapped[int] = mapped_column(default=0, server_default="0")  # per paid order
    created_by: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class OpexActual(Base):
    """What a fixed cost line really cost in one month (W16-R9 phase 3); replaces the planned amount of that line in that month."""

    __tablename__ = "opex_actuals"
    __table_args__ = (UniqueConstraint("item_id", "month", name="uq_opex_actual"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("opex_items.id", ondelete="CASCADE"), index=True)
    month: Mapped[str] = mapped_column(String(7))  # YYYY-MM
    amount_minor: Mapped[int] = mapped_column()
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    actor_staff_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)  # a staff member (ADR 083), never a customer id
    org_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    entity: Mapped[str] = mapped_column(String(40), default="")
    entity_id: Mapped[str] = mapped_column(String(80), default="")
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)  # never passwords, tokens or connection strings


class SupportGrant(Base):
    """The owner's permission for rootsquares staff to look at a square for a short time (ADR 089, W23-R64): for how long, which scopes, whether staff may
    change things. Only the square's owner creates or revokes one; one is active at a time. It stores no content of the square."""

    __tablename__ = "support_grants"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    square_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("squares.id", ondelete="CASCADE"), index=True)
    granted_by: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    duration_minutes: Mapped[int] = mapped_column()  # 60 | 1440 | 10080
    scopes: Mapped[list[str]] = mapped_column(JSON, default=list)  # content | settings | health | members
    allow_changes: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    note: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ending_notice_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # the "ends soon" mail went out


class SupportRequest(Base):
    """A staff member asks the owner for access, with a note. It is only shown to the owner (and mailed); the owner answers by creating a grant."""

    __tablename__ = "support_requests"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    square_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("squares.id", ondelete="CASCADE"), index=True)
    staff_id: Mapped[uuid.UUID] = mapped_column()
    staff_name: Mapped[str] = mapped_column(String(120))
    note: Mapped[str] = mapped_column(String(300))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    answered_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    grant_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)


class SupportSession(Base):
    """One use of a grant by one staff member: opened from the admin application, ended by the staff member, by expiry or by the owner revoking."""

    __tablename__ = "support_sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    grant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("support_grants.id", ondelete="CASCADE"), index=True)
    staff_id: Mapped[uuid.UUID] = mapped_column()
    staff_name: Mapped[str] = mapped_column(String(120))
    started_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_by: Mapped[str | None] = mapped_column(String(12), nullable=True)  # staff | expired | revoked
