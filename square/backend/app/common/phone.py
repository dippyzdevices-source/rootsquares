"""Phone number rule of a square (rootsquares W6-R52). bca-oslo accepted only Norwegian mobile numbers (8 digits, optional +47).

A square has a country (platform `squares.phone_country`, chosen when the square is created, default NO). A country has a calling code, the length
range of the number without that code, and whether a leading trunk zero is written ("07700 900123" in the UK). The browser gets the rule from
/api/square/config, so the forms and this module cannot disagree.
"""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class PhoneRule:
    country: str
    name: str
    dial: str  # calling code without "+"
    min_digits: int  # national number, without the calling code and the trunk zero
    max_digits: int
    trunk_zero: bool = False

    def public(self) -> dict:
        return {"country": self.country, "name": self.name, "dial": self.dial, "min_digits": self.min_digits, "max_digits": self.max_digits, "trunk_zero": self.trunk_zero}

    def message(self) -> str:
        length = str(self.min_digits) if self.min_digits == self.max_digits else f"{self.min_digits} to {self.max_digits}"
        return f"Enter a valid phone number for {self.name} (+{self.dial}, {length} digits)."


_RULES = (
    PhoneRule("NO", "Norway", "47", 8, 8),
    PhoneRule("SE", "Sweden", "46", 7, 10, True),
    PhoneRule("DK", "Denmark", "45", 8, 8),
    PhoneRule("FI", "Finland", "358", 5, 11, True),
    PhoneRule("IS", "Iceland", "354", 7, 7),
    PhoneRule("DE", "Germany", "49", 7, 12, True),
    PhoneRule("GB", "United Kingdom", "44", 9, 10, True),
    PhoneRule("IE", "Ireland", "353", 7, 9, True),
    PhoneRule("NL", "Netherlands", "31", 9, 9, True),
    PhoneRule("FR", "France", "33", 9, 9, True),
    PhoneRule("US", "United States", "1", 10, 10),
    PhoneRule("CA", "Canada", "1", 10, 10),
    PhoneRule("IN", "India", "91", 10, 10, True),
    PhoneRule("BD", "Bangladesh", "880", 10, 10, True),
)
RULES = {r.country: r for r in _RULES}
SUPPORTED_COUNTRIES = tuple(RULES)
DEFAULT_COUNTRY = "NO"


def phone_rule(country: str | None) -> PhoneRule:
    """The rule of a country code; anything unknown or missing counts as Norway (bca-oslo's own rule)."""
    return RULES.get((country or DEFAULT_COUNTRY).upper(), RULES[DEFAULT_COUNTRY])


def is_valid_phone(phone: str, rule: PhoneRule) -> bool:
    text = phone.strip()
    digits = re.sub(r"\D", "", text)
    if text.startswith("+"):
        if not digits.startswith(rule.dial):
            return False
        digits = digits[len(rule.dial):]
    elif digits.startswith("00" + rule.dial):
        digits = digits[2 + len(rule.dial):]
    elif digits.startswith(rule.dial) and len(digits) == len(rule.dial) + rule.max_digits and rule.min_digits == rule.max_digits:
        digits = digits[len(rule.dial):]  # "4712345678": the code written without + (as bca-oslo accepted)
    if rule.trunk_zero and digits.startswith("0"):
        digits = digits[1:]
    return rule.min_digits <= len(digits) <= rule.max_digits
