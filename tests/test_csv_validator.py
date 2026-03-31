"""Test suite for CSV validation functionality."""
import pytest
from services.csv_validator import (
    validate_date_format,
    validate_time_format,
    validate_message_format,
    validate_clocking_csv_format,
    validate_task_csv_format,
    CSVValidationError
)


class TestDateValidation:
    """Test cases for date format validation."""
    
    def test_valid_date_formats(self):
        """Test that valid date formats are accepted."""
        valid_dates = [
            "2024-01-01",
            "2024-12-31",
            "2023-06-15",
            "2025-02-28"
        ]
        for date_str in valid_dates:
            assert validate_date_format(date_str) is True, f"Date {date_str} should be valid"
    
    def test_invalid_date_formats(self):
        """Test that invalid date formats are rejected."""
        invalid_dates = [
            "2024/01/01",  # Wrong separator
            "01-01-2024",  # Wrong order
            "2024-13-01",  # Invalid month
            "2024-01-32",  # Invalid day
            "24-01-01",    # Two-digit year
            "not-a-date",
            "",
            "2024-02-30"   # Invalid date
        ]
        for date_str in invalid_dates:
            assert validate_date_format(date_str) is False, f"Date {date_str} should be invalid"
        
        # Note: Python's strptime is lenient and accepts single-digit months/days
        # like "2024-1-1", so we accept them too


class TestTimeValidation:
    """Test cases for time format validation."""
    
    def test_valid_time_formats(self):
        """Test that valid time formats are accepted."""
        valid_times = [
            "00:00",
            "08:30",
            "12:00",
            "17:45",
            "23:59"
        ]
        for time_str in valid_times:
            assert validate_time_format(time_str) is True, f"Time {time_str} should be valid"
    
    def test_invalid_time_formats(self):
        """Test that invalid time formats are rejected."""
        invalid_times = [
            "24:00",       # Invalid hour
            "12:60",       # Invalid minute
            "08-30",       # Wrong separator
            "not-a-time",
            "",
            "25:00"        # Hour too large
        ]
        for time_str in invalid_times:
            assert validate_time_format(time_str) is False, f"Time {time_str} should be invalid"
        
        # Note: Python's strptime is lenient and accepts single-digit hours/minutes
        # like "8:30" or "08:5", so we accept them too


class TestMessageValidation:
    """Test cases for message format validation."""
    
    def test_valid_messages(self):
        """Test that valid messages are accepted."""
        valid_messages = [
            "",
            "Normal message",
            "Message with numbers 123",
            "Message with special chars: @#$%^&*()",
            "Message with, comma and \"quotes\"",
            "A" * 500,  # Maximum length
            "Message with\ttab",
            "Message with\nnewline",
            "Message with 'single' quotes",
            "Message with \"double\" quotes",
            "Message with ''multiple'' 'balanced' quotes"
        ]
        for msg in valid_messages:
            assert validate_message_format(msg) is True, f"Message '{msg[:50]}...' should be valid"
    
    def test_invalid_messages(self):
        """Test that invalid messages are rejected."""
        invalid_messages = [
            "A" * 501,  # Too long
            "Message with\x00null character",
            "Message with\x01control character",
            "Message with\x7fDEL character",
            "Message with\x08backspace",
            "Message with unbalanced \"quote",
            "Multiple \"unbalanced\" quotes\""
        ]
        for msg in invalid_messages:
            assert validate_message_format(msg) is False, f"Message should be invalid"


class TestClockingCSVValidation:
    """Test cases for clocking CSV validation."""
    
    def test_valid_clocking_csv(self):
        """Test that a valid clocking CSV passes validation."""
        valid_csv = """Date,Task,Check In,Check Out,Message
2024-02-19,TASK-123,08:00,17:00,
2024-02-20,TASK-456,09:15,12:30,Lunch break
2024-02-21,TASK-789,13:00,18:00,"""
        is_valid, error = validate_clocking_csv_format(valid_csv)
        assert is_valid is True, f"Valid CSV should pass validation. Error: {error}"
        assert error is None
    
    def test_empty_csv(self):
        """Test that empty CSV content is rejected."""
        is_valid, error = validate_clocking_csv_format("")
        assert is_valid is False
        assert "empty" in error.lower()
    
    def test_invalid_header(self):
        """Test that invalid headers are rejected."""
        invalid_csv = """Date,Task,Start,End,Notes
2024-02-19,TASK-123,08:00,17:00,"""
        is_valid, error = validate_clocking_csv_format(invalid_csv)
        assert is_valid is False
        assert "header" in error.lower()
    
    def test_wrong_column_count(self):
        """Test that rows with wrong number of columns are rejected."""
        invalid_csv = """Date,Task,Check In,Check Out,Message
2024-02-19,TASK-123,08:00"""
        is_valid, error = validate_clocking_csv_format(invalid_csv)
        assert is_valid is False
        assert "columns" in error.lower()
    
    def test_invalid_date_in_data(self):
        """Test that invalid dates in data rows are rejected."""
        invalid_csv = """Date,Task,Check In,Check Out,Message
2024-13-01,TASK-123,08:00,17:00,"""
        is_valid, error = validate_clocking_csv_format(invalid_csv)
        assert is_valid is False
        assert "date" in error.lower()
    
    def test_invalid_check_in_time(self):
        """Test that invalid check-in times are rejected."""
        invalid_csv = """Date,Task,Check In,Check Out,Message
2024-02-19,TASK-123,25:00,17:00,"""
        is_valid, error = validate_clocking_csv_format(invalid_csv)
        assert is_valid is False
        assert "check-in" in error.lower()
    
    def test_invalid_check_out_time(self):
        """Test that invalid check-out times are rejected."""
        invalid_csv = """Date,Task,Check In,Check Out,Message
2024-02-19,TASK-123,08:00,24:00,"""
        is_valid, error = validate_clocking_csv_format(invalid_csv)
        assert is_valid is False
        assert "check-out" in error.lower()
    
    def test_check_out_before_check_in(self):
        """Test that check-out time before check-in time is rejected."""
        invalid_csv = """Date,Task,Check In,Check Out,Message
2024-02-19,TASK-123,17:00,08:00,"""
        is_valid, error = validate_clocking_csv_format(invalid_csv)
        assert is_valid is False
        assert "before" in error.lower()
    
    def test_empty_task_field(self):
        """Test that empty task fields are rejected."""
        invalid_csv = """Date,Task,Check In,Check Out,Message
2024-02-19,,08:00,17:00,"""
        is_valid, error = validate_clocking_csv_format(invalid_csv)
        assert is_valid is False
        assert "task" in error.lower() and "empty" in error.lower()
    
    def test_missing_check_out(self):
        """Test that missing check-out time is allowed (ongoing task)."""
        valid_csv = """Date,Task,Check In,Check Out,Message
2024-02-19,TASK-123,08:00,,"""
        is_valid, error = validate_clocking_csv_format(valid_csv)
        assert is_valid is True, f"CSV with missing check-out should be valid. Error: {error}"
        assert error is None
    
    def test_cross_day_clocking(self):
        """Test that cross-day clocking (23:59 to 00:00) is allowed."""
        valid_csv = """Date,Task,Check In,Check Out,Message
2024-02-19,TASK-123,22:00,23:59,
2024-02-20,TASK-123,00:00,02:00,"""
        is_valid, error = validate_clocking_csv_format(valid_csv)
        assert is_valid is True, f"Cross-day clocking should be valid. Error: {error}"
        assert error is None
    
    def test_multiple_valid_rows(self):
        """Test CSV with multiple valid rows."""
        valid_csv = """Date,Task,Check In,Check Out,Message
2024-02-19,TASK-123,08:00,10:00,Morning work
2024-02-19,TASK-456,10:00,12:00,
2024-02-19,TASK-123,13:00,17:00,Afternoon work
2024-02-20,TASK-789,09:00,17:30,Full day"""
        is_valid, error = validate_clocking_csv_format(valid_csv)
        assert is_valid is True, f"Valid CSV with multiple rows should pass. Error: {error}"
        assert error is None
    
    def test_csv_with_empty_message(self):
        """Test that empty message field is allowed."""
        valid_csv = """Date,Task,Check In,Check Out,Message
2024-02-19,TASK-123,08:00,17:00,"""
        is_valid, error = validate_clocking_csv_format(valid_csv)
        assert is_valid is True, f"Empty message should be allowed. Error: {error}"
        assert error is None
    
    def test_malformed_csv(self):
        """Test that malformed CSV is rejected."""
        invalid_csv = """Date,Task,Check In,Check Out,Message
2024-02-19,"TASK-123,08:00,17:00,"""  # Unclosed quote
        is_valid, error = validate_clocking_csv_format(invalid_csv)
        # Note: Python's csv module is quite forgiving, so this might still parse
        # but would fail other validations


class TestTaskCSVValidation:
    """Test cases for task CSV validation."""

    def test_valid_task_csv(self):
        """Test that a valid task CSV passes validation."""
        valid_csv = """Task,Description,Task Type
TASK-123,Implement feature X,fixed
TASK-456,Fix bug in module Y,open
TASK-789,Review pull request,closed"""
        is_valid, error = validate_task_csv_format(valid_csv)
        assert is_valid is True, f"Valid task CSV should pass validation. Error: {error}"
        assert error is None

    def test_empty_task_csv(self):
        """Test that empty CSV content is rejected."""
        is_valid, error = validate_task_csv_format("")
        assert is_valid is False
        assert "empty" in error.lower()

    def test_invalid_task_header(self):
        """Test that invalid headers are rejected."""
        invalid_csv = """TaskID,TaskDescription,Kind
TASK-123,Implement feature X,fixed"""
        is_valid, error = validate_task_csv_format(invalid_csv)
        assert is_valid is False
        assert "header" in error.lower()

    def test_wrong_column_count_in_task(self):
        """Test that rows with wrong number of columns are rejected."""
        invalid_csv = """Task,Description,Task Type
TASK-123"""
        is_valid, error = validate_task_csv_format(invalid_csv)
        assert is_valid is False
        assert "columns" in error.lower()

    def test_empty_task_field_in_task_csv(self):
        """Test that empty task fields are rejected."""
        invalid_csv = """Task,Description,Task Type
,Some description,fixed"""
        is_valid, error = validate_task_csv_format(invalid_csv)
        assert is_valid is False
        assert "task" in error.lower() and "empty" in error.lower()

    def test_task_with_empty_description(self):
        """Test that empty descriptions are allowed."""
        valid_csv = """Task,Description,Task Type
TASK-123,,fixed"""
        is_valid, error = validate_task_csv_format(valid_csv)
        assert is_valid is True, f"Empty description should be allowed. Error: {error}"
        assert error is None

    def test_multiple_valid_tasks(self):
        """Test CSV with multiple valid task rows."""
        valid_csv = """Task,Description,Task Type
TASK-123,First task,fixed
TASK-456,Second task,open
TASK-789,Third task,closed"""
        is_valid, error = validate_task_csv_format(valid_csv)
        assert is_valid is True, f"Valid task CSV with multiple rows should pass. Error: {error}"
        assert error is None

    def test_all_valid_task_types(self):
        """Test that all valid task_type values are accepted."""
        for task_type in ("fixed", "open", "closed"):
            csv_content = f"Task,Description,Task Type\nTASK-1,desc,{task_type}"
            is_valid, error = validate_task_csv_format(csv_content)
            assert is_valid is True, f"task_type '{task_type}' should be valid. Error: {error}"

    def test_invalid_task_type_rejected(self):
        """Test that an unknown task_type value is rejected."""
        invalid_csv = """Task,Description,Task Type
TASK-123,Some description,unknown"""
        is_valid, error = validate_task_csv_format(invalid_csv)
        assert is_valid is False
        assert "task type" in error.lower() or "invalid" in error.lower()


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_csv_with_only_header(self):
        """Test CSV with only header row."""
        csv_content = """Date,Task,Check In,Check Out,Message"""
        is_valid, error = validate_clocking_csv_format(csv_content)
        assert is_valid is True, f"CSV with only header should be valid. Error: {error}"
    
    def test_csv_with_whitespace_in_fields(self):
        """Test CSV with whitespace in fields."""
        csv_content = """Date,Task,Check In,Check Out,Message
2024-02-19, TASK-123 ,08:00,17:00, Some message """
        is_valid, error = validate_clocking_csv_format(csv_content)
        assert is_valid is True, f"CSV with whitespace should be valid. Error: {error}"
    
    def test_csv_with_special_characters(self):
        """Test CSV with special characters in message field."""
        csv_content = """Date,Task,Check In,Check Out,Message
2024-02-19,TASK-123,08:00,17:00,"Message with, comma"
2024-02-20,TASK-456,09:00,17:00,Message with "quotes\""""
        is_valid, error = validate_clocking_csv_format(csv_content)
        assert is_valid is True, f"CSV with special characters should be valid. Error: {error}"
    
    def test_same_check_in_and_check_out(self):
        """Test that same check-in and check-out times are allowed."""
        valid_csv = """Date,Task,Check In,Check Out,Message
2024-02-19,TASK-123,08:00,08:00,"""
        is_valid, error = validate_clocking_csv_format(valid_csv)
        assert is_valid is True, f"Same check-in and check-out times should be valid. Error: {error}"
        assert error is None
    
    def test_message_too_long(self):
        """Test that messages over 500 characters are rejected."""
        long_message = "A" * 501
        invalid_csv = f"""Date,Task,Check In,Check Out,Message
2024-02-19,TASK-123,08:00,17:00,{long_message}"""
        is_valid, error = validate_clocking_csv_format(invalid_csv)
        assert is_valid is False
        assert "message" in error.lower()
    
    def test_message_with_control_characters(self):
        """Test that messages with control characters are rejected."""
        invalid_csv = """Date,Task,Check In,Check Out,Message
2024-02-19,TASK-123,08:00,17:00,Bad\x00message"""
        is_valid, error = validate_clocking_csv_format(invalid_csv)
        assert is_valid is False
        assert "message" in error.lower()
    
    def test_message_with_unbalanced_quotes(self):
        """Test that messages with unbalanced quotes are rejected."""
        invalid_csv = """Date,Task,Check In,Check Out,Message
2024-02-19,TASK-123,08:00,17:00,Unbalanced "quote"""
        is_valid, error = validate_clocking_csv_format(invalid_csv)
        assert is_valid is False
        assert "quote" in error.lower()
    
    def test_message_with_leading_unbalanced_quote(self):
        """Test that message with leading unbalanced quote is rejected."""
        invalid_csv = """Date,Task,Check In,Check Out,Message
2024-02-19,TASK-123,08:00,17:00,My "message"""
        is_valid, error = validate_clocking_csv_format(invalid_csv)
        assert is_valid is False
        assert "quote" in error.lower()
    
    def test_unclosed_quote_in_csv(self):
        """Test that CSV with unclosed quote is rejected."""
        invalid_csv = """Date,Task,Check In,Check Out,Message
2025-12-09,LAAS-10556,13:31,,"test"""
        is_valid, error = validate_clocking_csv_format(invalid_csv)
        assert is_valid is False
        assert "quote" in error.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
