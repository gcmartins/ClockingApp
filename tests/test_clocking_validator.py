"""Tests for field-level validation helpers (services/clocking_validator.py)."""

from services.clocking_validator import (
    validate_date_format,
    validate_message_format,
    validate_time_format,
)


class TestDateValidation:
    def test_valid_date_formats(self):
        valid_dates = ["2024-01-01", "2024-12-31", "2023-06-15", "2025-02-28"]
        for date_str in valid_dates:
            assert validate_date_format(date_str) is True, f"Date {date_str} should be valid"

    def test_invalid_date_formats(self):
        invalid_dates = [
            "2024/01/01",
            "01-01-2024",
            "2024-13-01",
            "2024-01-32",
            "24-01-01",
            "not-a-date",
            "",
            "2024-02-30",
        ]
        for date_str in invalid_dates:
            assert validate_date_format(date_str) is False, f"Date {date_str} should be invalid"


class TestTimeValidation:
    def test_valid_time_formats(self):
        valid_times = ["00:00", "08:30", "12:00", "17:45", "23:59"]
        for time_str in valid_times:
            assert validate_time_format(time_str) is True, f"Time {time_str} should be valid"

    def test_invalid_time_formats(self):
        invalid_times = [
            "24:00",
            "12:60",
            "08-30",
            "not-a-time",
            "",
            "25:00",
        ]
        for time_str in invalid_times:
            assert validate_time_format(time_str) is False, f"Time {time_str} should be invalid"


class TestMessageValidation:
    def test_valid_messages(self):
        valid_messages = [
            "",
            "Normal message",
            "Message with numbers 123",
            "Message with, comma and \"quotes\"",
            "A" * 500,
            "Message with\ttab",
            "Message with\nnewline",
            "Message with ''multiple'' 'balanced' quotes",
        ]
        for msg in valid_messages:
            assert validate_message_format(msg) is True, f"Message '{msg[:50]}' should be valid"

    def test_invalid_messages(self):
        invalid_messages = [
            "A" * 501,
            "Message with\x00null character",
            "Message with\x01control character",
            "Message with\x7fDEL character",
            "Message with\x08backspace",
            "Message with unbalanced \"quote",
            "Multiple \"unbalanced\" quotes\"",
        ]
        for msg in invalid_messages:
            assert validate_message_format(msg) is False, "Message should be invalid"
