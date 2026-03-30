"""CSV validation utilities for ClockingApp."""
import csv
import datetime
import io
from typing import List, Tuple, Optional

from services.constants import CLOCKING_HEADER, TASK_HEADER


class CSVValidationError(Exception):
    """Exception raised when CSV validation fails."""
    pass


def validate_date_format(date_str: str) -> bool:
    """
    Validate date format (YYYY-MM-DD).
    
    Args:
        date_str: String to validate as a date
        
    Returns:
        True if valid date format, False otherwise
    """
    try:
        datetime.datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def validate_time_format(time_str: str) -> bool:
    """
    Validate time format (HH:MM).
    
    Args:
        time_str: String to validate as a time
        
    Returns:
        True if valid time format, False otherwise
    """
    try:
        datetime.datetime.strptime(time_str, "%H:%M")
        return True
    except ValueError:
        return False


def validate_message_format(message_str: str) -> bool:
    """
    Validate message string format.
    
    Validates:
    - No control characters (except tab, newline, carriage return)
    - Maximum length of 500 characters
    - Printable characters only
    - Balanced double quotes
    
    Args:
        message_str: String to validate as a message
        
    Returns:
        True if valid message format, False otherwise
    """
    if not message_str:
        return True  # Empty messages are allowed
    
    # Check maximum length
    if len(message_str) > 500:
        return False
    
    # Check for invalid control characters
    for char in message_str:
        # Allow printable characters, tab, newline, and carriage return
        if ord(char) < 32 and char not in ('\t', '\n', '\r'):
            return False
        # Disallow certain special control characters
        if ord(char) == 127:  # DEL character
            return False
    
    # Check for balanced quotes
    double_quote_count = message_str.count('"')
    
    # Quotes must be balanced (even number)
    if double_quote_count % 2 != 0:
        return False
    
    return True


def validate_clocking_csv_format(csv_content: str) -> Tuple[bool, Optional[str]]:
    """
    Validate the format of the clocking CSV content.
    
    Validates:
    - CSV can be parsed
    - Header matches expected format
    - Each row has correct number of columns
    - Date column contains valid dates
    - Time columns contain valid times or are empty
    - Check Out time is after Check In time (when both present)
    - No unclosed quotes or malformed CSV syntax
    
    Args:
        csv_content: The CSV content as a string
        
    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if validation passes, False otherwise
        - error_message: None if valid, error description if invalid
    """
    if not csv_content or csv_content.strip() == '':
        return False, "CSV content is empty"
    
    # Check for unclosed quotes by counting quotes in each line
    for line_num, line in enumerate(csv_content.split('\n'), start=1):
        if not line.strip():
            continue
        # Count quotes that are not escaped
        quote_count = line.count('"')
        # In valid CSV, quotes should be balanced (even number) in each line
        # unless a field spans multiple lines (which we don't support here)
        if quote_count % 2 != 0:
            return False, f"Line {line_num}: Unclosed quote detected. CSV syntax error"
    
    try:
        # Parse CSV
        csv_reader = csv.reader(io.StringIO(csv_content))
        rows = list(csv_reader)
        
        if len(rows) == 0:
            return False, "CSV has no rows"
        
        # Validate header
        header = rows[0]
        if header != CLOCKING_HEADER:
            return False, f"Invalid header. Expected {CLOCKING_HEADER}, got {header}"
        
        # Validate data rows
        for row_num, row in enumerate(rows[1:], start=2):
            # Skip empty rows
            if not any(row):
                continue
                
            # Check column count
            if len(row) != len(CLOCKING_HEADER):
                return False, f"Row {row_num}: Expected {len(CLOCKING_HEADER)} columns, got {len(row)}"
            
            date_str, task, check_in, check_out, message = row
            
            # Validate date (must be present and valid)
            if not date_str:
                return False, f"Row {row_num}: Date field is empty"
            if not validate_date_format(date_str):
                return False, f"Row {row_num}: Invalid date format '{date_str}'. Expected YYYY-MM-DD"

            # Validate task (should not be empty)
            if not task or task.strip() == '':
                return False, f"Row {row_num}: Task field is empty"

            # Validate check in time (must be present)
            if not check_in:
                return False, f"Row {row_num}: Check-in time is missing"
            if not validate_time_format(check_in):
                return False, f"Row {row_num}: Invalid check-in time format '{check_in}'. Expected HH:MM"

            # Validate check out time
            if check_out and not validate_time_format(check_out):
                return False, f"Row {row_num}: Invalid check-out time format '{check_out}'. Expected HH:MM"

            # Validate that check out is not before check in (if both present)
            if check_in and check_out:
                check_in_dt = datetime.datetime.strptime(check_in, "%H:%M")
                check_out_dt = datetime.datetime.strptime(check_out, "%H:%M")
                if check_out_dt < check_in_dt:
                    return False, f"Row {row_num}: Check-out time '{check_out}' cannot be before check-in time '{check_in}'"
            
            # Validate message format
            if not validate_message_format(message):
                return False, f"Row {row_num}: Invalid message format. Message must be under 500 characters and contain only valid printable characters"
        
        return True, None
        
    except csv.Error as e:
        return False, f"CSV parsing error: {str(e)}"
    except Exception as e:
        return False, f"Unexpected error during validation: {str(e)}"


def validate_task_csv_format(csv_content: str) -> Tuple[bool, Optional[str]]:
    """
    Validate the format of task CSV content (for open_tasks.csv and fixed_tasks.csv).
    
    Validates:
    - CSV can be parsed
    - Header matches expected format
    - Each row has correct number of columns
    - Task field is not empty
    
    Args:
        csv_content: The CSV content as a string
        
    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if validation passes, False otherwise
        - error_message: None if valid, error description if invalid
    """
    if not csv_content or csv_content.strip() == '':
        return False, "CSV content is empty"
    
    try:
        # Parse CSV
        csv_reader = csv.reader(io.StringIO(csv_content))
        rows = list(csv_reader)
        
        if len(rows) == 0:
            return False, "CSV has no rows"
        
        # Validate header
        header = rows[0]
        if header != TASK_HEADER:
            return False, f"Invalid header. Expected {TASK_HEADER}, got {header}"
        
        # Validate data rows
        for row_num, row in enumerate(rows[1:], start=2):
            # Skip empty rows
            if not any(row):
                continue
                
            # Check column count
            if len(row) != len(TASK_HEADER):
                return False, f"Row {row_num}: Expected {len(TASK_HEADER)} columns, got {len(row)}"
            
            task, description = row
            
            # Validate task (should not be empty)
            if not task or task.strip() == '':
                return False, f"Row {row_num}: Task field is empty"
        
        return True, None
        
    except csv.Error as e:
        return False, f"CSV parsing error: {str(e)}"
    except Exception as e:
        return False, f"Unexpected error during validation: {str(e)}"
