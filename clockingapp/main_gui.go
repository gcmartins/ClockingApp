//go:build gui

package main

import "github.com/gcmartins/clockingapp/ui"

func launchGUI() error {
	state := ui.NewAppState()
	state.Run()
	return nil
}
