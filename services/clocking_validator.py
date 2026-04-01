"""Field-level validation helpers for ClockingApp."""
import datetime
from typing import Tuple, Optional


def validate_date_format(date_str: str) -> bool:
    """Return True if date_str is a valid YYYY-MM-DD date."""
    try:
        datetime.datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def validate_time_format(time_str: str) -> bool:
    """Return True if time_str is a valid HH:MM time."""
    try:
        datetime.datetime.strptime(time_str, "%H:%M")
        return True
    except ValueError:
        return False


def validate_message_format(message_str: str) -> bool:
    """
    Return True if message_str is acceptable.

    Rules:
    - Empty strings are allowed.
    - Maximum 500 characters.
    - No control characters except tab, newline, carriage return.
    - Balanced double quotes (even count).
    """
    if not message_str:
        return True

    if len(message_str) > 500:
        return False

    for char in message_str:
        if ord(char) < 32 and char not in ('\t', '\n', '\r'):
            return False
        if ord(char) == 127:
            return False

    if message_str.count('"') % 2 != 0:
        return False

    return True
