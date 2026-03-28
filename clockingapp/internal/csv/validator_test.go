package csv

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestValidateClockingCSV_Valid(t *testing.T) {
	content := "Date,Task,Check In,Check Out,Message\n2024-01-15,TASK-1,09:00,17:30,Some work done\n2024-01-15,TASK-2,17:30,,\n"
	assert.NoError(t, ValidateClockingCSV(content))
}

func TestValidateClockingCSV_InvalidHeader(t *testing.T) {
	content := "date,task,checkin,checkout,msg\n"
	assert.Error(t, ValidateClockingCSV(content))
}

func TestValidateClockingCSV_InvalidDate(t *testing.T) {
	content := "Date,Task,Check In,Check Out,Message\n15-01-2024,TASK-1,09:00,17:00,\n"
	assert.Error(t, ValidateClockingCSV(content))
}

func TestValidateClockingCSV_InvalidTime(t *testing.T) {
	content := "Date,Task,Check In,Check Out,Message\n2024-01-15,TASK-1,9:0,17:00,\n"
	assert.Error(t, ValidateClockingCSV(content))
}

func TestValidateClockingCSV_CheckOutBeforeCheckIn(t *testing.T) {
	content := "Date,Task,Check In,Check Out,Message\n2024-01-15,TASK-1,17:00,09:00,\n"
	assert.Error(t, ValidateClockingCSV(content))
}

func TestValidateClockingCSV_MessageTooLong(t *testing.T) {
	msg := string(make([]byte, 501))
	content := "Date,Task,Check In,Check Out,Message\n2024-01-15,TASK-1,09:00,17:00," + msg + "\n"
	assert.Error(t, ValidateClockingCSV(content))
}

func TestValidateClockingCSV_OpenEntry(t *testing.T) {
	// Open entry (no check-out) is valid
	content := "Date,Task,Check In,Check Out,Message\n2024-01-15,TASK-1,09:00,,\n"
	assert.NoError(t, ValidateClockingCSV(content))
}

func TestValidateTaskCSV_Valid(t *testing.T) {
	content := "Task,Description\nTASK-1,Do something\nTASK-2,Do another thing\n"
	assert.NoError(t, ValidateTaskCSV(content))
}

func TestValidateTaskCSV_InvalidHeader(t *testing.T) {
	content := "task,desc\nTASK-1,Do something\n"
	assert.Error(t, ValidateTaskCSV(content))
}

func TestValidateTaskCSV_EmptyKey(t *testing.T) {
	content := "Task,Description\n,Do something\n"
	assert.Error(t, ValidateTaskCSV(content))
}

func TestValidateClockingCSV_WrongColumnCount(t *testing.T) {
	content := "Date,Task,Check In,Check Out,Message\n2024-01-15,TASK-1,09:00\n"
	assert.Error(t, ValidateClockingCSV(content))
}
