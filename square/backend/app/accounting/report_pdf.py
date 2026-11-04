"""The per-event accounting report as a PDF — everything the accounting page shows, in one file.

Built with fpdf2 + HarfBuzz text shaping so Bengali (and Norwegian æøå) render correctly: the
bundled Marcellus (headings, figures) and Karla (text) are the site's own typefaces; Noto Sans and Noto Sans Bengali are the fallbacks (Bengali text, any glyph they lack). This module
only lays out data it is handed — all numbers are computed by the accounting routes.
"""

import re
from datetime import date, datetime
from pathlib import Path

from fpdf import FPDF
from fpdf.enums import TableCellFillMode
from fpdf.fonts import FontFace

from app.common.money import format_money
from app.common.site import site_currency, site_name

FONT_DIR = Path(__file__).parent / "fonts"

INK = (58, 42, 30)
MUTED = (110, 98, 88)
HAIRLINE = (222, 214, 204)
SUNKEN = (246, 242, 236)
ACCENT = (157, 62, 38)
SUCCESS = (28, 110, 66)
PAGE_W = 210
MARGIN = 15
CONTENT_W = PAGE_W - 2 * MARGIN


def money(amount: int | None) -> str:
    """Minor units → "4 535.00 kr" (or the square's own currency), the same wording the accounting page uses."""
    return format_money(amount, site_currency())


def day(value: str | date | datetime | None) -> str:
    if value is None:
        return "—"
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    return f"{value.day} {value.strftime('%b %Y')}"


class _Report(FPDF):
    def __init__(self, title: str, generated: str):
        super().__init__(orientation="P", unit="mm", format="A4")
        self._report_title = title
        self._generated = generated
        self.set_margins(MARGIN, MARGIN, MARGIN)
        self.set_auto_page_break(auto=True, margin=18)
        # The site's own typefaces: Marcellus for headings and figures, Karla for text. Noto Sans stays as the
        # fallback for any glyph they lack, Noto Sans Bengali for Bengali text.
        self.add_font("Marcellus", "", str(FONT_DIR / "Marcellus-Regular.ttf"))
        self.add_font("Karla", "", str(FONT_DIR / "Karla-Regular.ttf"))
        self.add_font("Karla", "B", str(FONT_DIR / "Karla-SemiBold.ttf"))  # the page's "bold" is weight 600
        self.add_font("NotoSans", "", str(FONT_DIR / "NotoSans-Regular.ttf"))
        self.add_font("NotoSans", "B", str(FONT_DIR / "NotoSans-Bold.ttf"))
        self.add_font("NotoSansBengali", "", str(FONT_DIR / "NotoSansBengali-Regular.ttf"))
        self.add_font("NotoSansBengali", "B", str(FONT_DIR / "NotoSansBengali-Bold.ttf"))
        self.set_fallback_fonts(["NotoSans", "NotoSansBengali"], exact_match=False)
        self.set_text_shaping(True)

    def footer(self):
        self.set_y(-12)
        self.set_font("Karla", "", 8)
        self.set_text_color(*MUTED)
        self.cell(CONTENT_W / 2, 6, f"{self._report_title} · generated {self._generated}", align="L")
        self.cell(CONTENT_W / 2, 6, f"Page {self.page_no()} of {{nb}}", align="R")


def _heading(pdf: _Report, text: str) -> None:
    if pdf.get_y() > 245:
        pdf.add_page()
    pdf.ln(4)
    pdf.set_font("Marcellus", "", 13)
    pdf.set_text_color(*INK)
    pdf.cell(0, 7, text, new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(*HAIRLINE)
    pdf.line(MARGIN, pdf.get_y(), PAGE_W - MARGIN, pdf.get_y())
    pdf.ln(2)


def _tab_heading(pdf: _Report, text: str, count: int | None = None) -> None:
    """The page's four tabs (Overview, Collections, Expenses, Donations & Sponsorships) are stacked in the PDF, so each
    one opens with a heading of its own - larger than the sub-headings inside it, with the tab's count like the page."""
    _ensure(pdf, 30)
    pdf.ln(6)
    pdf.set_font("Marcellus", "", 19)
    pdf.set_text_color(*INK)
    label = text
    pdf.cell(pdf.get_string_width(label) + 2, 9, label)
    if count is not None:
        pdf.set_font("Karla", "", 11)
        pdf.set_text_color(*MUTED)
        pdf.cell(0, 9, f"  {count}")
    pdf.ln(9)
    pdf.set_draw_color(*ACCENT)
    pdf.set_line_width(0.5)
    pdf.line(MARGIN, pdf.get_y(), PAGE_W - MARGIN, pdf.get_y())
    pdf.set_line_width(0.2)
    pdf.ln(1)


def _card_title(pdf: _Report, text: str) -> None:
    """The page's card titles: small accent capitals, tracked out (Tickets by type, Tickets by Channels ...)."""
    _ensure(pdf, 16)
    pdf.ln(5)
    pdf.set_font("Karla", "B", 7.5)
    pdf.set_text_color(*ACCENT)
    pdf.set_char_spacing(1)
    pdf.cell(0, 5, text.upper(), new_x="LMARGIN", new_y="NEXT")
    pdf.set_char_spacing(0)
    pdf.set_draw_color(*HAIRLINE)
    pdf.line(MARGIN, pdf.get_y(), PAGE_W - MARGIN, pdf.get_y())
    pdf.ln(1.5)


COUPON_COLS = [46.0, 14.0, 34.0, 30.0, 28.0, 28.0]  # Coupon, Orders, Used, Before discount, Discount, Paid


def _coupon_table(pdf: _Report, coupons: list[dict]) -> None:
    """Coupon usage, drawn by hand so the "Used" column can carry the page's little meter (used / limit)."""
    xs = [MARGIN]
    for w in COUPON_COLS:
        xs.append(xs[-1] + w)

    def put(i: int, y: float, h: float, text: str, style: str = "", align: str = "L", colour=INK, size: float = 9) -> None:
        pdf.set_xy(xs[i] + 1.5, y)
        pdf.set_font("Karla", style, size)
        pdf.set_text_color(*colour)
        w = COUPON_COLS[i] - 3
        while size > 6 and pdf.get_string_width(text) > w:
            size -= 0.5
            pdf.set_font("Karla", style, size)
        pdf.cell(w, h, text, align=align)

    def rule(y: float) -> None:
        pdf.set_draw_color(*HAIRLINE)
        pdf.line(MARGIN, y, PAGE_W - MARGIN, y)

    _ensure(pdf, 14)
    y = pdf.get_y()
    pdf.set_char_spacing(0.5)
    for i, head in enumerate(["COUPON", "ORDERS", "USED", "BEFORE DISCOUNT", "DISCOUNT", "PAID"]):
        put(i, y, 6, head, "B", "L" if i in (0, 2) else "R", MUTED, 7)
    pdf.set_char_spacing(0)
    y += 6.5
    rule(y)
    pdf.set_y(y)
    for c in coupons:
        pdf.set_y(y)
        _ensure(pdf, 13)
        y = pdf.get_y()
        name = c["coupon_code"]
        if c.get("discount_percent") is not None:
            name += f" ({c['discount_percent']}% off)"
        if c.get("is_active") is False:
            name += " · retired"
        used = str(c["tickets_count"]) + (f" / {c['max_redemptions']}" if c.get("max_redemptions") is not None else "")
        put(0, y + 1, 5.5, name, "B")
        put(1, y + 1, 5.5, str(c["orders_count"]), "", "R")
        put(2, y + 1, 5.5, used)
        if c.get("max_redemptions"):
            share = min(1.0, c["tickets_count"] / c["max_redemptions"])
            bar_w = COUPON_COLS[2] - 5
            pdf.set_fill_color(*HAIRLINE)
            pdf.rect(xs[2] + 1.5, y + 7, bar_w, 1.3, style="F")
            pdf.set_fill_color(*ACCENT)
            pdf.rect(xs[2] + 1.5, y + 7, bar_w * share, 1.3, style="F")
        put(3, y + 1, 5.5, money(c["gross_total"]), "", "R")
        put(4, y + 1, 5.5, "−" + money(c["discount_total"]), "", "R", ACCENT)
        put(5, y + 1, 5.5, money(c["paid_total"]), "B", "R")
        y += 10.5
        rule(y)
        for tt in c["by_ticket_type"]:
            pdf.set_y(y)
            _ensure(pdf, 7)  # a page break mid-coupon: carry on at the top of the new page
            y = pdf.get_y()
            on_day = f" ({date.fromisoformat(tt['valid_on']).strftime('%a %d %b')})" if tt.get("valid_on") else ""
            pdf.set_xy(xs[0] + 4, y)
            pdf.set_font("Karla", "", 8.5)
            pdf.set_text_color(*MUTED)
            pdf.cell(sum(COUPON_COLS[:5]) - 4, 5.5, f"{tt['name']}{on_day}")
            pdf.set_font("Karla", "B", 8.5)
            pdf.set_text_color(*INK)
            pdf.cell(COUPON_COLS[5], 5.5, str(tt["count"]), align="R")
            y += 5.5
            rule(y)
        pdf.set_y(y)
    if len(coupons) > 1:
        pdf.set_y(y)
        _ensure(pdf, 9)
        y = pdf.get_y()
        put(0, y + 1, 5.5, "All coupons", "B")
        put(1, y + 1, 5.5, str(sum(c["orders_count"] for c in coupons)), "B", "R")
        put(2, y + 1, 5.5, str(sum(c["tickets_count"] for c in coupons)), "B")
        put(3, y + 1, 5.5, money(sum(c["gross_total"] for c in coupons)), "B", "R")
        put(4, y + 1, 5.5, "−" + money(sum(c["discount_total"] for c in coupons)), "B", "R", ACCENT)
        put(5, y + 1, 5.5, money(sum(c["paid_total"] for c in coupons)), "B", "R")
        y += 7.5
        rule(y)
        pdf.set_y(y)
    pdf.set_fill_color(255, 255, 255)
    pdf.ln(2)


def _note(pdf: _Report, text: str) -> None:
    pdf.set_font("Karla", "", 9)
    pdf.set_text_color(*MUTED)
    pdf.cell(0, 6, text, new_x="LMARGIN", new_y="NEXT")


def _pairs(pdf: _Report, rows: list[tuple[str, str]], empty: str) -> None:
    """Label left, bold value right — the accounting page's small summary cards."""
    if not rows:
        _note(pdf, empty)
        return
    pdf.set_draw_color(*HAIRLINE)
    for label, value in rows:
        pdf.set_font("Karla", "", 10)
        pdf.set_text_color(*MUTED)
        pdf.cell(CONTENT_W - 40, 7, label)
        pdf.set_font("Karla", "B", 10)
        pdf.set_text_color(*INK)
        pdf.cell(40, 7, value, align="R", new_x="LMARGIN", new_y="NEXT")
        pdf.line(MARGIN, pdf.get_y(), PAGE_W - MARGIN, pdf.get_y())


BOLD = FontFace(emphasis="BOLD", size_pt=9, color=INK)


def _put(row, cell) -> None:
    """A table cell is plain text, or (text, {"bold": True, "colspan": n, "align": "R"})."""
    if isinstance(cell, tuple):
        text, opts = cell
        row.cell(
            text,
            colspan=opts.get("colspan", 1),
            align=opts.get("align"),
            style=BOLD if opts.get("bold") else None,
        )
    else:
        row.cell(cell)


def _table(pdf: _Report, header: list[str], rows: list[list], widths: list[float], right: set[int], total: list[str] | None = None) -> None:
    pdf.set_fill_color(255, 255, 255)  # the cards/bars above leave a colour fill behind
    pdf.set_draw_color(*HAIRLINE)
    pdf.set_line_width(0.2)
    aligns = tuple("RIGHT" if i in right else "LEFT" for i in range(len(header)))
    with pdf.table(
        col_widths=widths,
        text_align=aligns,
        line_height=5.5,
        borders_layout="HORIZONTAL_LINES",
        cell_fill_mode=TableCellFillMode.NONE,
        padding=(1.2, 1.5),
        first_row_as_headings=True,
    ) as table:
        pdf.set_font("Karla", "B", 8)
        pdf.set_text_color(*MUTED)
        head = table.row()
        for text in header:
            head.cell(text.upper())
        pdf.set_font("Karla", "", 9)
        pdf.set_text_color(*INK)
        for values in rows:
            row = table.row()
            for cell in values:
                _put(row, cell)
        if total:
            pdf.set_font("Karla", "B", 9)
            row = table.row()
            for text in total:
                row.cell(text)
    pdf.set_font("Karla", "", 9)


GREY_SEGMENT = (201, 184, 166)
CARD_FILL = (253, 248, 241)


def _ensure(pdf: _Report, height: float) -> None:
    """Start a new page when `height` mm would run past the bottom margin."""
    if pdf.get_y() + height > 276:
        pdf.add_page()


def _card(pdf: _Report, x: float, y: float, w: float, h: float) -> None:
    pdf.set_fill_color(*CARD_FILL)
    pdf.set_draw_color(*HAIRLINE)
    pdf.set_line_width(0.2)
    pdf.rect(x, y, w, h, style="DF", round_corners=True, corner_radius=2.5)


def _label(pdf: _Report, x: float, y: float, w: float, text: str, colour=MUTED) -> None:
    pdf.set_xy(x, y)
    pdf.set_font("Karla", "", 7)  # the page's card labels are regular weight, muted, tracked out
    pdf.set_text_color(*colour)
    pdf.set_char_spacing(1)  # the page tracks these small capitals out (0.14em)
    pdf.cell(w, 4, text.upper())
    pdf.set_char_spacing(0)


def money_rounded(amount: int | None) -> str:
    """Whole units, "71 606 kr" (or the square's own currency); the figure cards on the accounting page round the same way."""
    text = format_money(round((amount or 0) / 100) * 100, site_currency(), whole_if_round=True)
    return re.sub(r"(?<=\d) (?=\d)", " ", text)  # no line break inside the number


def _fit_cell(pdf: _Report, w: float, h: float, text: str, family: str, size: float) -> None:
    """One-line cell that shrinks its font until the text fits `w` (so a figure never spills out of its card)."""
    pdf.set_font(family, "", size)
    while size > 6 and pdf.get_string_width(text) > w:
        size -= 0.5
        pdf.set_font(family, "", size)
    pdf.cell(w, h, text)


def _schedule(event) -> tuple[str, str]:
    """Single-day or multi-day, and the dates - the "Event schedule" card on the accounting page."""
    start, end = event.start_datetime, event.end_datetime
    if end is None or end.date() == start.date():
        times = f" · {start:%H:%M}" + (f" – {end:%H:%M}" if end else "")
        return "Single-day event", f"{day(start)}{times}"
    days = (end.date() - start.date()).days + 1
    return f"Multi-day event · {days} days", f"{day(start)} – {day(end)}"


def _hero(pdf: _Report, summary: dict, event) -> None:
    """The accounting page's hero: Net revenue (two rows) over the Event schedule card on the left, the six
    figure cards in three rows on the right - one shared row height, so both sides line up."""
    kpi_h = 23.0
    row_gap = 3.0
    h = 3 * kpi_h + 2 * row_gap
    _ensure(pdf, h + 4)
    top = pdf.get_y()
    left_w = 100.0
    gap = 4.0
    net_h = 2 * kpi_h + row_gap
    _card(pdf, MARGIN, top, left_w, net_h)
    inner_x = MARGIN + 5
    inner_w = left_w - 10

    collection = summary["collection_total"]
    donations = summary.get("donations_total", 0)
    sponsors = summary.get("sponsorships_total", 0)
    tickets = max(0, collection - donations - sponsors)

    _label(pdf, inner_x, top + 3.5, inner_w, "Net revenue")
    pdf.set_xy(inner_x, top + 8)
    pdf.set_text_color(*SUCCESS)
    _fit_cell(pdf, inner_w, 11, money_rounded(summary["net_total"]), "Marcellus", 26)
    pdf.set_xy(inner_x, top + 20)
    pdf.set_font("Karla", "", 8.5)
    pdf.set_text_color(*MUTED)
    pdf.cell(inner_w, 4.5, f"{money_rounded(collection)} collected  −  {money_rounded(summary['expenses_total'])} expenses")

    bar_y = top + 26.5
    pdf.set_fill_color(*HAIRLINE)
    pdf.rect(inner_x, bar_y, inner_w, 2.4, style="F")
    if collection > 0:
        x = inner_x
        for amount, colour in ((tickets, SUCCESS), (donations, ACCENT), (sponsors, GREY_SEGMENT)):
            seg = inner_w * amount / collection
            if seg > 0:
                pdf.set_fill_color(*colour)
                pdf.rect(x, bar_y, seg, 2.4, style="F")
                x += seg
    legend = (
        (SUCCESS, f"Ticket sales {money_rounded(tickets)}"),
        (ACCENT, f"Donations {money_rounded(donations)}"),
        (GREY_SEGMENT, f"Sponsorships {money_rounded(sponsors)}"),
    )
    pdf.set_font("Karla", "", 7.5)
    ly = top + 31.5
    for colour, text in legend:
        # one item per line, like the page
        pdf.set_fill_color(*colour)
        pdf.ellipse(inner_x, ly + 1.1, 2.2, 2.2, style="F")
        pdf.set_xy(inner_x + 3.6, ly)
        pdf.set_text_color(*MUTED)
        pdf.cell(inner_w - 3.6, 4.4, text)
        ly += 4.9

    # Event schedule: the third row on the left
    sy = top + net_h + row_gap
    _card(pdf, MARGIN, sy, left_w, kpi_h)
    kind, dates = _schedule(event)
    _label(pdf, inner_x, sy + 3, inner_w, "Event schedule")
    pdf.set_xy(inner_x, sy + 8)
    pdf.set_text_color(*INK)
    _fit_cell(pdf, inner_w, 6, kind, "Marcellus", 13)
    pdf.set_xy(inner_x, sy + 15.5)
    pdf.set_font("Karla", "", 7.5)
    pdf.set_text_color(*MUTED)
    pdf.cell(inner_w, 4, dates)

    coupons = summary.get("coupon_usage", [])
    coupon_tickets = sum(c["tickets_count"] for c in coupons)
    discount = sum(c["discount_total"] for c in coupons)
    gross = sum(c["gross_total"] for c in coupons)
    recorded = summary.get("recorded_expenses_total", 0)
    kpis = [
        ("Collection", money_rounded(collection), "Incl. donations & sponsors"),
        ("Expenses", money_rounded(summary["expenses_total"]), "Recorded + provider fees" if recorded else "Provider fees only"),
        ("Tickets sold", str(summary["tickets_sold"]), f"{coupon_tickets} used a coupon"),
        ("Coupon discounts", ("−" if discount else "") + money_rounded(discount), f"On {money_rounded(gross)} list price"),
        ("Donations", money_rounded(donations), "Received, fees absorbed"),
        ("Sponsorships", money_rounded(sponsors), "Received"),
    ]
    right_x = MARGIN + left_w + gap
    kpi_w = (CONTENT_W - left_w - gap - 3) / 2
    for i, (label, value, note) in enumerate(kpis):
        kx = right_x + (i % 2) * (kpi_w + 3)
        ky = top + (i // 2) * (kpi_h + row_gap)
        _card(pdf, kx, ky, kpi_w, kpi_h)
        _label(pdf, kx + 3.5, ky + 3, kpi_w - 7, label)
        pdf.set_xy(kx + 3.5, ky + 8.5)
        pdf.set_text_color(*INK)
        _fit_cell(pdf, kpi_w - 7, 6, value, "Marcellus", 12)
        pdf.set_xy(kx + 3.5, ky + 16)
        pdf.set_font("Karla", "", 6.5)
        pdf.set_text_color(*MUTED)
        pdf.cell(kpi_w - 7, 4, note)
    pdf.set_fill_color(255, 255, 255)
    pdf.set_y(top + h + 4)


def _checkin(pdf: _Report, summary: dict) -> None:
    expected = summary.get("tickets_expected", 0)
    if not expected:
        return
    done = summary.get("tickets_checked_in", 0)
    rate = round(done / expected * 100)
    _ensure(pdf, 18)
    top = pdf.get_y()
    _card(pdf, MARGIN, top, CONTENT_W, 14)
    _label(pdf, MARGIN + 5, top + 2.5, 40, "Check-in rate")
    track_x, track_w = MARGIN + 5, CONTENT_W - 80
    pdf.set_fill_color(*HAIRLINE)
    pdf.rect(track_x, top + 8, track_w, 2.4, style="F")
    pdf.set_fill_color(*SUCCESS)
    pdf.rect(track_x, top + 8, track_w * rate / 100, 2.4, style="F")
    pdf.set_xy(MARGIN + CONTENT_W - 70, top + 3)
    pdf.set_font("Marcellus", "", 16)
    pdf.set_text_color(*INK)
    pdf.cell(16, 8, f"{rate}%")
    pdf.set_font("Karla", "", 8)
    pdf.set_text_color(*MUTED)
    pdf.cell(52, 8, f"{done} of {expected} tickets checked in")
    pdf.set_y(top + 18)


def _meter_rows(pdf: _Report, rows: list[tuple[str, int]], empty: str) -> None:
    """Ticket types: label left, bold count right, a thin proportional bar underneath."""
    if not rows:
        _note(pdf, empty)
        return
    biggest = max(1, max(count for _label_text, count in rows))
    for text, count in rows:
        _ensure(pdf, 10)
        y = pdf.get_y()
        pdf.set_xy(MARGIN, y)
        pdf.set_font("Karla", "", 9.5)
        pdf.set_text_color(*MUTED)
        pdf.cell(CONTENT_W - 30, 6, text)
        pdf.set_font("Karla", "B", 9.5)
        pdf.set_text_color(*INK)
        pdf.cell(30, 6, str(count), align="R")
        pdf.set_fill_color(*HAIRLINE)
        pdf.rect(MARGIN, y + 6.4, CONTENT_W, 1.4, style="F")
        pdf.set_fill_color(*ACCENT)
        pdf.rect(MARGIN, y + 6.4, CONTENT_W * count / biggest, 1.4, style="F")
        pdf.set_y(y + 9.5)


def _channel_rows(pdf: _Report, summary: dict, provider_label) -> None:
    channels = summary["tickets_by_sale_mode"]
    if not channels:
        _note(pdf, "No paid tickets yet.")
        return
    fees = {f["provider"]: f for f in summary.get("fees_by_provider", [])}
    pdf.set_draw_color(*HAIRLINE)
    for row in channels:
        _ensure(pdf, 13)
        y = pdf.get_y()
        pdf.set_xy(MARGIN, y)
        pdf.set_font("Karla", "B", 9.5)
        pdf.set_text_color(*INK)
        pdf.cell(CONTENT_W - 30, 6, provider_label(row["provider"]))
        pdf.cell(30, 6, str(row["count"]), align="R")
        fee = fees.get(row["provider"])
        commission = (fee["processing"] - fee.get("processing_donations", 0)) if fee else 0
        sub = f"Amount {money(row.get('amount', 0))}" + (f" · Commission {money(commission)}" if commission else "")
        pdf.set_xy(MARGIN, y + 6)
        pdf.set_font("Karla", "", 8)
        pdf.set_text_color(*MUTED)
        pdf.cell(CONTENT_W, 4.5, sub)
        pdf.line(MARGIN, y + 11.5, PAGE_W - MARGIN, y + 11.5)
        pdf.set_y(y + 12)
    if summary.get("processing_fees_total"):
        _ensure(pdf, 8)
        pdf.set_font("Karla", "B", 9.5)
        pdf.set_text_color(*INK)
        pdf.cell(CONTENT_W - 40, 7, "Provider commissions")
        pdf.cell(40, 7, money(summary["processing_fees_total"]), align="R", new_x="LMARGIN", new_y="NEXT")


def build_event_report_pdf(
    *,
    event,
    phase_label: str,
    summary: dict,
    collections: list[dict],
    expenses: list[dict],
    provider_label,
    category_label,
    generated_at: datetime,
    collection_details: bool = False,
    contributions: list[dict] | None = None,
) -> bytes:
    generated = generated_at.strftime("%d %b %Y %H:%M")
    pdf = _Report(f"Accounting report · {event.title}", generated)
    pdf.alias_nb_pages()
    pdf.add_page()

    # Title block
    pdf.set_font("Karla", "B", 8)
    pdf.set_text_color(*ACCENT)
    pdf.set_char_spacing(1.4)
    pdf.cell(0, 5, f"{site_name().upper()} · ACCOUNTING REPORT", new_x="LMARGIN", new_y="NEXT")
    pdf.set_char_spacing(0)
    pdf.set_font("Marcellus", "", 22)
    pdf.set_text_color(*INK)
    pdf.multi_cell(0, 9, event.title, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Karla", "", 10)
    pdf.set_text_color(*MUTED)
    when = day(event.start_datetime)
    if event.end_datetime and event.end_datetime.date() != event.start_datetime.date():
        when = f"{when} – {day(event.end_datetime)}"
    meta = [when, phase_label]
    if event.venue:
        meta.append(event.venue)
    pdf.multi_cell(0, 5.5, " · ".join(meta), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 5.5, f"Generated {generated}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    _hero(pdf, summary, event)
    _checkin(pdf, summary)

    # How the headline figures are made up (the same bullets as the accounting page)
    pdf.set_font("Karla", "B", 7)
    pdf.set_text_color(*ACCENT)
    pdf.set_char_spacing(1)
    pdf.cell(0, 5, "HOW THESE NUMBERS ARE CALCULATED", new_x="LMARGIN", new_y="NEXT")
    pdf.set_char_spacing(0)
    pdf.set_font("Karla", "", 8.5)
    pdf.set_text_color(*MUTED)
    for line in (
        "**Collection** = what customers paid in total: paid order totals (Cash + Vipps QR + Vipps App + free orders, each after its coupon discount) + convenience fees + donations and sponsorships received",
        "**Expenses** = all expenses entered for this event + the payment providers' processing fees",
        "**Net** = Collection − Expenses",
        "**Tickets sold** = tickets on paid orders, all ticket types, free and coupon tickets included",
        "Pending, rejected, cancelled and refunded orders are not counted.",
    ):
        pdf.multi_cell(0, 4.6, "•  " + line, new_x="LMARGIN", new_y="NEXT", markdown=True)

    _tab_heading(pdf, "Overview")
    _card_title(pdf, "Tickets by type")
    _meter_rows(
        pdf,
        [
            (f'{r["name"]} ({date.fromisoformat(r["valid_on"]).strftime("%a %d %b")})' if r.get("valid_on") else r["name"], r["count"])
            for r in summary["tickets_by_type"]
        ],
        "No tickets sold yet.",
    )

    _card_title(pdf, "Tickets by Channels")
    _channel_rows(pdf, summary, provider_label)

    coupons = summary["coupon_usage"]
    if coupons:
        _card_title(pdf, "Coupons at a glance")
        _pairs(
            pdf,
            [
                ("Coupon orders", str(sum(c["orders_count"] for c in coupons))),
                ("Revenue given up", money(sum(c["discount_total"] for c in coupons))),
                ("Still paid by customers", money(sum(c["paid_total"] for c in coupons))),
            ],
            "",
        )

    if summary["top_expense_categories"]:
        _card_title(pdf, "Top Expenses")
        _pairs(pdf, [(category_label(r["category"]), money(r["amount"])) for r in summary["top_expense_categories"]], "")

    _heading(pdf, "Coupon usage")
    coupons = summary["coupon_usage"]
    if not coupons:
        _note(pdf, "No coupons were used on paid orders.")
    else:
        _coupon_table(pdf, coupons)

    _tab_heading(pdf, "Collections", len(collections))
    if not collections:
        _note(pdf, "No paid ticket orders yet.")
    else:
        rows = []
        for c in collections:
            method = provider_label(c["payment_method"]) if c["payment_method"] else (f"Coupon ({c['coupon_code']})" if c.get("coupon_code") else "—")
            rows.append([day(c["date"]), c["order_number"], c["customer_name"] or "—", method, money(c["amount"])])
            if collection_details and c.get("tickets"):
                # What was bought, one line per ticket type, across the full width under the order.
                rows.append([("", {}), (chr(10).join(c["tickets"]), {"colspan": 4})])
        _table(pdf, ["Date", "Reference", "Payer", "Method", "Amount"], rows, [22, 34, 44, 46, 34], {4}, ["Total", "", f"{len(collections)} order{'s' if len(collections) != 1 else ''}", "", money(sum(c["amount"] for c in collections))])

    fee_lines = [f for f in (summary.get("fees_by_provider") or []) if f["processing"]]
    _tab_heading(pdf, "Expenses", len(expenses) + len(fee_lines))
    if not expenses and not fee_lines:
        _note(pdf, "No expenses recorded.")
    else:
        rows = []
        for f in fee_lines:
            rows.append(["—", f"{provider_label(f['provider'])} processing fees", "Payment fees", provider_label(f["provider"]), "—", money(f["processing"])])
        for e in expenses:
            description = e["description"] + (f"\n{e['notes']}" if e.get("notes") else "")
            rows.append([day(e["date"]), description, category_label(e["category"]), e.get("vendor") or "—", "Yes" if e.get("receipt_key") else "No", money(e["amount"])])
        _table(pdf, ["Date", "Description", "Category", "Vendor", "Receipt", "Amount"], rows, [22, 50, 30, 30, 20, 28], {5}, ["Total", "", "", "", "", money(sum(e["amount"] for e in expenses) + sum(f["processing"] for f in fee_lines))])


    contributions = contributions or []
    _tab_heading(pdf, "Donations & Sponsorships", len(contributions))
    if not contributions:
        _note(pdf, "No donations or Sponsorships recorded.")
    else:
        rows = [
            [day(c["date"]), c["name"], "Sponsorship" if c["kind"] == "sponsorship" else "Donation", provider_label(c["method"]) if c.get("method") else "—", money(c["amount"])]
            for c in contributions
        ]
        _table(pdf, ["Date", "From", "Type", "Method", "Amount"], rows, [22, 62, 30, 34, 32], {4}, ["Total", "", "", "", money(sum(c["amount"] for c in contributions))])

    return bytes(pdf.output())


def build_general_report_pdf(
    *,
    period_label: str,
    income: list[dict],
    expenses: list[dict],
    income_by_source: list[dict],
    category_label,
    generated_at: datetime,
    budget: list[dict] | None = None,
    income_targets: list[dict] | None = None,
) -> bytes:
    """The general book as a PDF (W15-R17): the three headline figures, income by source, expenses by category, then every income and expense line.
    Only lays out what it is handed; the totals come from the same rows the page shows."""
    generated = generated_at.strftime("%d %b %Y %H:%M")
    pdf = _Report("General accounts", generated)
    pdf.alias_nb_pages()
    pdf.add_page()

    income_total = sum(r["amount"] for r in income)
    expense_total = sum(e["amount"] for e in expenses)
    pdf.set_font("NotoSans", "B", 8)
    pdf.set_text_color(*ACCENT)
    pdf.cell(0, 5, f"{site_name().upper()} · ACCOUNTING REPORT", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Marcellus", "", 22)
    pdf.set_text_color(*INK)
    pdf.cell(0, 9, "General accounts", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("NotoSans", "", 10)
    pdf.set_text_color(*MUTED)
    pdf.cell(0, 5.5, f"{period_label} · generated {generated}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    stats = [("Income", money(income_total), INK), ("Expenses", money(expense_total), INK), ("Net", money(income_total - expense_total), ACCENT)]
    box_w = (CONTENT_W - 2 * 3) / 3
    top = pdf.get_y()
    for i, (label, value, colour) in enumerate(stats):
        x = MARGIN + i * (box_w + 3)
        pdf.set_fill_color(*SUNKEN)
        pdf.set_draw_color(*HAIRLINE)
        pdf.rect(x, top, box_w, 19, style="DF")
        pdf.set_xy(x + 3, top + 3)
        pdf.set_font("NotoSans", "B", 7.5)
        pdf.set_text_color(*MUTED)
        pdf.cell(box_w - 6, 4, label.upper())
        pdf.set_xy(x + 3, top + 9)
        pdf.set_font("NotoSans", "B", 12)
        pdf.set_text_color(*colour)
        pdf.cell(box_w - 6, 7, value)
    pdf.set_fill_color(255, 255, 255)
    pdf.set_y(top + 21)

    _heading(pdf, "Income by source")
    _pairs(pdf, [(f"{s['label']} ({s['count']})", money(s["total"])) for s in income_by_source], "No income in this period.")

    by_category: dict[str, int] = {}
    for e in expenses:
        by_category[e["category"]] = by_category.get(e["category"], 0) + e["amount"]
    _heading(pdf, "Expenses by category")
    _pairs(pdf, [(category_label(c), money(t)) for c, t in sorted(by_category.items(), key=lambda kv: -kv[1])], "No expenses in this period.")

    if budget:
        _heading(pdf, "Budget for the year")
        rows = [[b["label"], money(b["budget"]), money(b["spent"]), money(b["remaining"])] for b in budget]
        _table(
            pdf,
            ["Category", "Budget", "Spent", "Left"],
            rows,
            [70, 36, 36, 38],
            {1, 2, 3},
            ["Total", money(sum(b["budget"] for b in budget)), money(sum(b["spent"] for b in budget)), money(sum(b["remaining"] for b in budget))],
        )

    if income_targets:
        _heading(pdf, "Income targets for the year")
        rows = [[t["label"], money(t["target"]), money(t["received"]), money(t["remaining"])] for t in income_targets]
        _table(
            pdf,
            ["Source", "Target", "Received", "Still to raise"],
            rows,
            [70, 36, 36, 38],
            {1, 2, 3},
            ["Total", money(sum(t["target"] for t in income_targets)), money(sum(t["received"] for t in income_targets)), money(sum(t["remaining"] for t in income_targets))],
        )

    _heading(pdf, "Income")
    if not income:
        _note(pdf, "No income in this period.")
    else:
        rows = [[day(r["date"]), r["source_label"], r.get("name") or "—", r.get("reference") or "—", money(r["amount"])] for r in income]
        _table(pdf, ["Date", "Source", "From", "Reference", "Amount"], rows, [22, 38, 42, 46, 32], {4}, ["Total", "", "", "", money(income_total)])

    _heading(pdf, "Expenses")
    if not expenses:
        _note(pdf, "No expenses in this period.")
    else:
        rows = []
        for e in expenses:
            description = e["description"] + (f"\n{e['notes']}" if e.get("notes") else "")
            rows.append([day(e["date"]), description, category_label(e["category"]), e.get("vendor") or "—", "Yes" if e.get("receipt_key") else "No", money(e["amount"])])
        _table(pdf, ["Date", "Description", "Category", "Vendor", "Receipt", "Amount"], rows, [22, 50, 30, 30, 20, 28], {5}, ["Total", "", "", "", "", money(expense_total)])

    return bytes(pdf.output())
