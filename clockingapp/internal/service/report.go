package service

import (
	"time"

	"github.com/gcmartins/clockingapp/internal/models"
)

// EodEntry is a single line in the end-of-day report.
type EodEntry struct {
	Task     string
	Duration time.Duration
	Messages []string
}

// EodReport generates today's report grouped by task.
func EodReport(records []models.ClockingRecord, now time.Time) []EodEntry {
	today := now.Truncate(24 * time.Hour)

	type accumulator struct {
		duration time.Duration
		messages []string
	}
	taskMap := make(map[string]*accumulator)
	var order []string

	for _, r := range records {
		if r.Date.Truncate(24*time.Hour) != today {
			continue
		}
		acc, exists := taskMap[r.Task]
		if !exists {
			acc = &accumulator{}
			taskMap[r.Task] = acc
			order = append(order, r.Task)
		}
		acc.duration += r.Duration(now)
		if r.Message != "" {
			acc.messages = append(acc.messages, r.Message)
		}
	}

	entries := make([]EodEntry, 0, len(order))
	for _, task := range order {
		acc := taskMap[task]
		entries = append(entries, EodEntry{
			Task:     task,
			Duration: acc.duration,
			Messages: acc.messages,
		})
	}
	return entries
}
