import pytest

from app.security.terminal_payment import validate_terminal_payment_fields


def test_terminal_payment_validation_normalizes_masked_input():
    payload = validate_terminal_payment_fields(
        "1111 1111 1111 1111", "3", "30", "123", "Demo Enroll", "Visa"
    )
    assert payload == {
        "card_number": "1111111111111111",
        "expiry_month": "03",
        "expiry_year": "30",
        "cvv": "123",
        "cardholder_name": "Demo Enroll",
        "card_type": "Visa",
    }


@pytest.mark.parametrize(
    "values",
    [
        ("123", "12", "30", "123", "Demo", "Visa"),
        ("1111111111111111", "13", "30", "123", "Demo", "Visa"),
        ("1111111111111111", "12", "30", "12", "Demo", "Visa"),
        ("1111111111111111", "12", "30", "123", "", "Visa"),
    ],
)
def test_terminal_payment_validation_rejects_invalid_input(values):
    with pytest.raises(ValueError):
        validate_terminal_payment_fields(*values)
