//go:build gui

package ui

import (
	"fmt"
	"strings"
	"time"

	"fyne.io/fyne/v2"
	"fyne.io/fyne/v2/container"
	"fyne.io/fyne/v2/dialog"
	"fyne.io/fyne/v2/widget"

	csvstore "github.com/gcmartins/clockingapp/internal/csv"
	"github.com/gcmartins/clockingapp/internal/constants"
	"github.com/gcmartins/clockingapp/internal/service"
)

// NewEodWindow creates the end-of-day report window.
func NewEodWindow(app fyne.App) fyne.Window {
	w := app.NewWindow("EOD Report — " + time.Now().Format("2006-01-02"))
	w.Resize(fyne.NewSize(600, 400))

	records, err := csvstore.ReadClockingCSV(constants.ClockingCSV)
	if err != nil {
		dialog.ShowError(err, w)
	}

	entries := service.EodReport(records, time.Now())

	var sb strings.Builder
	if len(entries) == 0 {
		sb.WriteString("No entries for today.\n")
	}
	for _, e := range entries {
		sb.WriteString(fmt.Sprintf("%s (%s)\n", e.Task, service.FormatDuration(e.Duration)))
		for _, msg := range e.Messages {
			sb.WriteString(fmt.Sprintf("  - %s\n", msg))
		}
		sb.WriteString("\n")
	}

	text := widget.NewMultiLineEntry()
	text.SetText(sb.String())
	text.Disable()

	w.SetContent(container.NewVScroll(text))
	return w
}
