"""Request and response models (Pydantic v2); spectree turns them into the OpenAPI document."""

from __future__ import annotations

import datetime as dt
import re
import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.platform import modules as square_modules
from app.platform import plans as square_plans
from app.platform import starter_sets

SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,38}[a-z0-9])$")


class SignupIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=200)
    name: str = Field(default="", max_length=200)
    organization_name: str = Field(min_length=2, max_length=200)

    @field_validator("email")
    @classmethod
    def _lower(cls, v: str) -> str:
        return v.lower()


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)

    @field_validator("email")
    @classmethod
    def _lower(cls, v: str) -> str:
        return v.lower()


class PasswordResetIn(BaseModel):
    email: EmailStr


class OrganizationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    role: str
    billing_country: str | None = None


class OrganizationIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    name: str
    organizations: list[OrganizationOut]


# Must match SUPPORTED_COUNTRIES in square/backend/app/common/phone.py (the square app owns the rules; the platform only stores the choice).
SUPPORTED_PHONE_COUNTRIES = ("NO", "SE", "DK", "FI", "IS", "DE", "GB", "IE", "NL", "FR", "US", "CA", "IN", "BD")  # W6-R52
SUPPORTED_CURRENCIES = ("NOK", "SEK", "DKK", "EUR", "GBP", "USD", "ISK")  # the currencies a square can be created with (W6-R47)


class SquareIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    slug: str
    theme_id: str = Field(min_length=1, max_length=60)
    currency: str = "NOK"
    phone_country: str = "NO"
    modules: list[str] | None = None  # the optional modules chosen; null = the ones the package starts with (W8-R9, W10-R40)
    launch_package: str = square_plans.DEFAULT_PACKAGE  # roots | square | grove | event (W10-R40)
    group_type: str = starter_sets.DEFAULT_GROUP_TYPE  # the kind of group: decides what starts on when no modules are sent (W14-R10)
    billing_country: str | None = None  # where the owner is (ISO alpha-2): tax and invoices; kept on the organisation (W12-R12)
    voucher_code: str | None = (
        None  # a code for the first payment of a launch package, kept on the square (W14-R30); an Event pass sends it to its checkout instead
    )

    @field_validator("billing_country")
    @classmethod
    def _billing_country(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        v = v.upper()
        if len(v) != 2 or not v.isalpha():
            raise ValueError("billing_country must be a two-letter country code")
        return v

    @field_validator("group_type")
    @classmethod
    def _group_type(cls, v: str) -> str:
        if v not in starter_sets.KEYS:
            raise ValueError(f"group_type must be one of: {', '.join(starter_sets.KEYS)}")
        return v

    @field_validator("launch_package")
    @classmethod
    def _launch_package(cls, v: str) -> str:
        if v not in square_plans.PACKAGES:
            raise ValueError("unknown launch package")
        return v

    @field_validator("modules")
    @classmethod
    def _modules(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        bad = square_modules.unknown_keys(v)
        if bad:
            raise ValueError(f"unknown modules: {', '.join(bad)}")
        return square_modules.normalize(v)

    @field_validator("phone_country")
    @classmethod
    def _phone_country(cls, v: str) -> str:
        v = v.strip().upper()
        if v not in SUPPORTED_PHONE_COUNTRIES:
            raise ValueError(f"phone_country must be one of {', '.join(SUPPORTED_PHONE_COUNTRIES)}")
        return v

    @field_validator("currency")
    @classmethod
    def _currency(cls, v: str) -> str:
        v = v.strip().upper()
        if v not in SUPPORTED_CURRENCIES:
            raise ValueError(f"currency must be one of {', '.join(SUPPORTED_CURRENCIES)}")
        return v

    @field_validator("slug")
    @classmethod
    def _slug(cls, v: str) -> str:
        v = v.strip().lower()
        if not SLUG_RE.match(v):
            raise ValueError("slug must be 3-40 characters: lowercase letters, digits and hyphens, starting and ending with a letter or digit")
        return v


class EventPassOut(BaseModel):
    """The life of an Event pass (W11, ADR 044): what the owner sees on the portal."""

    phase: str  # live | archive | removed
    started_at: dt.datetime | None = None
    live_until: dt.datetime | None = None
    archive_until: dt.datetime | None = None
    purge_at: dt.datetime | None = None
    days_left: int = 0  # days until the next change
    export_confirmed_at: dt.datetime | None = None
    reminders_sent: list[int] = []


class SquareOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    org_id: uuid.UUID
    org_name: str = ""  # the organisation's name, so a list of squares of several organisations can be grouped (W26-R27)
    name: str
    slug: str
    theme_id: str
    theme_overrides: dict[str, Any] | None = None  # the owner's own colours and font pair on top of the theme (W18-R18)
    look_seasons: list[dict[str, Any]] = []  # the seasonal looks, for the owner (W18-R49)
    look_draft: dict[str, Any] | None = None  # the shared draft: {look, token, expires_at, expired, has_passcode}, for the owner only (W18-R47)
    currency: str = "NOK"
    phone_country: str = "NO"
    billing_country: str | None = None  # the organisation's country (ISO alpha-2), for tax and invoices (W13-R18, shown in the portal Settings W13-R43)
    tax_percent: float = 0.0  # the tax that is inside the listed prices for that country (BILLING_TAX_RATES, W13-R51); 0 = none
    modules: list[str] = []  # the optional modules that are on (W8-R9)
    launch_package: str = "grove"  # roots | square | grove | event; squares made before packages existed are grove (W10-R40)
    voucher_code: str | None = None  # the code given when the square was created; it lowers the first payment (W14-R30)
    group_type: str | None = None  # cultural | religious (starter_sets.py); null = made before starter sets
    running_plan: str = "live"  # live | keep | event
    allowed_modules: list[str] = []  # the optional modules the launch package lets the owner switch on
    core_modules: list[str] = []  # the always-on parts this square has: all of them, except in a custom package that leaves some out (W19-R24)
    custom_amount_minor: int | None = None  # a custom package (W19-R20): the one amount agreed per period (USD minor units) and its period
    custom_interval: str | None = None
    paid_until: dt.datetime | None = None  # the running plan is paid up to here (W10-R42)
    billing_interval: str = "month"  # the owner's default billing period (W10-R46)
    sleep_state: str = "awake"  # awake | sleeping | waking | failed (W10-R44): the project is paused while it sleeps
    mail_contact_email: str | None = None  # the owner's address for the square's mail and replies (ADR 093, W25-R9)
    archived_at: dt.datetime | None = None  # its project was deleted after 12 months asleep with nothing paid (W13-R48, ADR 059)
    event_pass: EventPassOut | None = None  # only for an Event pass (W11, ADR 044)
    subscription: str | None = None  # renewing | ending (cancelled, runs to paid_until) | None (W12-R13)
    pending_plan: str | None = None  # 'keep' = a downgrade that starts when the paid time ends (paid_until); null = none (W18-R34)
    payment_failed: bool = False  # the last renewal payment failed and is not put right (W12-R18)
    grace_ends: dt.datetime | None = None  # until when the site stays live after a failed payment
    can_manage_billing: bool = False  # a payment customer exists: the card and receipts page can be opened (W12-R17)
    payment_required: bool = False  # real money is on (Stripe or BILLING_ENFORCE): the first payment comes before upgrades and running periods
    first_payment_due: bool = False  # a launch package in its trial or past it, first payment not made (W12-R9)
    awaiting_payment: bool = False  # a new Event pass not yet paid: not built, no clock (W12-R6)
    logo_url: str | None = None
    logo_dark_url: str | None = None
    status: str
    domain: str
    url: str
    has_database: bool
    error: str | None = None
    created_at: dt.datetime
    google_login: str = "requested"  # requested | enabled
    auth_callback_url: str | None = None  # the OAuth redirect URI to add in Google Cloud Console for this square


class ModulesIn(BaseModel):
    modules: list[str]

    @field_validator("modules")
    @classmethod
    def _modules(cls, v: list[str]) -> list[str]:
        bad = square_modules.unknown_keys(v)
        if bad:
            raise ValueError(f"unknown modules: {', '.join(bad)}")
        return square_modules.normalize(v)


class ProspectIn(BaseModel):
    """The form of "Nothing fits you? Speak to us" (W19-R22). `consent` must be true; `website` is a hidden field only a bot fills."""

    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    phone: str = Field(min_length=6, max_length=40)
    message: str | None = Field(default=None, max_length=1000)
    consent: bool
    website: str | None = Field(default=None, max_length=200)

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str) -> str:
        digits = [c for c in v if c.isdigit()]
        if len(digits) < 6 or any(not (c.isdigit() or c in "+-() .") for c in v):
            raise ValueError("enter a phone number")
        return v

    @field_validator("consent")
    @classmethod
    def _consent(cls, v: bool) -> bool:
        if not v:
            raise ValueError("please agree that we may contact you")
        return v


class ProspectPatch(BaseModel):
    status: str | None = None
    notes: str | None = Field(default=None, max_length=4000)

    @field_validator("status")
    @classmethod
    def _status(cls, v: str | None) -> str | None:
        if v is not None and v not in ("new", "contacted", "won", "closed"):
            raise ValueError("unknown status")
        return v


class ProspectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    email: str
    phone: str
    message: str | None = None
    source: str
    status: str
    notes: str | None = None
    created_at: dt.datetime
    updated_at: dt.datetime


class ProspectList(BaseModel):
    items: list[ProspectOut]


class CustomPackageIn(BaseModel):
    """Platform admin only (W19-R20): the modules and the one amount per period agreed with one square. The amount includes tax like the listed prices."""

    modules: list[str] = Field(max_length=60)
    amount_minor: int = Field(ge=100, le=100_000_000)
    interval: str

    @field_validator("interval")
    @classmethod
    def _interval(cls, v: str) -> str:
        if v not in ("month", "year"):
            raise ValueError("choose month or year")
        return v


class CustomGuide(BaseModel):
    """Platform admin only (W19-R27): a guiding minimum per month for each of the five steps of a custom package (USD minor units, 0 = no guide). Advice for
    whoever agrees a package, not a rule: the amount is still the admin's to set."""

    steps: list[int] = Field(min_length=5, max_length=5)

    @field_validator("steps")
    @classmethod
    def _steps(cls, v: list[int]) -> list[int]:
        if any(x < 0 or x > 100_000_000 for x in v):
            raise ValueError("an amount between 0 and 1,000,000")
        return v


class PlanIn(BaseModel):
    """Platform admin only (support and testing) until billing exists: set a square's launch package and running plan."""

    launch_package: str | None = None
    running_plan: str | None = None

    @field_validator("launch_package")
    @classmethod
    def _launch_package(cls, v: str | None) -> str | None:
        if v is not None and v not in square_plans.PACKAGES:
            raise ValueError("unknown launch package")
        return v

    @field_validator("running_plan")
    @classmethod
    def _running_plan(cls, v: str | None) -> str | None:
        if v is not None and v not in square_plans.RUNNING:
            raise ValueError("unknown running plan")
        return v


class PlanChangeIn(BaseModel):
    """Move to Keep (a downgrade: from the next renewal) or to Live (an upgrade: at once; or back to normal when a downgrade was waiting), W18-R34."""

    plan: str


class RunningPlanIn(BaseModel):
    """The owner puts the square to sleep (keep) or wakes it (live), W10-R41. The event pass is not switched this way."""

    running_plan: str

    @field_validator("running_plan")
    @classmethod
    def _running_plan(cls, v: str) -> str:
        if v not in (square_plans.KEEP, square_plans.LIVE):
            raise ValueError("choose keep or live")
        return v


class PriceOut(BaseModel):
    key: str
    amount_minor: int  # integer minor units (cents)
    currency: str
    interval: str  # one_off | month | year


class PriceList(BaseModel):
    items: list[PriceOut]
    tax_rates: dict[str, float] = {}  # country -> percent of tax that is inside the listed prices (W13-R51)


class PriceIn(BaseModel):
    amount_minor: int = Field(ge=0, le=100_000_000)


class CheckoutIn(BaseModel):
    kind: str  # upgrade | running | event_upgrade | event_pass (the $25 of a new Event pass) | first (package plus first Live period, at trial end)
    launch_package: str | None = None  # for an upgrade: the target package
    running_plan: str | None = None  # for a running period: live | keep
    interval: str | None = None  # month | year
    voucher_code: str | None = None  # a code that lowers a launch package or an Event pass once (W14-R27)

    @field_validator("kind")
    @classmethod
    def _kind(cls, v: str) -> str:
        if v not in ("upgrade", "running", "event_upgrade", "event_pass", "first"):
            raise ValueError("kind must be upgrade, running, event_upgrade, event_pass or first")
        return v


class PortalOut(BaseModel):
    url: str


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    square_id: uuid.UUID
    kind: str
    launch_package: str | None = None
    running_plan: str | None = None
    interval: str | None = None
    amount_minor: int
    currency: str
    status: str  # pending | paid | cancelled | failed
    provider: str
    created_at: dt.datetime
    paid_at: dt.datetime | None = None
    card_brand: str | None = None
    card_last4: str | None = None
    refunded_minor: int = 0  # how much has gone back (a partial refund keeps the status paid; all of it makes it refunded)
    list_minor: int | None = None  # the price before a voucher (W14-R27); amount_minor is what was charged
    discount_minor: int = 0
    voucher_code: str | None = None


class OrderList(BaseModel):
    items: list[OrderOut]


class CheckoutOut(BaseModel):
    order_id: uuid.UUID
    url: str  # where the browser goes to pay


class FakeConfirmIn(BaseModel):
    outcome: str  # paid | cancelled

    @field_validator("outcome")
    @classmethod
    def _outcome(cls, v: str) -> str:
        if v not in ("paid", "cancelled"):
            raise ValueError("outcome must be paid or cancelled")
        return v


class BillingIntervalIn(BaseModel):
    interval: str  # month | year

    @field_validator("interval")
    @classmethod
    def _interval(cls, v: str) -> str:
        if v not in ("month", "year"):
            raise ValueError("choose month or year")
        return v


class MailContactIn(BaseModel):
    """The owner's e-mail contact for the square (ADR 093, W25-R9). null or empty clears it: the square then uses its public contact address."""

    email: EmailStr | None = None

    @field_validator("email", mode="before")
    @classmethod
    def _blank_is_none(cls, v: Any) -> Any:
        return None if isinstance(v, str) and not v.strip() else v


class MailDomainRequestIn(BaseModel):
    """The owner asks for an own sending domain and the name before the @ (ADR 091, 095); staff set it up."""

    domain: str = Field(min_length=3, max_length=253)
    local_part: str = Field(default="hello", min_length=1, max_length=64)


class MailDomainNameIn(BaseModel):
    local_part: str = Field(min_length=1, max_length=64)


class MailDomainInstructionsIn(BaseModel):
    to: EmailStr  # the person who looks after the owner's domain


class MailDomainApproveIn(BaseModel):
    """Staff set it up: the domain and name of the request unless staff correct them."""

    domain: str | None = Field(default=None, max_length=253)
    local_part: str | None = Field(default=None, max_length=64)


class MailDomainRejectIn(BaseModel):
    note: str = Field(default="", max_length=500)


class MailDomainRecordOut(BaseModel):
    record: str = ""  # SPF, DKIM, ...
    type: str = ""  # TXT, MX, CNAME
    name: str = ""  # relative to the domain the owner typed, as Resend gives it
    value: str = ""
    priority: int | None = None
    status: str = ""


class MailDomainOut(BaseModel):
    allowed: bool  # the square's package has the feature
    available: bool  # this server has the key that manages domains
    domain: str | None = None
    local_part: str = "hello"
    status: str | None = None  # Resend's: not_started, pending, verified, partially_verified, partially_failed, failed, temporary_failure
    verified: bool = False
    from_address: str | None = None  # what the square's mail is sent from, only while verified
    records: list[MailDomainRecordOut] = []
    state: str = "none"  # none | requested | registered (waiting for the DNS) | verified
    requested_domain: str | None = None  # what the owner asked for, until staff set it up or turn it down
    requested_local: str | None = None
    requested_at: dt.datetime | None = None
    help_requested: bool = False  # the owner asked for IT help (a small one-time support fee applies)
    auto_approve: bool = True  # a request is set up at once (MAIL_DOMAIN_AUTO_APPROVE); False = staff set it up


class SiteDomainRequestIn(BaseModel):
    """The owner asks for an own website domain (ADR 098), for example www.theirassociation.org."""

    domain: str = Field(min_length=3, max_length=253)


class SiteDomainActivateIn(BaseModel):
    """Staff added the domain on the host: the domain of the request unless staff correct it."""

    domain: str | None = Field(default=None, max_length=253)


class SiteDomainRejectIn(BaseModel):
    note: str = Field(default="", max_length=500)


class SiteDomainOut(BaseModel):
    allowed: bool  # the square's package has the feature (Grove)
    target: str  # the name the owner points a CNAME at (CUSTOM_DOMAIN_TARGET)
    state: str = "none"  # none | requested (waiting for staff) | active
    domain: str | None = None  # the active own domain
    requested_domain: str | None = None
    requested_at: dt.datetime | None = None
    default_domain: str = ""  # the square's address on rootsquares, which keeps working
    help_requested: bool = False  # the owner asked staff for IT help with the domain (a small one-time support fee applies)
    dns: str = "unchecked"  # unchecked | pointing | not_pointing | unknown (filled only by a check)
    # the domain at the host (Render), asked of the host only by the staff API:
    # off (no key, domains are added by hand) | not_added | unverified | verified | unknown
    render: str = "off"


class ThemeIn(BaseModel):
    """theme_id missing = keep the theme. overrides missing = keep the owner's own look; overrides null or {} = clear it (W18-R18)."""

    theme_id: str | None = Field(default=None, min_length=1, max_length=60)
    overrides: dict[str, Any] | None = None  # {"colors": {"bg", "ink", "acc"} | null, "fonts": "<pair id>" | null}, checked by theme_overrides.parse


class ThemeDraftIn(BaseModel):
    """Save the draft look (W18-R47). passcode missing = keep the old one, "" = remove it; renew_link = a new link (the old one stops working)."""

    look: dict[str, Any]
    theme_id: str | None = Field(default=None, min_length=1, max_length=60)  # the theme picked in the editor, shown with the draft and set on Publish
    passcode: str | None = Field(default=None, max_length=60)
    renew_link: bool = False


class ThemeSeasonsIn(BaseModel):
    """The whole list of seasonal looks (W18-R49); an empty list removes them all. Checked by theme_overrides.parse_seasons."""

    seasons: list[dict[str, Any]] = Field(default_factory=list, max_length=12)


class ModuleStatusOut(BaseModel):
    key: str
    holds_data: bool = False  # yes or no, never a number (ADR 038)
    pending: list[str] = []  # work in progress, as sentences for the owner to read before switching the module off


class ModuleStatusList(BaseModel):
    available: bool  # false = the square server could not be asked; the screen then shows nothing extra
    items: list[ModuleStatusOut]


class SquareHealthCheckOut(BaseModel):
    key: str
    group: str  # system | jobs | setup | site
    state: str  # ok | warn | fail | off
    text: str  # one plain sentence; never data or numbers (ADR 038)


class SquareHealthOut(BaseModel):
    reachable: bool
    version: str = ""
    checks: list[SquareHealthCheckOut]


class ModuleOut(BaseModel):
    key: str
    label: str
    description: str
    tier: str
    needs: list[str]
    parent: str | None = None
    starts_off: bool = False


class StarterSetOut(BaseModel):
    key: str
    label: str
    description: str
    modules: list[str]


class StarterSetList(BaseModel):
    items: list[StarterSetOut]


class CorePartOut(BaseModel):
    key: str
    label: str
    description: str
    needs: list[str]


class ModuleList(BaseModel):
    items: list[ModuleOut]
    core: list[CorePartOut] = []  # the always-on parts and what each needs, for the custom package form (W19-R24)
    module_core_needs: dict[str, list[str]] = {}  # the always-on parts each optional module needs


class OwnerSquareOut(SquareOut):
    owner_email: str | None = None
    organization_name: str
    suspended_at: dt.datetime | None = None


class OwnerTimelineItem(BaseModel):
    at: dt.datetime
    action: str


class SubsCount(BaseModel):
    key: str
    count: int
    price_minor: int


class SubsUpcoming(BaseModel):
    square_id: str
    name: str
    slug: str
    state: str  # trial | unpaid | renewing | ending | failed | asleep | paid | expired
    paid_until: dt.datetime | None = None
    next_minor: int
    package: str


class OwnerSubscriptions(BaseModel):
    """Money and plan state across squares, from the platform's own tables (W12-R20)."""

    mrr_minor: int
    paid_30d_minor: int
    paying: int
    trial: int
    failed: int
    asleep: int
    packages: list[SubsCount]
    running: list[SubsCount]
    upcoming: list[SubsUpcoming]


class OwnerOrderOut(OrderOut):
    refundable: bool = False  # a paid first payment, renewal or Event pass inside the refund days with something left to refund (W12-R19, W13-R31)
    refundable_minor: int = 0  # what is left to refund (0 when not refundable)


class RefundIn(BaseModel):
    # empty = refund it in full (with its effects); a smaller amount = a goodwill refund that changes nothing else
    amount_minor: int | None = Field(default=None, ge=1)


class OwnerSquareDetail(OwnerSquareOut):
    orders: list[OwnerOrderOut] = []
    provider: str | None = None
    provider_project_ref: str | None = None
    dashboard_url: str | None = None
    timeline: list[OwnerTimelineItem]


class OwnerSquareRef(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    status: str
    awaiting_payment: bool = False  # an unpaid Event pass (its status is provisioning but nothing is being built)


class OwnerUserOut(BaseModel):
    id: uuid.UUID
    email: str
    name: str
    sign_in: str  # password | supabase | neon
    organizations: int
    active_sessions: int
    created_at: dt.datetime


class OwnerUserList(BaseModel):
    items: list[OwnerUserOut]


class OwnerUserOrg(BaseModel):
    id: uuid.UUID
    name: str
    role: str
    squares: list[OwnerSquareRef]


class OwnerUserDetail(OwnerUserOut):
    orgs: list[OwnerUserOrg]


class LoggedOutOut(BaseModel):
    revoked: int


class OwnerOrgOut(BaseModel):
    id: uuid.UUID
    name: str
    owner_email: str | None = None
    members: int
    created_at: dt.datetime
    squares: list[OwnerSquareRef]


class OwnerOrgList(BaseModel):
    items: list[OwnerOrgOut]


class OwnerAuditItem(BaseModel):
    id: uuid.UUID
    at: dt.datetime
    action: str
    entity: str
    entity_id: str
    actor_id: uuid.UUID | None = None
    actor_email: str | None = None  # null when there is no actor or the account was deleted
    actor_kind: str | None = None  # 'user' (a customer account) or 'staff' (ADR 083); null with no actor
    request_id: str | None = None
    data: dict[str, object]


class OwnerAuditPage(BaseModel):
    items: list[OwnerAuditItem]
    next_before: str | None = None  # pass as `before` to get the next page


class HealthCheckOut(BaseModel):
    id: str
    status: str  # ok | warn | fail | off
    detail: str = ""


class OwnerHealth(BaseModel):
    environment: dict[str, str]
    checks: list[HealthCheckOut]


class SuspendIn(BaseModel):
    suspended: bool


class SquareCheckOut(BaseModel):
    ok: bool
    admins: int | None = None


class OwnerWeek(BaseModel):
    week_start: dt.date
    users: int
    squares: int


class OwnerAttention(BaseModel):
    kind: str  # failed | stuck | google_requested | mail_domain_requested | mail_domain_help | site_domain_requested | site_domain_help | support_granted
    square_id: uuid.UUID
    name: str
    slug: str
    detail: str | None = None
    since: dt.datetime


class PortalAttention(BaseModel):
    kind: str  # mail_domain_records | mail_domain_failed | support_request
    square_id: uuid.UUID
    name: str
    slug: str
    detail: str | None = None  # the domain, or the note of the staff member
    since: dt.datetime


class PortalAttentionList(BaseModel):
    items: list[PortalAttention]
    count: int


class OwnerAttentionList(BaseModel):
    items: list[OwnerAttention]
    count: int


class OwnerOverview(BaseModel):
    squares_total: int
    squares_ready: int
    squares_provisioning: int
    squares_awaiting_payment: int = 0  # unpaid Event passes: not being built, waiting for the $25 (W13-R33); not counted in squares_provisioning
    squares_failed: int
    users_total: int
    organizations_total: int
    weeks: list[OwnerWeek]
    attention: list[OwnerAttention]


class SquareList(BaseModel):
    items: list[SquareOut]


class OwnerSquareList(BaseModel):
    items: list[OwnerSquareOut]


class PublicSquareOut(BaseModel):
    """The public face of a ready square (hello-world page). No emails, keys or connection strings."""

    name: str
    slug: str
    theme_id: str
    theme_overrides: dict[str, Any] | None = None  # as in SquareOut, read by the square app (W18-R18)
    domain: str
    google_login: str
    has_auth_project: bool
    database: dict[str, object]  # {"ok": bool, "admins": int} read from the square's own database
    auth_url: str | None = None  # the square's own auth project and its publishable key (public by design), for signing in to the square
    auth_public_key: str | None = None


class SquareMeOut(BaseModel):
    """Who a token of the square's own auth project belongs to."""

    email: str
    name: str
    role: str | None  # the person's role in the square's admins table, or None for a member who is not an admin
    is_admin: bool


class AccountDeleteIn(BaseModel):
    confirm_email: EmailStr  # the person types their own address to confirm


class AccountDeleted(BaseModel):
    ok: bool = True
    provider_account_removed: bool  # false = the sign-in account at the identity provider could not be removed automatically


class SquareDeleteIn(BaseModel):
    confirm_slug: str  # the address of the square, typed to confirm
    force: bool = False  # platform admin only: delete the row even if the provider no longer knows the project


class GoogleIn(BaseModel):
    enabled: bool
    apply: bool = False  # also switch Google on or off at the square's own auth project (needs the platform's Google client and the provider token)


class Ack(BaseModel):
    ok: bool = True


# ---- vouchers and partners (W14-R27) -----------------------------------------------------------------------------


class VoucherCheckIn(BaseModel):
    code: str = Field(min_length=1, max_length=60)
    kind: str  # the same kinds as a checkout
    launch_package: str | None = None
    running_plan: str | None = None
    interval: str | None = None


class VoucherPreviewIn(BaseModel):
    code: str = Field(min_length=1, max_length=60)
    kind: str  # first (a launch package, at creation) | event_pass
    launch_package: str | None = None


class VoucherCheckOut(BaseModel):
    valid: bool
    reason: str | None = None  # voucher_unknown, voucher_expired, ... when not valid
    message: str | None = None  # a sentence for the customer when not valid
    list_minor: int = 0
    discount_minor: int = 0
    payable_minor: int = 0
    codes: list[str] = Field(default_factory=list)  # the codes used (W15-R19)
    ignored: list[dict[str, str]] = Field(default_factory=list)  # typed but not used: {code, why}


class VoucherIn(BaseModel):
    code: str
    kind: str
    value: int = Field(ge=1, le=100_000_000)
    applies_to: str = "all"
    packages: list[str] | None = None
    valid_from: dt.datetime | None = None
    valid_until: dt.datetime | None = None
    max_uses: int | None = Field(default=None, ge=1, le=1_000_000)
    once_per_org: bool = True
    new_customers_only: bool = False
    active: bool = True
    stackable: bool = False
    partner_id: uuid.UUID | None = None
    note: str | None = Field(default=None, max_length=300)


class VoucherPatch(BaseModel):
    code: str | None = None
    kind: str | None = None
    value: int | None = Field(default=None, ge=1, le=100_000_000)
    applies_to: str | None = None
    packages: list[str] | None = None
    valid_from: dt.datetime | None = None
    valid_until: dt.datetime | None = None
    max_uses: int | None = Field(default=None, ge=1, le=1_000_000)
    once_per_org: bool | None = None
    new_customers_only: bool | None = None
    active: bool | None = None
    stackable: bool | None = None
    partner_id: uuid.UUID | None = None
    note: str | None = Field(default=None, max_length=300)
    clear: list[str] = Field(default_factory=list)  # fields to empty: packages, valid_from, valid_until, max_uses, partner_id, note


class VoucherOut(BaseModel):
    id: uuid.UUID
    code: str
    kind: str
    value: int
    applies_to: str
    packages: list[str] | None = None
    valid_from: dt.datetime | None = None
    valid_until: dt.datetime | None = None
    max_uses: int | None = None
    once_per_org: bool
    new_customers_only: bool
    active: bool
    stackable: bool = False
    partner_id: uuid.UUID | None = None
    partner_name: str | None = None
    note: str | None = None
    created_at: dt.datetime
    uses: int = 0  # paid orders that used it
    discount_minor: int = 0  # the total it has given away


class VoucherList(BaseModel):
    items: list[VoucherOut]


class RedemptionOut(BaseModel):
    order_id: uuid.UUID
    paid_at: dt.datetime | None = None
    square_name: str
    organization_name: str
    kind: str
    list_minor: int
    discount_minor: int
    paid_minor: int


class RedemptionList(BaseModel):
    items: list[RedemptionOut]


class PartnerIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: str | None = Field(default=None, max_length=200)
    commission_percent: int = Field(default=0, ge=0, le=100)
    active: bool = True


class PartnerPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    email: str | None = Field(default=None, max_length=200)
    commission_percent: int | None = Field(default=None, ge=0, le=100)
    active: bool | None = None


class PartnerOut(BaseModel):
    id: uuid.UUID
    name: str
    email: str | None = None
    commission_percent: int
    active: bool
    created_at: dt.datetime
    vouchers: int = 0


class PartnerList(BaseModel):
    items: list[PartnerOut]


class PartnerReportLine(BaseModel):
    code: str
    uses: int
    revenue_minor: int  # what customers paid with this code, after refunds
    discount_minor: int
    commission_minor: int


class PartnerReport(BaseModel):
    partner: PartnerOut
    lines: list[PartnerReportLine]
    uses: int
    revenue_minor: int
    discount_minor: int
    commission_minor: int  # owed: revenue x the partner's commission percent; paid out by hand


class VoucherSettings(BaseModel):
    """How codes combine on one payment (W15-R19): best | sequential | additive, and the most codes that may be typed (1 to 5)."""

    mode: str
    max_codes: int = Field(ge=1, le=5)


class InvoiceSeller(BaseModel):
    """Who issues the invoice, kept as platform settings (W19-R16); an empty value is not shown."""

    name: str = Field(default="", max_length=200)
    org_no: str = Field(default="", max_length=200)
    address: str = Field(default="", max_length=200)
    email: str = Field(default="", max_length=200)
    prefix: str = Field(default="", max_length=10)
    footer: str = Field(default="", max_length=200)  # a sentence for the foot of every invoice, e.g. that it is valid without a signature; empty = none


class InvoiceOut(BaseModel):
    """The printable invoice of a paid order (W19-R16): the order plus everything around it. The lines are made by the page from the order."""

    number: str
    issued_at: dt.datetime
    seller: InvoiceSeller
    buyer_name: str
    square_name: str
    country: str | None = None
    tax_percent: float = 0.0  # the percent already inside the charged amount (BILLING_TAX_RATES for the billing country); 0 = no tax shown
    net_minor: int  # the charged amount without tax
    tax_minor: int
    period_start: dt.date | None = None
    period_end: dt.date | None = None
    order: OrderOut


# ---- support access (ADR 089, W23-R64) ----------------------------------------------------------------------------------------------------
class SupportGrantIn(BaseModel):
    duration_minutes: int
    scopes: list[str] = Field(min_length=1, max_length=4)
    allow_changes: bool = False
    members_confirmed: bool = False
    note: str | None = Field(default=None, max_length=300)


class SupportSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    staff_name: str
    started_at: dt.datetime
    ended_at: dt.datetime | None = None
    ended_by: str | None = None


class SupportGrantOut(BaseModel):
    id: uuid.UUID
    created_at: dt.datetime
    expires_at: dt.datetime
    duration_minutes: int
    scopes: list[str]
    allow_changes: bool
    note: str | None = None
    sessions: list[SupportSessionOut] = []


class SupportRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    staff_name: str
    note: str
    created_at: dt.datetime
    answered_at: dt.datetime | None = None


class SupportAuditOut(BaseModel):
    at: dt.datetime
    action: str  # support.grant | support.revoke | support.request | support.session_start | support.session_end | support.denied
    who: str  # the staff member's name, or the name (else the e-mail) of the person of the organisation who allowed or ended access; empty if unknown
    by_you: bool = False  # the person who is looking did it themselves
    scopes: list[str] = []
    allow_changes: bool | None = None
    ended_by: str | None = None


class SupportStateOut(BaseModel):
    """What the owner sees on the Support access page: the active grant (or none) and the requests waiting. The log is paged (SupportActivityOut)."""

    grant: SupportGrantOut | None = None
    requests: list[SupportRequestOut] = []
    can_manage: bool = False  # only the owner may grant and revoke


class SupportActivityOut(BaseModel):
    """One page of the log of every use, newest first."""

    items: list[SupportAuditOut] = []
    page: int
    per_page: int
    total: int


class SupportRequestIn(BaseModel):
    note: str = Field(min_length=3, max_length=300)


class SupportStaffStateOut(BaseModel):
    """What a staff member sees for one square: whether a grant is active and for what; never the owner's note."""

    square_id: uuid.UUID
    square_name: str
    domain: str
    active: bool
    scopes: list[str] = []
    allow_changes: bool = False
    expires_at: dt.datetime | None = None


class SupportSessionStartOut(BaseModel):
    session_id: uuid.UUID
    token: str
    token_expires_at: dt.datetime
    grant_expires_at: dt.datetime
    domain: str
    scopes: list[str]
    allow_changes: bool


class SupportOverviewRow(BaseModel):
    square_id: uuid.UUID
    square_name: str
    domain: str
    scopes: list[str] = []
    allow_changes: bool = False
    expires_at: dt.datetime | None = None
    open_sessions: int = 0


class SupportOverviewRequest(BaseModel):
    square_id: uuid.UUID
    square_name: str
    staff_name: str
    note: str
    created_at: dt.datetime
    answered_at: dt.datetime | None = None


class SupportOverviewOut(BaseModel):
    active: list[SupportOverviewRow] = []
    requests: list[SupportOverviewRequest] = []


# ---- analytics (ADR 090, W23-R77): the owner's numbers, passed on from the square and never stored here -------------------------------------
class AnalyticsSwitchIn(BaseModel):
    enabled: bool


class AnalyticsDayOut(BaseModel):
    day: str
    visits: int = 0
    views: int = 0
    visitors: int = 0


class AnalyticsTotalsOut(BaseModel):
    visits: int = 0
    views: int = 0
    visitors: int = 0  # the sum of each day's different visitors: nobody is followed from one day to the next


class AnalyticsPageOut(BaseModel):
    path: str
    views: int | None = None  # null when the figure is under 5 (`few`)
    few: bool = False


class AnalyticsSourceOut(BaseModel):
    source: str
    visits: int | None = None
    few: bool = False


class AnalyticsEventOut(BaseModel):
    slug: str
    title: str
    views: int | None = None
    views_few: bool = False
    tickets: int | None = None
    tickets_few: bool = False


class AnalyticsOut(BaseModel):
    """What the owner's Health tab shows. Only these fields are passed on from the square, whatever else its answer holds."""

    enabled: bool = False  # the owner's switch (the only thing the platform stores about analytics)
    reachable: bool = True
    resting: bool = False  # the square sleeps
    counting: bool = False  # the square server is counting (it also needs its key)
    days: int = 30
    start: str | None = None
    end: str | None = None
    daily: list[AnalyticsDayOut] = []
    totals: AnalyticsTotalsOut = AnalyticsTotalsOut()
    previous: AnalyticsTotalsOut = AnalyticsTotalsOut()
    pages: list[AnalyticsPageOut] = []
    sources: list[AnalyticsSourceOut] = []
    events: list[AnalyticsEventOut] = []
