# ruff: noqa: E501  (HTML table markup is long on purpose)
"""The look of every platform e-mail (W13-R5): the design project's `Email Template Send-ready.html` (Brass, light with a dark-mode variant), the footer in the
chocolate gradient of the site footer, and the real logo mark as an inline PNG (mail apps cannot show SVG; the PNGs are drawn by scripts/make_email_logo.py).
Table layout and inline styles on purpose (mail apps ignore most CSS). Every value is escaped. A plain-text body is always sent next to the HTML."""

from __future__ import annotations

import base64
from html import escape
from pathlib import Path
from typing import Any

ASSETS = Path(__file__).resolve().parent / "email_assets"
FONT = "Inter,Helvetica,Arial,sans-serif"
SERIF = "'Cormorant Garamond',Georgia,'Times New Roman',serif"
FOOT_GRADIENT = "linear-gradient(180deg,#140b07,#1b100a,#22150e)"

# Dark mode (design): swaps the light colours by matching the inline colour values. Apple Mail and Outlook apps honour it, Gmail mostly does not.
_CSS = (
    '@import url("https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@500&family=Inter:wght@400;500;600&display=swap");'
    '@media (prefers-color-scheme:dark){body,td[bgcolor="#ebe4d4"],table[bgcolor="#ebe4d4"]{background:#100f0c!important}'
    'td[bgcolor="#f4efe4"]{background:#14120f!important}table[bgcolor="#fbf8f0"]{background:#1c1a16!important}'
    'td[bgcolor="#1c1a16"]{background:#efe9dc!important}td[bgcolor="#9a7a2e"]{background:#c9a55a!important}'
    '[style*="#cfc5ad"]{border-color:#5a5343!important}[style*="color:#1c1a16"],h1{color:#efe9dc!important}'
    '[style*="color:#5e584c"]{color:#aaa291!important}[style*="color:#735510"]{color:#d2b06a!important}[style*="color:#9a7a2e"]{color:#c9a55a!important}'
    'a[style*="color:#fbf8f0"]{color:#14120f!important}a{color:#d2b06a}.logo-ink{display:none!important}.logo-cream{display:inline-block!important}}'
    "@media(max-width:620px){.w{width:100%!important}.p{padding-left:24px!important;padding-right:24px!important}.h1{font-size:38px!important;line-height:40px!important}}"
    "a{color:#735510}"
)


def _rich(text: str) -> str:
    """Escaped text; **word** becomes bold."""
    parts = escape(text).split("**")
    return "".join(f'<strong style="color:#1c1a16;">{p}</strong>' if i % 2 else p for i, p in enumerate(parts))


def inline_images() -> list[dict[str, Any]]:
    """The two logo PNGs as inline attachments (Resend `content_id`), referenced in the HTML as cid:rs-logo-ink and cid:rs-logo-cream."""
    return [
        {"filename": f"{name}.png", "content": base64.b64encode((ASSETS / f"{name}.png").read_bytes()).decode(), "content_id": f"rs-{name}"}
        for name in ("logo-ink", "logo-cream")
    ]


def _logo(variant: str, size: int, extra: str = "") -> str:
    return (
        f'<img class="logo-{variant}" src="cid:rs-logo-{variant}" width="{size}" height="{size}" alt="" '
        f'style="display:inline-block;vertical-align:middle;border:0;{extra}">'
    )


def render(*, eyebrow: str, heading: str, paragraphs: list[str], button: tuple[str, str] | None, site_url: str, preheader: str = "", note: str = "") -> str:
    site = escape(site_url.rstrip("/"), quote=True)
    body = "".join(
        f'<tr><td class="p" style="padding:{20 if i == 0 else 16}px 48px 0 48px;font-family:{FONT};font-size:16px;line-height:25px;color:#5e584c;">{_rich(p)}</td></tr>'
        for i, p in enumerate(paragraphs)
    )
    cta = ""
    if button is not None:
        label, url = button
        cta = (
            '<tr><td class="p" style="padding:32px 48px 0 48px;"><table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>'
            f'<td bgcolor="#1c1a16" style="background:#1c1a16;border-radius:6px;"><a href="{escape(url, quote=True)}" '
            f'style="display:block;padding:14px 28px;font-family:{FONT};font-size:15px;font-weight:bold;line-height:20px;color:#fbf8f0;text-decoration:none;">'
            f"{escape(label)}</a></td></tr></table></td></tr>"
        )
    note_row = (
        f'<tr><td class="p" style="padding:28px 48px 0 48px;font-family:{FONT};font-size:14px;line-height:22px;color:#5e584c;">{_rich(note)}</td></tr>'
        if note
        else ""
    )
    link = 'style="color:#f3efe4;text-decoration:none;"'
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light dark"><meta name="supported-color-schemes" content="light dark"><title>{escape(heading)}</title><style>{_CSS}</style></head>
<body style="margin:0;padding:0;background:#ebe4d4;">
<span style="display:none;max-height:0;overflow:hidden;opacity:0;color:#ebe4d4;font-size:1px;line-height:1px;">{escape(preheader)}</span>
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" bgcolor="#ebe4d4" style="background:#ebe4d4;"><tr><td align="center" style="padding:32px 12px;">
<table role="presentation" class="w" cellpadding="0" cellspacing="0" border="0" width="600" style="width:600px;max-width:600px;">
<tr><td class="p" style="padding:0 40px 20px 40px;font-family:{FONT};font-size:22px;font-weight:bold;letter-spacing:-0.3px;color:#1c1a16;">{_logo("ink", 32)}{_logo("cream", 32, "display:none;")}<span style="vertical-align:middle;">&nbsp; rootsquares</span></td></tr>
<tr><td bgcolor="#f4efe4" style="background:#f4efe4;border:1px solid #cfc5ad;border-radius:6px;">
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">
<tr><td class="p" style="padding:48px 48px 0 48px;font-family:{FONT};font-size:12px;line-height:12px;letter-spacing:2px;text-transform:uppercase;color:#735510;">{escape(eyebrow)}</td></tr>
<tr><td class="p" style="padding:16px 48px 0 48px;"><h1 class="h1" style="margin:0;font-family:{SERIF};font-weight:500;font-size:46px;line-height:48px;letter-spacing:-0.4px;color:#1c1a16;">{escape(heading)}</h1></td></tr>
<tr><td class="p" style="padding:20px 48px 0 48px;"><table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr><td width="56" height="1" bgcolor="#9a7a2e" style="width:56px;height:1px;line-height:1px;font-size:1px;">&nbsp;</td></tr></table></td></tr>
{body}{cta}{note_row}
<tr><td style="font-size:0;line-height:48px;height:48px;">&nbsp;</td></tr>
</table></td></tr>
<tr><td style="font-size:0;line-height:12px;height:12px;">&nbsp;</td></tr>
<tr><td bgcolor="#1b100a" style="background:#1b100a;background-image:{FOOT_GRADIENT};border-radius:6px;">
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">
<tr><td class="p" style="padding:32px 40px 0 40px;font-family:{FONT};font-size:20px;font-weight:bold;color:#f3efe4;">{_logo("cream", 28, "display:inline-block!important;")}<span style="vertical-align:middle;">&nbsp; rootsquares</span></td></tr>
<tr><td class="p" style="padding:8px 40px 0 40px;font-family:{FONT};font-size:14px;line-height:21px;color:#c9bca8;">Made for associations across the Nordics.</td></tr>
<tr><td class="p" style="padding:20px 40px 0 40px;font-family:{FONT};font-size:14px;line-height:20px;"><a href="{site}/pricing" {link}>Pricing</a>&nbsp;&nbsp;&nbsp;<a href="{site}/templates" {link}>Templates</a>&nbsp;&nbsp;&nbsp;<a href="{site}/contact" {link}>Contact</a></td></tr>
<tr><td class="p" style="padding:24px 40px 0 40px;"><table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%"><tr><td height="1" bgcolor="#5a4630" style="height:1px;line-height:1px;font-size:1px;">&nbsp;</td></tr></table></td></tr>
<tr><td class="p" style="padding:16px 40px 32px 40px;font-family:{FONT};font-size:12px;line-height:18px;color:#c9bca8;">&copy; rootsquares<br>You received this because of your square on rootsquares. Questions? Just reply to this e-mail.</td></tr>
</table></td></tr>
</table></td></tr></table></body></html>
"""


def from_text(text: str, *, site_url: str, eyebrow: str, heading: str, button_label: str = "Open") -> dict[str, Any]:
    """Keyword arguments for `EmailProvider.send` built from a mail's plain text, so the text and HTML versions always say the same:
    blank lines separate paragraphs, and the first line that is only a link becomes the button."""
    button: tuple[str, str] | None = None
    kept: list[str] = []
    current: list[str] = []
    for raw in [*text.strip().splitlines(), ""]:
        line = raw.strip()
        if line.startswith(("http://", "https://")) and " " not in line and button is None:
            button = (button_label, line)
            line = ""
        if line:
            current.append(line)
        elif current:
            kept.append(" ".join(current))
            current = []
    return {
        "html": render(eyebrow=eyebrow, heading=heading, paragraphs=kept, button=button, site_url=site_url, preheader=kept[0] if kept else ""),
        "inline_images": inline_images(),
    }
