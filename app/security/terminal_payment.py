from __future__ import annotations
import re


def validate_terminal_payment_fields(card_number, expiry_month, expiry_year, cvv, cardholder_name, card_type):
    """Validate masked terminal input and return a normalized in-memory payload."""
    card_number = re.sub(r"\D", "", str(card_number))
    expiry_month = str(expiry_month).strip()
    expiry_year = str(expiry_year).strip()
    cvv = str(cvv).strip()
    cardholder_name = str(cardholder_name).strip()
    card_type = str(card_type).strip()

    if not 12 <= len(card_number) <= 19 or not card_number.isdigit():
        raise ValueError("Test card number must contain 12–19 digits.")
    if not re.fullmatch(r"\d{1,2}", expiry_month) or not 1 <= int(expiry_month) <= 12:
        raise ValueError("Expiry month must be between 1 and 12.")
    if not re.fullmatch(r"\d{2}|\d{4}", expiry_year):
        raise ValueError("Expiry year must contain 2 or 4 digits.")
    if not re.fullmatch(r"\d{3,4}", cvv):
        raise ValueError("Test CVV must contain 3 or 4 digits.")
    if not cardholder_name or not card_type:
        raise ValueError("Cardholder name and card type are required.")

    return {
        "card_number": card_number,
        "expiry_month": expiry_month.zfill(2),
        "expiry_year": expiry_year,
        "cvv": cvv,
        "cardholder_name": cardholder_name,
        "card_type": card_type,
    }
