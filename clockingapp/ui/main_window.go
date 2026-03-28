//go:build gui

package ui

import (
	"fyne.io/fyne/v2"
	"fyne.io/fyne/v2/container"
	"fyne.io/fyne/v2/driver/desktop"
	"fyne.io/fyne/v2/menu"
	"fyne.io/fyne/v2/theme"
)

// MainWindow wraps the primary application window.
type MainWindow struct {
	fyne.Window
	state          *AppState
	clockingView   *ClockingView
}

// NewMainWindow creates the main application window with menu bar and system tray.
func NewMainWindow(state *AppState) *MainWindow {
	w := state.App.NewWindow("ClockingApp")
	w.Resize(fyne.NewSize(900, 600))
	w.SetMaster()

	mw := &MainWindow{Window: w, state: state}

	// Central content
	cv := NewClockingView(w)
	mw.clockingView = cv
	w.SetContent(container.NewStack(cv.Container))

	// Menu bar
	w.SetMainMenu(mw.buildMenu())

	// System tray (only available on desktop drivers)
	if desk, ok := fyne.CurrentApp().(desktop.App); ok {
		trayMenu := fyne.NewMenu("ClockingApp",
			fyne.NewMenuItem("Show", func() { w.Show() }),
			fyne.NewMenuItemSeparator(),
			fyne.NewMenuItem("Quit", func() { state.App.Quit() }),
		)
		desk.SetSystemTrayMenu(trayMenu)
		desk.SetSystemTrayIcon(theme.ComputerIcon())
	}

	// Minimise to tray on close
	w.SetCloseIntercept(func() { w.Hide() })

	return mw
}

func (mw *MainWindow) buildMenu() *fyne.MainMenu {
	return fyne.NewMainMenu(
		fyne.NewMenu("File",
			fyne.NewMenuItem("Settings", func() {
				d := NewSettingsDialog(mw.Window)
				d.Show()
			}),
			fyne.NewMenuItemSeparator(),
			fyne.NewMenuItem("Quit", func() { mw.state.App.Quit() }),
		),
		fyne.NewMenu("View",
			fyne.NewMenuItem("Clocking Summary", func() {
				NewSummaryWindow(mw.state.App).Show()
			}),
			fyne.NewMenuItem("EOD Report", func() {
				NewEodWindow(mw.state.App).Show()
			}),
		),
		fyne.NewMenu("Tasks",
			fyne.NewMenuItem("Update Open Tasks (Jira)", func() {
				go mw.clockingView.UpdateOpenTasks()
			}),
		),
	)
}

// Show displays the window.
func (mw *MainWindow) Show() {
	mw.Window.Show()
}

// buildTrayMenu is a helper kept for reference; integrated inline above.
func buildTrayMenu(app fyne.App, w fyne.Window) *fyne.Menu {
	return fyne.NewMenu("ClockingApp",
		fyne.NewMenuItem("Show", func() { w.Show() }),
		fyne.NewMenuItemSeparator(),
		fyne.NewMenuItem("Quit", func() { app.Quit() }),
	)
}

// suppress unused import warning
var _ = menu.NewItem
