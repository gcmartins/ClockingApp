//go:build gui

package ui

import (
	"fmt"
	"time"

	"fyne.io/fyne/v2"
	"fyne.io/fyne/v2/container"
	"fyne.io/fyne/v2/dialog"
	"fyne.io/fyne/v2/theme"
	"fyne.io/fyne/v2/widget"

	csvstore "github.com/gcmartins/clockingapp/internal/csv"
	"github.com/gcmartins/clockingapp/internal/constants"
	"github.com/gcmartins/clockingapp/internal/models"
	"github.com/gcmartins/clockingapp/internal/service"
	"github.com/gcmartins/clockingapp/internal/jira"
)

// ClockingView is the central widget containing task buttons, timer, and CSV editor.
type ClockingView struct {
	Container  *fyne.Container
	win        fyne.Window
	timerLabel *widget.Label
	csvEditor  *widget.Entry
	stopBtn    *widget.Button
	taskButtons *fyne.Container
	records    []models.ClockingRecord
	stopTicker chan struct{}
}

// NewClockingView creates and starts the clocking widget.
func NewClockingView(win fyne.Window) *ClockingView {
	cv := &ClockingView{win: win, stopTicker: make(chan struct{})}

	cv.timerLabel = widget.NewLabel("00:00:00")
	cv.timerLabel.TextStyle = fyne.TextStyle{Monospace: true}
	cv.timerLabel.Alignment = fyne.TextAlignCenter

	cv.stopBtn = widget.NewButtonWithIcon("Stop", theme.MediaStopIcon(), cv.clockOut)
	cv.stopBtn.Disable()

	cv.csvEditor = widget.NewMultiLineEntry()
	cv.csvEditor.SetPlaceHolder("Loading work_hours.csv ...")
	cv.csvEditor.Wrapping = fyne.TextWrapOff

	saveCSVBtn := widget.NewButton("Save CSV", cv.saveCSV)

	cv.taskButtons = container.NewVBox()

	cv.Container = container.NewBorder(
		container.NewVBox(cv.timerLabel, cv.stopBtn),
		container.NewVBox(saveCSVBtn),
		nil, nil,
		container.NewHSplit(
			container.NewVScroll(cv.taskButtons),
			container.NewVScroll(cv.csvEditor),
		),
	)

	cv.reload()
	cv.startTimer()
	return cv
}

func (cv *ClockingView) reload() {
	recs, err := csvstore.ReadClockingCSV(constants.ClockingCSV)
	if err == nil {
		cv.records = recs
	}

	// Rebuild task buttons
	cv.taskButtons.Objects = nil

	fixed, _ := csvstore.ReadTaskCSV(constants.FixedTaskCSV)
	open, _ := csvstore.ReadTaskCSV(constants.OpenTaskCSV)
	all := append(fixed, open...)

	active := service.ActiveTask(cv.records)
	for _, t := range all {
		t := t // capture loop var
		btn := widget.NewButton(t.Key, func() { cv.clockIn(t.Key) })
		if t.Key == active {
			btn.Importance = widget.HighImportance
		}
		lbl := widget.NewLabel(t.Description)
		lbl.Wrapping = fyne.TextWrapWord
		cv.taskButtons.Add(container.NewBorder(nil, nil, btn, nil, lbl))
	}
	cv.taskButtons.Refresh()

	if active != "" {
		cv.stopBtn.Enable()
	} else {
		cv.stopBtn.Disable()
	}

	// Reload CSV editor text
	if text, err := csvstore.ReadCSVText(constants.ClockingCSV); err == nil {
		cv.csvEditor.SetText(text)
	}
}

func (cv *ClockingView) clockIn(taskKey string) {
	recs, _ := csvstore.ReadClockingCSV(constants.ClockingCSV)
	if err := service.CheckIn(constants.ClockingCSV, taskKey, recs, time.Now()); err != nil {
		dialog.ShowError(err, cv.win)
		return
	}
	cv.reload()
}

func (cv *ClockingView) clockOut() {
	if err := service.CheckOut(constants.ClockingCSV, time.Now()); err != nil {
		dialog.ShowError(err, cv.win)
		return
	}
	cv.reload()
}

func (cv *ClockingView) saveCSV() {
	text := cv.csvEditor.Text
	if err := csvstore.ValidateClockingCSV(text); err != nil {
		dialog.ShowError(fmt.Errorf("CSV validation failed: %w", err), cv.win)
		return
	}
	if err := csvstore.SaveCSVText(constants.ClockingCSV, text); err != nil {
		dialog.ShowError(err, cv.win)
		return
	}
	cv.reload()
}

// UpdateOpenTasks fetches open Jira issues and rewrites open_tasks.csv.
func (cv *ClockingView) UpdateOpenTasks() {
	client, err := jira.NewClient()
	if err != nil {
		dialog.ShowError(err, cv.win)
		return
	}
	tasks, err := client.GetOpenIssues()
	if err != nil {
		dialog.ShowError(err, cv.win)
		return
	}
	if err := csvstore.WriteTaskCSV(constants.OpenTaskCSV, tasks); err != nil {
		dialog.ShowError(err, cv.win)
		return
	}
	cv.reload()
	dialog.ShowInformation("Jira Sync", fmt.Sprintf("Loaded %d open issues.", len(tasks)), cv.win)
}

func (cv *ClockingView) startTimer() {
	go func() {
		ticker := time.NewTicker(time.Second)
		defer ticker.Stop()
		for {
			select {
			case <-cv.stopTicker:
				return
			case <-ticker.C:
				recs, _ := csvstore.ReadClockingCSV(constants.ClockingCSV)
				now := time.Now()
				total := service.TodayHours(recs, now)
				label := service.FormatDuration(total)
				cv.timerLabel.SetText(label)
				if total >= constants.OvertimeHours*time.Hour {
					cv.timerLabel.Importance = widget.DangerImportance
				} else {
					cv.timerLabel.Importance = widget.MediumImportance
				}
				cv.timerLabel.Refresh()
			}
		}
	}()
}
