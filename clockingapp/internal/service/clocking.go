package service

import (
	"fmt"
	"time"

	csvstore "github.com/gcmartins/clockingapp/internal/csv"
	"github.com/gcmartins/clockingapp/internal/models"
)

// CheckIn clocks in to taskKey. If there is already an open entry for a
// different task, it is checked out first.
func CheckIn(path, taskKey string, records []models.ClockingRecord, now time.Time) error {
	// Auto-checkout any open entry for a different task
	for _, r := range records {
		if r.IsOpen() && r.Task != taskKey {
			if err := csvstore.UpdateCheckOut(path, now); err != nil {
				return fmt.Errorf("auto-checkout failed: %w", err)
			}
			break
		}
	}
	return csvstore.AppendCheckIn(path, taskKey, now)
}

// CheckOut closes the most recent open entry.
func CheckOut(path string, now time.Time) error {
	return csvstore.UpdateCheckOut(path, now)
}

// ActiveTask returns the task key of the currently open clocking entry, or "" if none.
func ActiveTask(records []models.ClockingRecord) string {
	for i := len(records) - 1; i >= 0; i-- {
		if records[i].IsOpen() {
			return records[i].Task
		}
	}
	return ""
}

// TodayHours returns the total duration worked today across all records.
// If there is an open entry, the current time is used as the end time for it.
func TodayHours(records []models.ClockingRecord, now time.Time) time.Duration {
	today := now.Truncate(24 * time.Hour)
	var total time.Duration
	for _, r := range records {
		if r.Date.Truncate(24*time.Hour).Equal(today) {
			total += r.Duration(now)
		}
	}
	return total
}

// FormatDuration formats a duration as HH:MM:SS.
func FormatDuration(d time.Duration) string {
	if d < 0 {
		d = 0
	}
	h := int(d.Hours())
	m := int(d.Minutes()) % 60
	s := int(d.Seconds()) % 60
	return fmt.Sprintf("%02d:%02d:%02d", h, m, s)
}

// FormatDurationJira formats a duration as "Xh Ym" for Jira worklogs.
func FormatDurationJira(d time.Duration) string {
	h := int(d.Hours())
	m := int(d.Minutes()) % 60
	if h > 0 && m > 0 {
		return fmt.Sprintf("%dh %dm", h, m)
	} else if h > 0 {
		return fmt.Sprintf("%dh", h)
	}
	return fmt.Sprintf("%dm", m)
}
