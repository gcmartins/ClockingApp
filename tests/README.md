# Testing Guide

## Running Tests

To run all tests:

```bash
pytest tests/
```

To run tests with verbose output:

```bash
pytest tests/ -v
```

To run a specific test file:

```bash
pytest tests/test_csv_validator.py -v
```

To run a specific test class or method:

```bash
pytest tests/test_csv_validator.py::TestClockingCSVValidation -v
pytest tests/test_csv_validator.py::TestClockingCSVValidation::test_valid_clocking_csv -v
```

## Test Coverage

The test suite covers:

### Date and Time Validation
- Valid and invalid date formats (YYYY-MM-DD)
- Valid and invalid time formats (HH:MM)

### Clocking CSV Validation
- Header validation
- Column count validation
- Date format validation in data rows
- Time format validation for check-in/check-out
- Logical validation (check-out after check-in)
- Empty task field detection
- Cross-day clocking support
- Missing check-out time handling

### Task CSV Validation
- Header validation
- Column count validation
- Empty task field detection
- Optional description fields

### Edge Cases
- Empty CSV content
- CSV with only headers
- Special characters in fields
- Whitespace handling

## Running with Coverage

Coverage is enabled by default via `pyproject.toml`. A simple `pytest` run reports coverage:

```bash
uv run pytest
```

To see a quick summary without the HTML report:

```bash
uv run pytest --no-cov-on-fail --cov-report=term-missing
```