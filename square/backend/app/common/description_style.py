"""Shared validation for the optional per-item description-typeface override
(`description_style`, null = the site default — see SiteSettings.description_style)."""

from app.settings.admin_routes import DESCRIPTION_STYLES


def clean_description_style(data: dict, cleaned: dict, errors: dict) -> None:
    """Reads `description_style` from `data` into `cleaned` (None/"" clears it), or adds an error."""
    if "description_style" not in data:
        return
    value = data["description_style"]
    if value is None or value == "":
        cleaned["description_style"] = None
    elif value in DESCRIPTION_STYLES:
        cleaned["description_style"] = value
    else:
        errors["description_style"] = (
            f"Must be one of: {', '.join(DESCRIPTION_STYLES)}, or empty for the site default."
        )
