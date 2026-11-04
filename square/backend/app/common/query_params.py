"""Multi-value filter parameters. A dropdown filter that allows several choices sends them comma-separated
(`?payment_method=cash,vipps_qr`); an empty or missing parameter means "no filter"."""

from flask import request


def csv_arg(name: str) -> list[str]:
    """The non-empty, de-duplicated values of a comma-separated query parameter, in the order given."""
    values: list[str] = []
    for part in (request.args.get(name) or "").split(","):
        part = part.strip()
        if part and part not in values:
            values.append(part)
    return values


def csv_int_arg(name: str) -> list[int]:
    """Like csv_arg, for ids; anything that is not a whole number is ignored."""
    out: list[int] = []
    for part in csv_arg(name):
        try:
            number = int(part)
        except ValueError:
            continue
        if number not in out:
            out.append(number)
    return out
