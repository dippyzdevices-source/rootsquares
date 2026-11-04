"""The square's own bank details as shown to a payer (donations, tickets, memberships). Each field is optional; an empty one is left out of the page (rule 11)."""


def bank_details(settings) -> dict:
    fields = {
        "holder": settings.bank_account_holder,
        "bank_name": settings.bank_name,
        "account_number": settings.bank_account_number,
        "iban": settings.bank_iban,
        "bic": settings.bank_bic,
        "note": settings.bank_transfer_note,
    }
    return {key: (value or "").strip() for key, value in fields.items()}
