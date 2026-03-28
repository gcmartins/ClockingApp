package service

import (
	"sort"
	"time"

	"github.com/gcmartins/clockingapp/internal/models"
)

// TaskDuration holds how long was spent on a task.
type TaskDuration struct {
	Task     string
	Duration time.Duration
}

// DaySummary holds one day's breakdown.
type DaySummary struct {
	Date  time.Time
	Tasks []TaskDuration
	Total time.Duration
}

// WeekSummary returns the last 7 calendar days (newest first) with per-task breakdowns.
func WeekSummary(records []models.ClockingRecord, now time.Time) []DaySummary {
	// Build day → task → duration map
	type dayKey = time.Time
	type taskKey = string
	dayTask := make(map[dayKey]map[taskKey]time.Duration)

	today := now.Truncate(24 * time.Hour)
	cutoff := today.AddDate(0, 0, -6)

	for _, r := range records {
		day := r.Date.Truncate(24 * time.Hour)
		if day.Before(cutoff) || day.After(today) {
			continue
		}
		if dayTask[day] == nil {
			dayTask[day] = make(map[taskKey]time.Duration)
		}
		dayTask[day][r.Task] += r.Duration(now)
	}

	// Collect all days in the 7-day window
	summaries := make([]DaySummary, 0, 7)
	for i := 0; i < 7; i++ {
		day := today.AddDate(0, 0, -i)
		taskMap := dayTask[day]
		var tasks []TaskDuration
		var total time.Duration
		for task, dur := range taskMap {
			tasks = append(tasks, TaskDuration{Task: task, Duration: dur})
			total += dur
		}
		sort.Slice(tasks, func(a, b int) bool { return tasks[a].Task < tasks[b].Task })
		summaries = append(summaries, DaySummary{Date: day, Tasks: tasks, Total: total})
	}
	return summaries
}
