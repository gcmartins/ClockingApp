package csv

import (
	"encoding/csv"
	"fmt"
	"os"
	"strings"
	"time"

	"github.com/gcmartins/clockingapp/internal/constants"
	"github.com/gcmartins/clockingapp/internal/models"
)

// InitCSVFiles creates the three CSV files with their headers if they don't exist.
func InitCSVFiles() error {
	files := map[string][]string{
		constants.ClockingCSV:  constants.ClockingHeaders,
		constants.FixedTaskCSV: constants.TaskHeaders,
		constants.OpenTaskCSV:  constants.TaskHeaders,
	}
	for path, headers := range files {
		if _, err := os.Stat(path); os.IsNotExist(err) {
			if err := writeCSVHeader(path, headers); err != nil {
				return fmt.Errorf("init %s: %w", path, err)
			}
		}
	}
	return nil
}

func writeCSVHeader(path string, headers []string) error {
	f, err := os.Create(path)
	if err != nil {
		return err
	}
	defer f.Close()
	w := csv.NewWriter(f)
	if err := w.Write(headers); err != nil {
		return err
	}
	w.Flush()
	return w.Error()
}

// AppendCheckIn writes a new check-in row to work_hours.csv.
func AppendCheckIn(path, taskKey string, now time.Time) error {
	f, err := os.OpenFile(path, os.O_APPEND|os.O_WRONLY|os.O_CREATE, 0644)
	if err != nil {
		return err
	}
	defer f.Close()
	w := csv.NewWriter(f)
	row := []string{
		now.Format(constants.DateFormat),
		taskKey,
		now.Format(constants.TimeFormat),
		"",
		"",
	}
	if err := w.Write(row); err != nil {
		return err
	}
	w.Flush()
	return w.Error()
}

// UpdateCheckOut reads the CSV at path, finds the last open row, fills the
// check-out time, and handles midnight crossover by splitting into two rows.
func UpdateCheckOut(path string, now time.Time) error {
	content, err := os.ReadFile(path)
	if err != nil {
		return err
	}

	r := csv.NewReader(strings.NewReader(string(content)))
	r.TrimLeadingSpace = true
	rows, err := r.ReadAll()
	if err != nil {
		return err
	}

	// Find last open row
	openIdx := -1
	for i := len(rows) - 1; i >= 1; i-- {
		if len(rows[i]) >= 5 && strings.TrimSpace(rows[i][3]) == "" {
			openIdx = i
			break
		}
	}
	if openIdx < 0 {
		return fmt.Errorf("no open clocking entry found")
	}

	openRow := rows[openIdx]
	checkInDate, err := time.Parse(constants.DateFormat, strings.TrimSpace(openRow[0]))
	if err != nil {
		return fmt.Errorf("invalid date in open row: %w", err)
	}

	today := now.Truncate(24 * time.Hour)
	recordDate := checkInDate.Truncate(24 * time.Hour)

	if today.Equal(recordDate) {
		// Same day: simple update
		rows[openIdx][3] = now.Format(constants.TimeFormat)
	} else {
		// Midnight crossover: split into two rows
		// Row 1: original date, check-in → 23:59
		rows[openIdx][3] = "23:59"

		// Row 2: next day(s), 00:00 → check-out
		nextDate := recordDate.AddDate(0, 0, 1)
		newRow := []string{
			nextDate.Format(constants.DateFormat),
			openRow[1],
			"00:00",
			now.Format(constants.TimeFormat),
			openRow[4],
		}
		rows = append(rows[:openIdx+1], append([][]string{newRow}, rows[openIdx+1:]...)...)
	}

	return writeAllRows(path, rows)
}

// WriteTaskCSV overwrites the task CSV file with the given tasks.
func WriteTaskCSV(path string, tasks []models.Task) error {
	rows := make([][]string, 0, len(tasks)+1)
	rows = append(rows, constants.TaskHeaders)
	for _, t := range tasks {
		rows = append(rows, []string{t.Key, t.Description})
	}
	return writeAllRows(path, rows)
}

// SaveCSVText replaces the content of path with the provided raw text after validation.
func SaveCSVText(path, text string) error {
	return os.WriteFile(path, []byte(text), 0644)
}

// ReadCSVText reads the raw text content of a CSV file.
func ReadCSVText(path string) (string, error) {
	b, err := os.ReadFile(path)
	if err != nil {
		return "", err
	}
	return string(b), nil
}

func writeAllRows(path string, rows [][]string) error {
	f, err := os.Create(path)
	if err != nil {
		return err
	}
	defer f.Close()
	w := csv.NewWriter(f)
	if err := w.WriteAll(rows); err != nil {
		return err
	}
	w.Flush()
	return w.Error()
}
