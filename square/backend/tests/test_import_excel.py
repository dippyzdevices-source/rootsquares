"""Tests for import excel (12 tests), e.g. parse member rows reads the header and data rows; parse member rows skips fully blank rows; validate row accepts a complete valid row."""
from datetime import date
from io import BytesIO

from openpyxl import Workbook, load_workbook

from app.imports.excel import parse_member_rows, validate_row, write_xlsx

HEADER = [
    "name", "email", "phone", "address", "family_info",
    "membership_type", "membership_status", "start_date", "end_date",
]

VALID_TYPES = {"individual", "family", "student", "senior", "lifetime"}


def _workbook_bytes(rows: list[list]) -> bytes:
    wb = Workbook()
    sheet = wb.active
    sheet.append(HEADER)
    for row in rows:
        sheet.append(row)
    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def test_parse_member_rows_reads_the_header_and_data_rows():
    data = _workbook_bytes([
        ["Priya Das", "priya@example.com", "+4712345678", "Oslo", "spouse: Anita",
         "individual", "active", "2026-01-01", None],
    ])

    rows = parse_member_rows(data)

    assert len(rows) == 1
    assert rows[0]["name"] == "Priya Das"
    assert rows[0]["email"] == "priya@example.com"


def test_parse_member_rows_skips_fully_blank_rows():
    data = _workbook_bytes([
        ["Priya Das", "priya@example.com", None, None, None, "individual", "active",
         "2026-01-01", None],
        [None, None, None, None, None, None, None, None, None],
    ])

    rows = parse_member_rows(data)

    assert len(rows) == 1


def test_validate_row_accepts_a_complete_valid_row():
    cleaned, errors = validate_row({
        "name": "Priya Das",
        "email": "priya@example.com",
        "phone": "+4712345678",
        "address": "Oslo",
        "family_info": None,
        "membership_type": "individual",
        "membership_status": "active",
        "start_date": date(2026, 1, 1),
        "end_date": None,
    }, VALID_TYPES)

    assert errors == {}
    assert cleaned["name"] == "Priya Das"
    assert cleaned["email"] == "priya@example.com"
    assert cleaned["start_date"] == "2026-01-01"
    assert cleaned["end_date"] is None


def test_validate_row_requires_name_and_email():
    cleaned, errors = validate_row({"name": None, "email": None}, VALID_TYPES)

    assert "name" in errors
    assert "email" in errors


def test_validate_row_rejects_a_malformed_email():
    cleaned, errors = validate_row({
        "name": "Priya Das", "email": "not-an-email", "membership_type": "individual",
        "start_date": date(2026, 1, 1),
    }, VALID_TYPES)

    assert "email" in errors


def test_validate_row_rejects_an_invalid_membership_type():
    cleaned, errors = validate_row({
        "name": "Priya Das", "email": "priya@example.com", "membership_type": "bogus",
        "start_date": date(2026, 1, 1),
    }, VALID_TYPES)

    assert "membership_type" in errors


def test_validate_row_defaults_membership_status_to_active():
    cleaned, errors = validate_row({
        "name": "Priya Das", "email": "priya@example.com", "membership_type": "individual",
        "start_date": date(2026, 1, 1),
    }, VALID_TYPES)

    assert errors == {}
    assert cleaned["membership_status"] == "active"


def test_validate_row_rejects_an_end_date_before_start_date():
    cleaned, errors = validate_row({
        "name": "Priya Das", "email": "priya@example.com", "membership_type": "individual",
        "start_date": date(2026, 6, 1), "end_date": date(2026, 1, 1),
    }, VALID_TYPES)

    assert "end_date" in errors


def test_validate_row_parses_a_string_date():
    cleaned, errors = validate_row({
        "name": "Priya Das", "email": "priya@example.com", "membership_type": "individual",
        "start_date": "2026-01-01",
    }, VALID_TYPES)

    assert errors == {}
    assert cleaned["start_date"] == "2026-01-01"


def test_validate_row_rejects_an_unparseable_date():
    cleaned, errors = validate_row({
        "name": "Priya Das", "email": "priya@example.com", "membership_type": "individual",
        "start_date": "not-a-date",
    }, VALID_TYPES)

    assert "start_date" in errors


def test_write_xlsx_produces_a_readable_workbook():
    data = write_xlsx(["Name", "Email"], [["Priya Das", "priya@example.com"], ["Rohan", "r@x.com"]])

    workbook = load_workbook(BytesIO(data))
    sheet = workbook.active
    rows = list(sheet.iter_rows(values_only=True))

    assert rows[0] == ("Name", "Email")
    assert rows[1] == ("Priya Das", "priya@example.com")
    assert rows[2] == ("Rohan", "r@x.com")


def test_write_xlsx_never_turns_visitor_text_into_a_formula():
    data = write_xlsx(["Name"], [["=HYPERLINK(\"http://evil.example\",\"x\")"], ["+4799999999"]])
    sheet = load_workbook(BytesIO(data)).active
    assert sheet["A2"].data_type == "s" and sheet["A2"].value.startswith("=")
    assert sheet["A3"].value == "+4799999999"
