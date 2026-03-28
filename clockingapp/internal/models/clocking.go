package models

import "time"

// ClockingRecord represents a single row in work_hours.csv.
type ClockingRecord struct {
	Date     time.Time
	Task     string
	CheckIn  time.Time
	CheckOut time.Time // zero value means not checked out yet
	Message  string
}

// IsOpen returns true when this record has no check-out time yet.
func (r ClockingRecord) IsOpen() bool {
	return r.CheckOut.IsZero()
}

// Duration returns the duration of a completed record.
// For open records the caller must supply the current time.
func (r ClockingRecord) Duration(now time.Time) time.Duration {
	end := r.CheckOut
	if r.IsOpen() {
		end = now
	}
	return end.Sub(r.CheckIn)
}
