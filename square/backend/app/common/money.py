"""Money text for a site's currency (rootsquares W6-R47). Amounts are integers in minor units (øre, cents); bca-oslo printed everything as "kr"."""

KRONE_CURRENCIES = {"NOK", "SEK", "DKK", "ISK"}  # written "250.00 kr"
SYMBOLS = {"EUR": "€", "GBP": "£", "USD": "$"}  # written "€250.00"


def format_money(minor_units: int | None, currency: str = "NOK", *, whole_if_round: bool = False) -> str:
    amount = (minor_units or 0) / 100
    text = f"{amount:,.0f}".replace(",", " ") if whole_if_round and (minor_units or 0) % 100 == 0 else f"{amount:.2f}"
    if currency in KRONE_CURRENCIES:
        return f"{text} kr"
    if currency in SYMBOLS:
        return f"{SYMBOLS[currency]}{text}"
    return f"{text} {currency}"
