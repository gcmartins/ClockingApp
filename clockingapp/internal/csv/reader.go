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

// ReadClockingCSV parses work_hours.csv into a slice of ClockingRecord.
func ReadClockingCSV(path string) ([]models.ClockingRecord, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()

	r := csv.NewReader(f)
	r.TrimLeadingSpace = true

	rows, err := r.ReadAll()
	if err != nil {
		return nil, err
	}
	if len(rows) == 0 {
		return nil, nil
	}

	// Skip header row
	records := make([]models.ClockingRecord, 0, len(rows)-1)
	for i, row := range rows[1:] {
		if len(row) < 5 {
			return nil, fmt.Errorf("row %d: expected 5 columns, got %d", i+2, len(row))
		}
		rec, err := parseClockingRow(row)
		if err != nil {
			return nil, fmt.Errorf("row %d: %w", i+2, err)
		}
		records = append(records, rec)
	}
	return records, nil
}

func parseClockingRow(row []string) (models.ClockingRecord, error) {
	date, err := time.Parse(constants.DateFormat, strings.TrimSpace(row[0]))
	if err != nil {
		return models.ClockingRecord{}, fmt.Errorf("invalid date %q: %w", row[0], err)
	}

	checkInStr := strings.TrimSpace(row[2])
	checkIn, err := time.Parse(constants.TimeFormat, checkInStr)
	if err != nil {
		return models.ClockingRecord{}, fmt.Errorf("invalid check-in time %q: %w", checkInStr, err)
	}
	// Combine date + time into a single time.Time
	checkIn = time.Date(date.Year(), date.Month(), date.Day(),
		checkIn.Hour(), checkIn.Minute(), 0, 0, time.Local)

	rec := models.ClockingRecord{
		Date:    date,
		Task:    strings.TrimSpace(row[1]),
		CheckIn: checkIn,
		Message: strings.TrimSpace(row[4]),
	}

	checkOutStr := strings.TrimSpace(row[3])
	if checkOutStr != "" {
		checkOut, err := time.Parse(constants.TimeFormat, checkOutStr)
		if err != nil {
			return models.ClockingRecord{}, fmt.Errorf("invalid check-out time %q: %w", checkOutStr, err)
		}
		rec.CheckOut = time.Date(date.Year(), date.Month(), date.Day(),
			checkOut.Hour(), checkOut.Minute(), 0, 0, time.Local)
	}

	return rec, nil
}

// ReadTaskCSV parses fixed_tasks.csv or open_tasks.csv into a slice of Task.
func ReadTaskCSV(path string) ([]models.Task, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()

	r := csv.NewReader(f)
	r.TrimLeadingSpace = true

	rows, err := r.ReadAll()
	if err != nil {
		return nil, err
	}
	if len(rows) == 0 {
		return nil, nil
	}

	tasks := make([]models.Task, 0, len(rows)-1)
	for i, row := range rows[1:] {
		if len(row) < 2 {
			return nil, fmt.Errorf("task row %d: expected 2 columns, got %d", i+2, len(row))
		}
		tasks = append(tasks, models.Task{
			Key:         strings.TrimSpace(row[0]),
			Description: strings.TrimSpace(row[1]),
		})
	}
	return tasks, nil
}
