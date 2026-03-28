//go:build gui

package ui

import (
	"fyne.io/fyne/v2"
	"fyne.io/fyne/v2/app"
)

const appID = "com.gcmartins.clockingapp"

// AppState holds shared Fyne application state.
type AppState struct {
	App        fyne.App
	MainWindow fyne.Window
}

// NewAppState initialises the Fyne application.
func NewAppState() *AppState {
	a := app.NewWithID(appID)
	return &AppState{App: a}
}

// Run shows the main window and starts the Fyne event loop.
func (s *AppState) Run() {
	w := NewMainWindow(s)
	s.MainWindow = w.Window
	w.Show()
	s.App.Run()
}
