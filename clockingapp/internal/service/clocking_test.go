package service

import (
	"testing"
	"time"

	"github.com/gcmartins/clockingapp/internal/models"
	"github.com/stretchr/testify/assert"
)

func makeRecord(dateStr, task, checkIn, checkOut string) models.ClockingRecord {
	date, _ := time.ParseInLocation("2006-01-02", dateStr, time.Local)
	ci, _ := time.ParseInLocation("2006-01-02 15:04", dateStr+" "+checkIn, time.Local)
	r := models.ClockingRecord{Date: date, Task: task, CheckIn: ci}
	if checkOut != "" {
		co, _ := time.ParseInLocation("2006-01-02 15:04", dateStr+" "+checkOut, time.Local)
		r.CheckOut = co
	}
	return r
}

func TestTodayHours_NoRecords(t *testing.T) {
	now := time.Now()
	assert.Equal(t, time.Duration(0), TodayHours(nil, now))
}

func TestTodayHours_ClosedRecords(t *testing.T) {
	today := time.Now().Format("2006-01-02")
	records := []models.ClockingRecord{
		makeRecord(today, "TASK-1", "09:00", "12:00"), // 3h
		makeRecord(today, "TASK-2", "13:00", "17:00"), // 4h
	}
	total := TodayHours(records, time.Now())
	assert.Equal(t, 7*time.Hour, total)
}

func TestTodayHours_OpenRecord(t *testing.T) {
	today := time.Now().Format("2006-01-02")
	checkInTime, _ := time.ParseInLocation("2006-01-02 15:04", today+" 09:00", time.Local)
	now := checkInTime.Add(2 * time.Hour)

	records := []models.ClockingRecord{
		{Date: checkInTime, Task: "TASK-1", CheckIn: checkInTime},
	}
	total := TodayHours(records, now)
	assert.Equal(t, 2*time.Hour, total)
}

func TestTodayHours_IgnoresOtherDays(t *testing.T) {
	yesterday := time.Now().AddDate(0, 0, -1).Format("2006-01-02")
	today := time.Now().Format("2006-01-02")
	records := []models.ClockingRecord{
		makeRecord(yesterday, "TASK-1", "09:00", "17:00"),
		makeRecord(today, "TASK-2", "09:00", "10:00"),
	}
	total := TodayHours(records, time.Now())
	assert.Equal(t, 1*time.Hour, total)
}

func TestActiveTask_NoOpen(t *testing.T) {
	today := time.Now().Format("2006-01-02")
	records := []models.ClockingRecord{
		makeRecord(today, "TASK-1", "09:00", "12:00"),
	}
	assert.Equal(t, "", ActiveTask(records))
}

func TestActiveTask_Open(t *testing.T) {
	today := time.Now().Format("2006-01-02")
	records := []models.ClockingRecord{
		makeRecord(today, "TASK-1", "09:00", "12:00"),
		makeRecord(today, "TASK-2", "12:00", ""),
	}
	assert.Equal(t, "TASK-2", ActiveTask(records))
}

func TestFormatDuration(t *testing.T) {
	cases := []struct {
		d    time.Duration
		want string
	}{
		{8*time.Hour + 30*time.Minute + 15*time.Second, "08:30:15"},
		{0, "00:00:00"},
		{time.Hour, "01:00:00"},
		{59*time.Second, "00:00:59"},
	}
	for _, c := range cases {
		assert.Equal(t, c.want, FormatDuration(c.d))
	}
}

func TestFormatDurationJira(t *testing.T) {
	assert.Equal(t, "8h 30m", FormatDurationJira(8*time.Hour+30*time.Minute))
	assert.Equal(t, "2h", FormatDurationJira(2*time.Hour))
	assert.Equal(t, "45m", FormatDurationJira(45*time.Minute))
}
