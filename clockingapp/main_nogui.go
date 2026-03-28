//go:build !gui

package main

import "fmt"

func launchGUI() error {
	return fmt.Errorf("GUI support not compiled in. Rebuild with: go build -tags gui -o clockingapp .\n" +
		"Requires Fyne: go get fyne.io/fyne/v2@latest")
}
