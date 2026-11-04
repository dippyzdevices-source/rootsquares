import re
import uuid
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from decimal import Decimal, InvalidOperation

from flask import Blueprint, g, jsonify, request
from werkzeug.utils import secure_filename

from app.audit.service import log_action
from app.auth.decorators import require_role
from app.extensions import db
from app.gallery.media_processing import MediaValidationError, process_upload
from app.settings.models import bank_transfer_available, get_site_settings, vipps_qr_available, vipps_qr_has_details
from app.settings.routes import _serialize_settings
from app.storage.service import get_public_storage

admin_settings_bp = Blueprint("admin_settings", __name__, url_prefix="/api/admin/settings")
admin_settings_bp.before_request(require_role("admin"))

EDITABLE_FIELDS = (
    "contact_email",
    "contact_phone",
    "contact_address",
    "maintenance_allowed_event_slugs",
    "maintenance_allowed_page_paths",
    "maintenance_hidden_page_paths",
    "donation_intro",
    "donation_thanks",
    "message_footer_update",
    "message_footer_service",
)
MESSAGE_FOOTER_MAX = 400
# The words a square can set for its home page, header and footer (W6-R64), with their longest allowed length.
HOME_CONTENT_FIELDS = {
    "eyebrow": 80,  # small line above the headline
    "script_line": 60,  # handwritten line above the headline ("since 2010")
    "headline": 120,
    "local_line": 120,  # the headline again in the community's own language
    "intro": 600,
    "intro_name": 80,  # the association's full name, shown in the script font under the intro
    "intro_suffix": 120,  # what follows that name ("of Oslo.")
    "blurb": 400,  # the short text in the dark "association" band
    "sponsors_eyebrow": 60,  # the small line above the sponsors strip on the home page (W7-R6)
    "sponsors_title": 120,  # the heading of the sponsors strip; the strip itself shows whenever the square has sponsors
    "testimonials_eyebrow": 60,  # the small line above the testimonial on the home page (W7-R7)
    "testimonials_empty_text": 300,  # what is said while there are no testimonials yet; empty = the testimonial side is hidden until there is one
    "testimonials_button": 60,  # the button to the page where visitors send their own; empty = no button
    "association_eyebrow": 60,  # the small line above the association text next to it
    "association_button": 60,  # the button to the About page; empty = no button
    "utility_text": 80,  # the small line in the top bar
    "tagline_local": 80,  # the line under the name in the header and footer
    "footer_registration": 80,  # a line in the footer such as "Org. nr. 995757664" (the label differs per country, so it is one free line)
    "footer_blurb": 300,  # a short description under the name in the footer
    "footer_copyright": 160,  # the whole copyright line; empty = "(c) year name"
}
# Social links in the footer (W6-R70): which networks a square can link, in the order shown. A link with an empty address is simply not shown.
SOCIAL_NETWORKS = ("facebook", "instagram", "youtube")
HOME_STATS_MAX = 3
# The heading block of each public page (W6-R75): a small line, a handwritten line, the title, the title in the community's own language, an
# intro. Empty = the page's own neutral text. `nav_label` (W11-R43) is the page's name in the menu, the footer and the browser tab: "Heritage" can be
# "Peek Us"; the address of the page does not change.
PAGE_HEADING_PAGES = ("events", "gallery", "news", "membership", "contact", "committee", "heritage")
PAGE_HEADING_FIELDS = {"eyebrow": 60, "script_line": 60, "title": 120, "local_line": 120, "intro": 400, "nav_label": 40}
# The band at the bottom of the gallery page (W7-R4): a small line, a title, a text and a button label, plus a choice to list which years have
# photos. Empty title = no band at all; empty button label = no button; the coverage list is off unless chosen.
GALLERY_BAND_FIELDS = {"eyebrow": 60, "title": 120, "text": 400, "button_label": 60}
# The newsletter band at the bottom of the news page, and whether the Magazines tab exists (W7-R5). Empty title = no band (and no subscribe form);
# empty consent = no consent line; magazines are off unless chosen.
NEWS_BAND_FIELDS = {"eyebrow": 60, "title": 120, "text": 300, "consent": 300}
# The extra parts of the contact page (W7-R9): a heading and up to 5 questions with answers below the form, and a line with a link under the page.
# No questions = no section; empty footnote = no line.
CONTACT_PAGE_FIELDS = {"faq_eyebrow": 60, "faq_title": 120, "footnote_text": 200, "footnote_link": 60}
CONTACT_FAQ_MAX = 5
# The sections of the About page (W7-R10): who we are (cards), what we do, a timeline, and a get-involved card; founders come from the Founders
# module. Every part is optional: no cards / no title and text / no rows / no title and text = that section is not shown.
ABOUT_PAGE_FIELDS = {
    "values_title": 120,
    "values_button": 60,
    "what_title": 120,
    "what_text": 1200,
    "what_membership_link": 60,
    "what_events_link": 60,
    "timeline_eyebrow": 60,
    "timeline_title": 120,
    "involve_badge": 40,
    "involve_title": 120,
    "involve_text": 400,
    "involve_button": 60,
}
# The two lists beside the membership types on the Membership page (W7-R11): why join, and how to join. No rows = that list is not shown.
MEMBERSHIP_PAGE_FIELDS = {"benefits_eyebrow": 60, "steps_eyebrow": 60}
MEMBERSHIP_PAGE_LISTS = {
    "benefits": (6, {"text": 300}, "text"),
    "steps": (6, {"text": 300}, "text"),
}
# Lists of rows: key -> (most rows, {field: longest}, the field a row needs to be kept)
ABOUT_PAGE_LISTS = {
    "values": (6, {"title": 80, "description": 300}, "title"),
    "timeline": (10, {"year": 12, "title": 100, "description": 400}, "title"),
}


def clean_rows(rows, most: int, fields: dict, needed: str):
    """Rows of short texts for a settings list. Returns (kept rows, error text or None); a row without its needed field is dropped."""
    if not isinstance(rows, list) or len(rows) > most:
        return [], f"must be a list of at most {most}"
    kept = []
    for row in rows:
        if not isinstance(row, dict):
            return [], "must hold objects"
        clean = {}
        for key, longest in fields.items():
            text = row.get(key, "")
            if not isinstance(text, str) or len(text.strip()) > longest:
                return [], f"{key} must be text of at most {longest} characters"
            clean[key] = text.strip()
        if clean[needed]:
            kept.append({key: text for key, text in clean.items() if text})
    return kept, None


# Choices (W6-R67): how big the logo is in the header and footer, and how the name is written there. Empty = the default (medium, as written).
HOME_CONTENT_CHOICES = {"logo_size": ("small", "medium", "large"), "name_style": ("plain", "caps")}
BOOLEAN_FIELDS = ("maintenance_mode", "vipps_app_public", "vipps_qr_enabled", "cash_enabled", "bank_transfer_enabled", "stripe_enabled")
# The square's bank details (plain text, each optional) and their longest allowed length.
BANK_FIELDS = {"bank_account_holder": 200, "bank_name": 200, "bank_account_number": 60, "bank_iban": 60, "bank_bic": 30, "bank_transfer_note": 1000}
# Per-method fee fields (app/payments/fees.py): percents 0-100 with at most 2 decimals, fixed part in øre.
FEE_PERCENT_FIELDS = tuple(
    f"{m}_{kind}_percent" for m in ("vipps_qr", "vipps_app", "cash", "stripe") for kind in ("convenience", "processing")
)
FEE_FIXED_FIELDS = tuple(f"{m}_processing_fixed_ore" for m in ("vipps_qr", "vipps_app", "cash", "stripe"))
MAX_FIXED_FEE_ORE = 100_000

# Typefaces offered for description text (Design System exploration "Description Type"):
# karla = body font (original), cormorant = Cormorant Garamond 500, source = Source Serif 4.
DESCRIPTION_STYLES = ("karla", "cormorant", "source")

# The app's own fixed top-level public routes that can be allowlisted during maintenance mode,
# independent of (and unaffected by) maintenance_allowed_event_slugs above. Keys, not raw
# paths — frontend/src/router/index.ts maps each key to its actual path (and, for events/
# gallery/news, that mapping also covers their own detail sub-routes via prefix matching, the
# same way an allowed event slug already covers that event's own /tickets sub-route).
MAINTENANCE_PAGE_KEYS = (
    "home",
    "events",
    "heritage",
    "committee",
    "gallery",
    "membership",
    "news",
    "contact",
    "testimonials",
)


def _normalize_slug_list(value: str) -> str:
    """"mahalaya-2026, , saraswati-2027,mahalaya-2026" -> "mahalaya-2026,saraswati-2027" —
    strips each entry, drops empties (a trailing comma or blank line is easy to leave in an
    admin's free-text edit), and dedupes while preserving first-seen order, so the stored value
    is always clean regardless of how it was typed.
    """
    seen: dict[str, None] = {}
    for part in value.split(","):
        slug = part.strip()
        if slug:
            seen.setdefault(slug, None)
    return ",".join(seen)


def _normalize_page_keys(value: str) -> tuple[str, str | None]:
    """Same de-duplication/trimming as _normalize_slug_list, but also rejects anything outside
    MAINTENANCE_PAGE_KEYS — unlike an event slug (free text, checked against a live table
    elsewhere), these are the app's own fixed routes, so an unrecognized key is almost certainly
    a typo and should error rather than silently do nothing.
    """
    seen: dict[str, None] = {}
    for part in value.split(","):
        key = part.strip()
        if not key:
            continue
        if key not in MAINTENANCE_PAGE_KEYS:
            return "", f"Unknown page \"{key}\". Must be one of: {', '.join(MAINTENANCE_PAGE_KEYS)}."
        seen.setdefault(key, None)
    return ",".join(seen), None


def _validate_settings_payload(data: dict) -> tuple[dict, dict]:
    errors: dict[str, str] = {}
    cleaned: dict = {}

    for field in EDITABLE_FIELDS:
        if field not in data:
            continue
        value = data[field]
        if not isinstance(value, str):
            errors[field] = "Must be a string."
        elif field == "maintenance_allowed_event_slugs":
            cleaned[field] = _normalize_slug_list(value)
        elif field in ("maintenance_allowed_page_paths", "maintenance_hidden_page_paths"):
            normalized, error = _normalize_page_keys(value)
            if error:
                errors[field] = error
            else:
                cleaned[field] = normalized
        elif field.startswith("message_footer_") and len(value.strip()) > MESSAGE_FOOTER_MAX:
            errors[field] = f"At most {MESSAGE_FOOTER_MAX} characters."
        else:
            cleaned[field] = value.strip()

    if "donation_amounts" in data:
        value = data["donation_amounts"]
        parts = [p.strip() for p in value.split(",") if p.strip()] if isinstance(value, str) else None
        if parts is None or len(parts) > 8 or not all(p.isdigit() and 0 < int(p) <= 1_000_000 for p in parts):
            errors["donation_amounts"] = "Whole amounts separated by commas, at most 8 (for example 100,250,500)."
        else:
            cleaned["donation_amounts"] = ",".join(parts)

    if "vipps_number" in data:
        value = data["vipps_number"]
        if value is None or (isinstance(value, str) and not value.strip()):
            cleaned["vipps_number"] = None  # blank clears it
        elif not isinstance(value, str) or not re.fullmatch(r"\d{3,12}", value.strip()):
            errors["vipps_number"] = "Digits only, 3 to 12 of them."
        else:
            cleaned["vipps_number"] = value.strip()

    if "timezone" in data:
        value = data["timezone"]
        try:
            if not isinstance(value, str) or not value.strip():
                raise ValueError
            ZoneInfo(value.strip())
            cleaned["timezone"] = value.strip()
        except (ValueError, ZoneInfoNotFoundError, OSError):
            errors["timezone"] = "Must be a time zone name such as Europe/Oslo."

    if "description_style" in data:
        value = data["description_style"]
        if value not in DESCRIPTION_STYLES:
            errors["description_style"] = f"Must be one of: {', '.join(DESCRIPTION_STYLES)}."
        else:
            cleaned["description_style"] = value

    for field, longest in BANK_FIELDS.items():
        if field in data:
            value = data[field]
            if not isinstance(value, str) or len(value.strip()) > longest:
                errors[field] = f"Must be text of at most {longest} characters."
            else:
                cleaned[field] = value.strip()

    for field in ("cash_ticket_note", "cash_membership_note"):
        if field in data:
            value = data[field]
            if not isinstance(value, str) or len(value) > 1000:
                errors[field] = "Must be text of at most 1000 characters."
            else:
                cleaned[field] = value.strip()

    if "home_content" in data:
        value = data["home_content"]
        if not isinstance(value, dict):
            errors["home_content"] = "Must be an object."
        else:
            content: dict = {}
            for key, longest in HOME_CONTENT_FIELDS.items():
                text = value.get(key, "")
                if not isinstance(text, str) or len(text.strip()) > longest:
                    errors["home_content"] = f"{key} must be text of at most {longest} characters."
                    break
                if text.strip():
                    content[key] = text.strip()
            for key, allowed in HOME_CONTENT_CHOICES.items():
                choice = value.get(key, "")
                if choice in ("", None):
                    continue
                if choice not in allowed:
                    errors["home_content"] = f"{key} must be one of: {', '.join(allowed)}."
                    break
                content[key] = choice
            links = value.get("social_links", [])
            if "home_content" not in errors:
                if not isinstance(links, list) or len(links) > len(SOCIAL_NETWORKS):
                    errors["home_content"] = "social_links must be a list of at most %d." % len(SOCIAL_NETWORKS)
                else:
                    cleaned_links = []
                    for item in links:
                        network = item.get("network") if isinstance(item, dict) else None
                        url = item.get("url", "") if isinstance(item, dict) else None
                        if network not in SOCIAL_NETWORKS or not isinstance(url, str) or len(url.strip()) > 300:
                            errors["home_content"] = "Each social link needs a network (%s) and an address." % ", ".join(SOCIAL_NETWORKS)
                            break
                        if url.strip() and not url.strip().lower().startswith("https://"):
                            errors["home_content"] = "Social links must start with https://."
                            break
                        if url.strip() and network not in [c["network"] for c in cleaned_links]:
                            cleaned_links.append({"network": network, "url": url.strip()})
                    if cleaned_links:
                        content["social_links"] = cleaned_links
            headings = value.get("page_headings", {})
            if "home_content" not in errors:
                if not isinstance(headings, dict) or any(page not in PAGE_HEADING_PAGES for page in headings):
                    errors["home_content"] = "page_headings: the pages are %s." % ", ".join(PAGE_HEADING_PAGES)
                else:
                    cleaned_headings = {}
                    for page, fields in headings.items():
                        if not isinstance(fields, dict):
                            errors["home_content"] = f"page_headings.{page} must be an object."
                            break
                        kept = {}
                        for key, longest in PAGE_HEADING_FIELDS.items():
                            text = fields.get(key, "")
                            if not isinstance(text, str) or len(text.strip()) > longest:
                                errors["home_content"] = f"page_headings.{page}.{key} must be text of at most {longest} characters."
                                break
                            if text.strip():
                                kept[key] = text.strip()
                        if "home_content" in errors:
                            break
                        if kept:
                            cleaned_headings[page] = kept
                    if cleaned_headings and "home_content" not in errors:
                        content["page_headings"] = cleaned_headings
            for band_key, band_fields, flag in (("gallery_band", GALLERY_BAND_FIELDS, "show_coverage"), ("news_band", NEWS_BAND_FIELDS, "show_magazines")):
                band = value.get(band_key, {})
                if "home_content" in errors:
                    break
                if not isinstance(band, dict):
                    errors["home_content"] = f"{band_key} must be an object."
                    break
                kept_band: dict = {}
                for key, longest in band_fields.items():
                    text = band.get(key, "")
                    if not isinstance(text, str) or len(text.strip()) > longest:
                        errors["home_content"] = f"{band_key}.{key} must be text of at most {longest} characters."
                        break
                    if text.strip():
                        kept_band[key] = text.strip()
                if "home_content" in errors:
                    break
                chosen = band.get(flag, False)
                if not isinstance(chosen, bool):
                    errors["home_content"] = f"{band_key}.{flag} must be true or false."
                    break
                if chosen:
                    kept_band[flag] = True
                if kept_band:
                    content[band_key] = kept_band
            contact = value.get("contact_page", {})
            if "home_content" not in errors:
                if not isinstance(contact, dict):
                    errors["home_content"] = "contact_page must be an object."
                else:
                    kept_contact: dict = {}
                    for key, longest in CONTACT_PAGE_FIELDS.items():
                        text = contact.get(key, "")
                        if not isinstance(text, str) or len(text.strip()) > longest:
                            errors["home_content"] = f"contact_page.{key} must be text of at most {longest} characters."
                            break
                        if text.strip():
                            kept_contact[key] = text.strip()
                    faq = contact.get("faq", [])
                    if "home_content" not in errors:
                        if not isinstance(faq, list) or len(faq) > CONTACT_FAQ_MAX:
                            errors["home_content"] = f"contact_page.faq must be a list of at most {CONTACT_FAQ_MAX}."
                        else:
                            kept_faq = []
                            for item in faq:
                                title = item.get("title", "") if isinstance(item, dict) else None
                                answer = item.get("content", "") if isinstance(item, dict) else None
                                if not isinstance(title, str) or not isinstance(answer, str) or len(title.strip()) > 150 or len(answer.strip()) > 600:
                                    errors["home_content"] = "Each question needs a title (at most 150 characters) and an answer (at most 600)."
                                    break
                                if title.strip() and answer.strip():
                                    kept_faq.append({"title": title.strip(), "content": answer.strip()})
                            if kept_faq:
                                kept_contact["faq"] = kept_faq
                    if kept_contact and "home_content" not in errors:
                        content["contact_page"] = kept_contact
            for page_key, page_fields, page_lists in (("about_page", ABOUT_PAGE_FIELDS, ABOUT_PAGE_LISTS), ("membership_page", MEMBERSHIP_PAGE_FIELDS, MEMBERSHIP_PAGE_LISTS)):
                block = value.get(page_key, {})
                if "home_content" in errors:
                    break
                if not isinstance(block, dict):
                    errors["home_content"] = f"{page_key} must be an object."
                    break
                kept_block: dict = {}
                for key, longest in page_fields.items():
                    text = block.get(key, "")
                    if not isinstance(text, str) or len(text.strip()) > longest:
                        errors["home_content"] = f"{page_key}.{key} must be text of at most {longest} characters."
                        break
                    if text.strip():
                        kept_block[key] = text.strip()
                for key, (most, row_fields, needed) in page_lists.items():
                    if "home_content" in errors:
                        break
                    rows, problem = clean_rows(block.get(key, []), most, row_fields, needed)
                    if problem:
                        errors["home_content"] = f"{page_key}.{key} {problem}."
                    elif rows:
                        kept_block[key] = rows
                if kept_block and "home_content" not in errors:
                    content[page_key] = kept_block
            stats = value.get("stats", [])
            if "home_content" not in errors:
                if not isinstance(stats, list) or len(stats) > HOME_STATS_MAX:
                    errors["home_content"] = f"stats must be a list of at most {HOME_STATS_MAX}."
                else:
                    cleaned_stats = []
                    for item in stats:
                        number = item.get("value", "") if isinstance(item, dict) else None
                        label = item.get("label", "") if isinstance(item, dict) else None
                        if not isinstance(number, str) or not isinstance(label, str) or len(number.strip()) > 12 or len(label.strip()) > 40:
                            errors["home_content"] = "Each statistic needs a value (at most 12 characters) and a label (at most 40)."
                            break
                        if number.strip() and label.strip():
                            cleaned_stats.append({"value": number.strip(), "label": label.strip()})
                    if cleaned_stats:
                        content["stats"] = cleaned_stats
            if "home_content" not in errors:
                cleaned["home_content"] = content

    for field in ("privacy_text", "terms_text", "about_text"):
        if field in data:
            value = data[field]
            if not isinstance(value, str) or len(value) > 30000:
                errors[field] = "Must be text of at most 30000 characters."
            else:
                cleaned[field] = value.strip()
    for field in FEE_PERCENT_FIELDS:
        if field not in data:
            continue
        value = data[field]
        try:
            number = Decimal(str(value)) if isinstance(value, (int, float, str)) and not isinstance(value, bool) else None
        except InvalidOperation:
            number = None
        if number is None or not number.is_finite() or not (0 <= number <= 100) or number != number.quantize(Decimal("0.01")):
            errors[field] = "Must be a percentage from 0 to 100 with at most 2 decimals."
        else:
            cleaned[field] = number.quantize(Decimal("0.01"))

    for field in FEE_FIXED_FIELDS:
        if field not in data:
            continue
        value = data[field]
        if isinstance(value, bool) or not isinstance(value, int) or not (0 <= value <= MAX_FIXED_FEE_ORE):
            errors[field] = f"Must be a whole number of øre from 0 to {MAX_FIXED_FEE_ORE}."
        else:
            cleaned[field] = value

    for field in BOOLEAN_FIELDS:
        if field not in data:
            continue
        value = data[field]
        if not isinstance(value, bool):
            errors[field] = "Must be a boolean."
        else:
            cleaned[field] = value

    return cleaned, errors


def _serialize_admin_settings(settings) -> dict:
    # vipps_app_public is deliberately not in the public serializer — customers learn about
    # Vipps App from GET /api/payments/vipps-app, which also checks the credentials.
    return {
        **_serialize_settings(settings),
        "vipps_app_public": settings.vipps_app_public,
        "vipps_qr_enabled": settings.vipps_qr_enabled,
        "vipps_qr_image_url": settings.vipps_qr_image_url,
        "vipps_number": settings.vipps_number,  # the saved number, even while the switch is off (the public settings show it only when usable)
        "vipps_qr_available": vipps_qr_available(settings),
        "stripe_enabled": settings.stripe_enabled,
        "cash_enabled": settings.cash_enabled,
        "cash_ticket_note": settings.cash_ticket_note,
        "cash_membership_note": settings.cash_membership_note,
        "bank_transfer_enabled": settings.bank_transfer_enabled,
        "bank_account_holder": settings.bank_account_holder,
        "bank_name": settings.bank_name,
        "bank_account_number": settings.bank_account_number,
        "bank_iban": settings.bank_iban,
        "bank_bic": settings.bank_bic,
        "bank_transfer_note": settings.bank_transfer_note,
        "bank_transfer_available": bank_transfer_available(settings),
        "donation_amounts": settings.donation_amounts,
        "donation_intro": settings.donation_intro,
        "donation_thanks": settings.donation_thanks,
        "message_footer_update": settings.message_footer_update,
        "message_footer_service": settings.message_footer_service,
        **{f: float(getattr(settings, f)) for f in FEE_PERCENT_FIELDS},
        **{f: getattr(settings, f) for f in FEE_FIXED_FIELDS},
    }


@admin_settings_bp.get("")
def admin_get_settings():
    return jsonify(_serialize_admin_settings(get_site_settings()))


@admin_settings_bp.patch("")
def admin_update_settings():
    data = request.get_json(silent=True) or {}
    cleaned, errors = _validate_settings_payload(data)
    if errors:
        return jsonify({"errors": errors}), 400

    settings = get_site_settings()
    # Vipps QR needs something to pay to: the number or the QR picture. Switching it on without either is refused; clearing the
    # last of them switches it off (a method that cannot be used must not stay on).
    number_after = cleaned["vipps_number"] if "vipps_number" in cleaned else settings.vipps_number
    has_details = bool((number_after or "").strip() or settings.vipps_qr_image_url)
    if cleaned.get("vipps_qr_enabled") and not has_details:
        return jsonify({"errors": {"vipps_qr_enabled": "Add your Vipps number or upload your Vipps QR picture first."}}), 400
    if not has_details and "vipps_qr_enabled" not in cleaned:
        cleaned["vipps_qr_enabled"] = False
    for field, value in cleaned.items():
        setattr(settings, field, value)
    db.session.commit()

    method_switches = {"vipps_app_public": "Vipps-App", "vipps_qr_enabled": "Vipps-QR", "cash_enabled": "Cash", "bank_transfer_enabled": "Bank transfer", "stripe_enabled": "Stripe"}
    switched = [field for field in method_switches if field in cleaned]
    if any(f in cleaned for f in FEE_PERCENT_FIELDS + FEE_FIXED_FIELDS):
        log_action(g.current_user, "settings_updated", "Updated payment fee settings")
    elif switched:
        for field in switched:
            state = "ON" if cleaned[field] else "OFF"
            log_action(g.current_user, "settings_updated", f"Switched {method_switches[field]} payments {state}")
    elif any(field in cleaned for field in BANK_FIELDS):
        log_action(g.current_user, "settings_updated", "Updated the bank transfer details")
    elif "vipps_number" in cleaned:
        log_action(g.current_user, "settings_updated", "Updated the Vipps number")
    elif "privacy_text" in cleaned or "terms_text" in cleaned:
        log_action(g.current_user, "settings_updated", "Updated the legal texts")
    elif "donation_amounts" in cleaned or "donation_intro" in cleaned or "donation_thanks" in cleaned:
        log_action(g.current_user, "settings_updated", "Updated the donation settings")
    elif "message_footer_update" in cleaned or "message_footer_service" in cleaned:
        log_action(g.current_user, "settings_updated", "Updated the wording of the message footers")
    elif "about_text" in cleaned:
        log_action(g.current_user, "settings_updated", "Updated the About page text")
    elif "home_content" in cleaned:
        log_action(g.current_user, "settings_updated", "Updated the home page content")
    else:
        log_action(g.current_user, "settings_updated", "Updated site contact settings")

    return jsonify(_serialize_admin_settings(settings))


@admin_settings_bp.post("/vipps-qr-image")
def admin_upload_vipps_qr_image():
    """The picture of the square's own Vipps QR code, shown to people who choose to pay with Vipps QR."""
    file = request.files.get("file")
    if file is None:
        return jsonify({"errors": {"file": "A file is required."}}), 400
    try:
        processed = process_upload(file)
    except MediaValidationError as exc:
        return jsonify({"errors": {"file": str(exc)}}), 400

    settings = get_site_settings()
    storage = get_public_storage()
    old_key = storage.key_from_url(settings.vipps_qr_image_url) if settings.vipps_qr_image_url else None
    storage_key = f"site/vipps-qr-{uuid.uuid4().hex}-{secure_filename(file.filename) or 'qr'}"
    storage.upload(storage_key, processed.original_bytes, processed.original_content_type)
    if old_key:
        storage.delete(old_key)
    settings.vipps_qr_image_url = storage.url_for(storage_key)
    db.session.commit()
    log_action(g.current_user, "settings_updated", "Updated the Vipps QR picture")
    return jsonify(_serialize_admin_settings(settings))


@admin_settings_bp.delete("/vipps-qr-image")
def admin_delete_vipps_qr_image():
    settings = get_site_settings()
    if settings.vipps_qr_image_url:
        old_key = get_public_storage().key_from_url(settings.vipps_qr_image_url)
        settings.vipps_qr_image_url = None
        if not vipps_qr_has_details(settings):
            settings.vipps_qr_enabled = False  # nothing left to pay to
        db.session.commit()
        if old_key:
            get_public_storage().delete(old_key)
        log_action(g.current_user, "settings_updated", "Removed the Vipps QR picture")
    return jsonify(_serialize_admin_settings(settings))


@admin_settings_bp.post("/heritage-image")
def admin_upload_heritage_image():
    """Replaces the Heritage page's hero photo — a single image, same upload flow as the
    committee/founder portraits (validated by process_upload, stored in the public bucket)."""
    file = request.files.get("file")
    if file is None:
        return jsonify({"errors": {"file": "A file is required."}}), 400

    try:
        processed = process_upload(file)
    except MediaValidationError as exc:
        return jsonify({"errors": {"file": str(exc)}}), 400

    settings = get_site_settings()
    storage = get_public_storage()
    old_key = storage.key_from_url(settings.heritage_image_url) if settings.heritage_image_url else None

    safe_name = secure_filename(file.filename) or "heritage"
    storage_key = f"site/heritage-{uuid.uuid4().hex}-{safe_name}"
    storage.upload(storage_key, processed.original_bytes, processed.original_content_type)
    if old_key:
        storage.delete(old_key)

    settings.heritage_image_url = storage.url_for(storage_key)
    db.session.commit()

    log_action(g.current_user, "settings_updated", "Updated the Heritage page image")

    return jsonify(_serialize_settings(settings))
