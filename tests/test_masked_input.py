from io import StringIO

from app.security.masked_input import read_masked_input


def test_masked_input_prints_stars_and_returns_value():
    chars = iter("abc\r")
    output = StringIO()

    value = read_masked_input("Secret: ", char_reader=lambda: next(chars), output=output)

    assert value == "abc"
    assert output.getvalue() == "Secret: ***\n"


def test_masked_input_backspace_removes_one_mask():
    chars = iter("ab\x08c\n")
    output = StringIO()

    value = read_masked_input("Secret: ", char_reader=lambda: next(chars), output=output)

    assert value == "ac"
    assert output.getvalue() == "Secret: **\b \b*\n"
