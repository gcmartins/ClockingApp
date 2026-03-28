package csv

import (
	"encoding/csv"
	"fmt"
	"strings"
	"time"
	"unicode"
)

// ValidateClockingCSV validates the raw CSV text of work_hours.csv.
// Returns a descriptive error if the content is invalid, nil otherwise.
func ValidateClockingCSV(content string) error {
	r := csv.NewReader(strings.NewReader(content))
	r.TrimLeadingSpace = true
	rows, err := r.ReadAll()
	if err != nil {
		return fmt.Errorf("CSV parse error: %w", err)
	}
	if len(rows) == 0 {
		return fmt.Errorf("CSV is empty")
	}

	// Validate header
	expected := []string{"Date", "Task", "Check In", "Check Out", "Message"}
	if err := validateHeader(rows[0], expected); err != nil {
		return err
	}

	for i, row := range rows[1:] {
		lineNum := i + 2
		if len(row) != 5 {
			return fmt.Errorf("line %d: expected 5 columns, got %d", lineNum, len(row))
		}
		if err := validateDate(row[0], lineNum); err != nil {
			return err
		}
		if err := validateTime(row[2], lineNum, "Check In"); err != nil {
			return err
		}
		checkOutStr := strings.TrimSpace(row[3])
		if checkOutStr != "" {
			if err := validateTime(checkOutStr, lineNum, "Check Out"); err != nil {
				return err
			}
			// Check-out must be >= check-in
			ci, _ := time.Parse("15:04", strings.TrimSpace(row[2]))
			co, _ := time.Parse("15:04", checkOutStr)
			if co.Before(ci) {
				return fmt.Errorf("line %d: Check Out %q is before Check In %q", lineNum, checkOutStr, row[2])
			}
		}
		if err := validateMessage(row[4], lineNum); err != nil {
			return err
		}
	}
	return nil
}

// ValidateTaskCSV validates the raw CSV text of a task CSV file.
func ValidateTaskCSV(content string) error {
	r := csv.NewReader(strings.NewReader(content))
	r.TrimLeadingSpace = true
	rows, err := r.ReadAll()
	if err != nil {
		return fmt.Errorf("CSV parse error: %w", err)
	}
	if len(rows) == 0 {
		return fmt.Errorf("CSV is empty")
	}
	expected := []string{"Task", "Description"}
	if err := validateHeader(rows[0], expected); err != nil {
		return err
	}
	for i, row := range rows[1:] {
		lineNum := i + 2
		if len(row) != 2 {
			return fmt.Errorf("line %d: expected 2 columns, got %d", lineNum, len(row))
		}
		if strings.TrimSpace(row[0]) == "" {
			return fmt.Errorf("line %d: Task key must not be empty", lineNum)
		}
	}
	return nil
}

func validateHeader(got, expected []string) error {
	if len(got) != len(expected) {
		return fmt.Errorf("header: expected %v, got %v", expected, got)
	}
	for i, h := range expected {
		if strings.TrimSpace(got[i]) != h {
			return fmt.Errorf("header column %d: expected %q, got %q", i+1, h, got[i])
		}
	}
	return nil
}

func validateDate(s string, line int) error {
	s = strings.TrimSpace(s)
	if _, err := time.Parse("2006-01-02", s); err != nil {
		return fmt.Errorf("line %d: invalid date %q (expected YYYY-MM-DD)", line, s)
	}
	return nil
}

func validateTime(s string, line int, field string) error {
	s = strings.TrimSpace(s)
	t, err := time.Parse("15:04", s)
	if err != nil {
		return fmt.Errorf("line %d: invalid %s time %q (expected HH:MM)", line, field, s)
	}
	if t.Hour() < 0 || t.Hour() > 23 || t.Minute() < 0 || t.Minute() > 59 {
		return fmt.Errorf("line %d: %s time %q out of range", line, field, s)
	}
	return nil
}

func validateMessage(s string, line int) error {
	if len(s) > 500 {
		return fmt.Errorf("line %d: message exceeds 500 characters", line)
	}
	for _, r := range s {
		if !unicode.IsPrint(r) && r != '\t' && r != '\n' && r != '\r' {
			return fmt.Errorf("line %d: message contains invalid character %q", line, r)
		}
	}
	return nil
}
