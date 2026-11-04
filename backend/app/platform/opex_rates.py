"""Exchange rates for showing the costs in another currency (W16-R9 phase 4). Display only: every stored amount stays in US dollars.

Rates come from Frankfurter (the European Central Bank's daily rates, free, no key) when the owner presses Refresh, never in the background, and are kept
as platform settings ("rate|date|source") so the page works offline. A rate can also be typed by hand. An indication is enough, not accounting.
"""

from __future__ import annotations

import datetime as dt

import httpx
from sqlalchemy.orm import Session

from app.platform.models import PlatformSetting

CURRENCIES = ("NOK", "INR")
URL = "https://api.frankfurter.dev/v1/latest"


class RatesUnavailableError(Exception):
    """Frankfurter could not be reached or answered something unexpected."""


def fetch_rates() -> tuple[dict[str, float], str]:
    """The USD rates of the supported currencies and the day they are for. Only this function touches the network."""
    try:
        r = httpx.get(URL, params={"base": "USD", "symbols": ",".join(CURRENCIES)}, timeout=8.0)
        r.raise_for_status()
        body = r.json()
        rates = {c: float(body["rates"][c]) for c in CURRENCIES}
        return rates, str(body["date"])
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        raise RatesUnavailableError("The rate service did not answer") from exc


def _key(code: str) -> str:
    return f"opex.rate.{code}"


def load(db: Session) -> dict[str, dict[str, object]]:
    out: dict[str, dict[str, object]] = {}
    for code in CURRENCIES:
        row = db.get(PlatformSetting, _key(code))
        if row is None:
            continue
        rate, _, rest = row.value.partition("|")
        day, _, source = rest.partition("|")
        out[code] = {"rate": float(rate), "date": day, "source": source or "frankfurter"}
    return out


def save(db: Session, code: str, rate: float, day: str, source: str) -> None:
    value = f"{rate!r}|{day}|{source}"
    row = db.get(PlatformSetting, _key(code))
    if row is None:
        db.add(PlatformSetting(key=_key(code), value=value))
    else:
        row.value = value


def refresh(db: Session) -> None:
    rates, day = fetch_rates()
    for code, rate in rates.items():
        save(db, code, rate, day, "frankfurter")


def today() -> str:
    return dt.date.today().isoformat()
