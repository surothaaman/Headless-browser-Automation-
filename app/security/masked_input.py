"""Terminal input helpers for payment data.

The standard :mod:`getpass` implementation deliberately shows no characters.
This module keeps input hidden while displaying one ``*`` per character.
"""

from __future__ import annotations

import os
import sys
from typing import Callable, TextIO


def _read_character() -> str:
    """Read one character without echoing it, on Windows or POSIX."""
    if os.name == "nt":
        import msvcrt

        value = msvcrt.getwch()
        if value in ("\x00", "\xe0"):
            msvcrt.getwch()  # consume an extended-key suffix
            return ""
        return value

    import termios
    import tty

    stream = sys.stdin
    if not hasattr(stream, "fileno"):
        return stream.read(1)
    fd = stream.fileno()
    previous = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        return stream.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, previous)


def read_masked_input(
    prompt: str,
    *,
    char_reader: Callable[[], str] | None = None,
    output: TextIO | None = None,
) -> str:
    """Read a line while displaying ``*`` for each entered character.

    Backspace removes the last mask and character. Enter submits the value.
    ``char_reader`` and ``output`` are injectable so this behavior can be
    tested without a real terminal.
    """
    reader = char_reader or _read_character
    stream = output or sys.stdout
    stream.write(prompt)
    stream.flush()
    chars: list[str] = []
    while True:
        char = reader()
        if char in ("\r", "\n", ""):
            stream.write("\n")
            stream.flush()
            return "".join(chars)
        if char in ("\x03",):
            raise KeyboardInterrupt
        if char in ("\x08", "\x7f"):
            if chars:
                chars.pop()
                stream.write("\b \b")
                stream.flush()
            continue
        if char.isprintable():
            chars.append(char)
            stream.write("*")
            stream.flush()
