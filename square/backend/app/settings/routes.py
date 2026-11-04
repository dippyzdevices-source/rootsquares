from flask import Blueprint, jsonify

from app.settings.models import get_site_settings, vipps_qr_available

settings_bp = Blueprint("settings", __name__, url_prefix="/api/settings")


def _serialize_settings(settings) -> dict:
    return {
        "contact_email": settings.contact_email,
        "contact_phone": settings.contact_phone,
        "contact_address": settings.contact_address,
        "timezone": settings.timezone,
        "maintenance_mode": settings.maintenance_mode,
        "maintenance_allowed_event_slugs": settings.maintenance_allowed_event_slugs,
        "maintenance_allowed_page_paths": settings.maintenance_allowed_page_paths,
        "maintenance_hidden_page_paths": settings.maintenance_hidden_page_paths,
        "heritage_image_url": settings.heritage_image_url,
        "description_style": settings.description_style,
        "privacy_text": settings.privacy_text,
        "terms_text": settings.terms_text,
        "about_text": settings.about_text,
        "home_content": settings.home_content or {},
        # The number people pay to when they use Vipps QR: only while that method is on and a number is set (rootsquares W6-R38).
        "vipps_number": (settings.vipps_number or "").strip() if vipps_qr_available(settings) else None,
        "vipps_qr_image_url": settings.vipps_qr_image_url if vipps_qr_available(settings) else None,
    }


@settings_bp.get("")
def get_settings():
    """Public, no auth — the Contact page (and anywhere else that needs the association's
    contact details) fetches these instead of hardcoding them in the frontend.
    """
    return jsonify(_serialize_settings(get_site_settings()))
