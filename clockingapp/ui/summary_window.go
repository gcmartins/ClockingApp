//go:build gui

package ui

import (
	"fmt"
	"time"

	"fyne.io/fyne/v2"
	"fyne.io/fyne/v2/container"
	"fyne.io/fyne/v2/dialog"
	"fyne.io/fyne/v2/widget"

	"github.com/gcmartins/clockingapp/internal/clockify"
	csvstore "github.com/gcmartins/clockingapp/internal/csv"
	"github.com/gcmartins/clockingapp/internal/constants"
	"github.com/gcmartins/clockingapp/internal/jira"
	"github.com/gcmartins/clockingapp/internal/models"
	"github.com/gcmartins/clockingapp/internal/service"
)

// NewSummaryWindow creates a window showing the last 7 days of clocked time.
func NewSummaryWindow(app fyne.App) fyne.Window {
	w := app.NewWindow("Clocking Summary")
	w.Resize(fyne.NewSize(700, 500))

	records, err := csvstore.ReadClockingCSV(constants.ClockingCSV)
	if err != nil {
		dialog.ShowError(err, w)
	}

	summaries := service.WeekSummary(records, time.Now())

	logArea := widget.NewMultiLineEntry()
	logArea.SetPlaceHolder("Push log will appear here...")
	logArea.Disable()

	dayCards := container.NewVBox()
	for _, day := range summaries {
		day := day // capture
		header := widget.NewLabelWithStyle(
			fmt.Sprintf("%s — %s", day.Date.Format("Mon 2006-01-02"), service.FormatDuration(day.Total)),
			fyne.TextAlignLeading, fyne.TextStyle{Bold: true},
		)
		rows := container.NewVBox()
		for _, td := range day.Tasks {
			rows.Add(widget.NewLabel(fmt.Sprintf("  %-20s %s", td.Task, service.FormatDuration(td.Duration))))
		}
		pushBtn := widget.NewButton("Push "+day.Date.Format("01/02"), func() {
			go pushDay(day, records, logArea, w)
		})
		card := container.NewVBox(header, rows, pushBtn)
		dayCards.Add(card)
	}

	content := container.NewVSplit(
		container.NewVScroll(dayCards),
		container.NewVScroll(logArea),
	)
	w.SetContent(content)
	return w
}

func pushDay(day service.DaySummary, allRecords []models.ClockingRecord, logArea *widget.Entry, win fyne.Window) {
	appendLog := func(msg string) {
		logArea.Enable()
		logArea.SetText(logArea.Text + msg + "\n")
		logArea.Disable()
	}

	jiraClient, jiraErr := jira.NewClient()
	clockifyClient, clockifyErr := clockify.NewClient()

	dayRecords := recordsForDay(allRecords, day.Date)
	for _, r := range dayRecords {
		if r.IsOpen() {
			appendLog(fmt.Sprintf("[Skip] %s has no check-out", r.Task))
			continue
		}
		dur := r.CheckOut.Sub(r.CheckIn)

		if jiraErr == nil {
			if err := jiraClient.PushWorklog(r.Task, r.CheckIn, dur); err != nil {
				appendLog(fmt.Sprintf("[Jira] ERROR %s: %v", r.Task, err))
			} else {
				appendLog(fmt.Sprintf("[Jira] OK %s (%s)", r.Task, service.FormatDurationJira(dur)))
			}
		} else {
			appendLog(fmt.Sprintf("[Jira] Skipped (not configured)"))
		}

		if clockifyErr == nil {
			if err := clockifyClient.PushWorklog(r.Task, r.CheckIn, r.CheckOut); err != nil {
				appendLog(fmt.Sprintf("[Clockify] ERROR %s: %v", r.Task, err))
			} else {
				appendLog(fmt.Sprintf("[Clockify] OK %s", r.Task))
			}
		} else {
			appendLog(fmt.Sprintf("[Clockify] Skipped (not configured)"))
		}
	}
	appendLog("Done.")
}

func recordsForDay(records []models.ClockingRecord, day time.Time) []models.ClockingRecord {
	target := day.Truncate(24 * time.Hour)
	var out []models.ClockingRecord
	for _, r := range records {
		if r.Date.Truncate(24*time.Hour).Equal(target) {
			out = append(out, r)
		}
	}
	return out
}
