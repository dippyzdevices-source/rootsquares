import re
from datetime import date, datetime
from io import BytesIO

from openpyxl import Workbook, load_workbook

from app.memberships.routes import VALID_MEMBERSHIP_STATUSES
from app.memberships.service import is_child_type

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def parse_member_rows(file_bytes: bytes) -> list[dict]:
    """Reads the first worksheet's header row (lowercased column names) and every
    non-blank data row after it into a list of dicts. Performs no validation — see
    validate_row for that.
    """
    workbook = load_workbook(BytesIO(file_bytes), data_only=True)
    sheet = workbook.active
    rows_iter = sheet.iter_rows(values_only=True)
    header_row = next(rows_iter, ())
    header = [str(cell).strip().lower() if cell is not None else "" for cell in header_row]

    rows: list[dict] = []
    for raw_row in rows_iter:
        if all(cell is None for cell in raw_row):
            continue
        rows.append({header[i]: raw_row[i] for i in range(len(header)) if i < len(raw_row)})
    return rows


def _clean_str(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _clean_date(value) -> tuple[date | None, str | None]:
    if value is None:
        return None, None
    if isinstance(value, datetime):
        return value.date(), None
    if isinstance(value, date):
        return value, None
    try:
        return date.fromisoformat(str(value).strip()), None
    except ValueError:
        return None, "Must be a valid date (YYYY-MM-DD)."


def validate_row(row: dict, valid_membership_types: set[str]) -> tuple[dict, dict[str, str]]:
    """Validates one parsed Excel row. Returns (cleaned, errors) — cleaned's date fields are
    ISO strings (JSON-transportable for the preview response), never raw date objects.

    `valid_membership_types` is looked up from the MembershipType table by the caller (never a
    hardcoded set) — see app/memberships/admin_routes.py, which replaced the old constant so an
    admin can add or retire a type without a code change.
    """
    errors: dict[str, str] = {}
    cleaned: dict = {}

    name = _clean_str(row.get("name"))
    if not name:
        errors["name"] = "This field is required."
    else:
        cleaned["name"] = name

    # A row with a parent_email is a child: they may have no email of their own, and their
    # parent is resolved later (preview checks it, confirm links it — see admin_routes.py).
    parent_email = _clean_str(row.get("parent_email"))
    cleaned["parent_email"] = None
    if parent_email:
        if not EMAIL_PATTERN.match(parent_email):
            errors["parent_email"] = "Must be a valid email address."
        else:
            cleaned["parent_email"] = parent_email.lower()

    email = _clean_str(row.get("email"))
    if not email:
        if not parent_email:
            errors["email"] = "This field is required."
        cleaned["email"] = None
    elif not EMAIL_PATTERN.match(email):
        errors["email"] = "Must be a valid email address."
    else:
        cleaned["email"] = email.lower()

    cleaned["phone"] = _clean_str(row.get("phone"))
    cleaned["address"] = _clean_str(row.get("address"))
    cleaned["family_info"] = _clean_str(row.get("family_info"))

    membership_type = _clean_str(row.get("membership_type"))
    if not membership_type:
        errors["membership_type"] = "This field is required."
    elif membership_type not in valid_membership_types:
        errors["membership_type"] = f"Must be one of {sorted(valid_membership_types)}."
    else:
        cleaned["membership_type"] = membership_type

    membership_status = _clean_str(row.get("membership_status")) or "active"
    if membership_status not in VALID_MEMBERSHIP_STATUSES:
        errors["membership_status"] = f"Must be one of {sorted(VALID_MEMBERSHIP_STATUSES)}."
    else:
        cleaned["membership_status"] = membership_status

    start_date, start_error = _clean_date(row.get("start_date"))
    if start_error:
        errors["start_date"] = start_error
    elif start_date is None:
        errors["start_date"] = "This field is required."
    else:
        cleaned["start_date"] = start_date.isoformat()

    end_date, end_error = _clean_date(row.get("end_date"))
    if end_error:
        errors["end_date"] = end_error
    else:
        cleaned["end_date"] = end_date.isoformat() if end_date else None

    if membership_type and "membership_type" not in errors:
        if parent_email and not is_child_type(membership_type):
            errors["membership_type"] = "A row with a parent_email must have membership_type child."
        elif is_child_type(membership_type) and not parent_email:
            errors["parent_email"] = "A child row needs the parent's email."

    if not errors and cleaned.get("end_date") and cleaned["end_date"] < cleaned["start_date"]:
        errors["end_date"] = "Must not be before start_date."

    return cleaned, errors


def write_xlsx(headers: list[str], rows: list[list]) -> bytes:
    """Builds a single-sheet .xlsx file (header row + data rows) and returns its bytes —
    shared by every admin export endpoint (members, orders, payments).
    """
    return write_xlsx_sheets([("Sheet", headers, rows)])


def write_xlsx_sheets(sheets: list[tuple[str, list[str], list[list]]]) -> bytes:
    """Builds a multi-sheet .xlsx file from (sheet name, header row, data rows) tuples and returns
    its bytes — used where one download needs more than one table (e.g. the per-event buyers
    export: one sheet per order, one per ticket)."""
    workbook = Workbook()
    workbook.remove(workbook.active)
    for name, headers, rows in sheets:
        sheet = workbook.create_sheet(title=name)
        sheet.append(headers)
        for row in rows:
            sheet.append(row)
            for cell in sheet[sheet.max_row]:
                if cell.data_type == "f":  # text typed by a visitor (a name, a message) must never run as a spreadsheet formula
                    cell.data_type = "s"
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
