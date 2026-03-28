//go:build gui

package ui

import (
	"fyne.io/fyne/v2"
	"fyne.io/fyne/v2/container"
	"fyne.io/fyne/v2/dialog"
	"fyne.io/fyne/v2/widget"

	"github.com/gcmartins/clockingapp/internal/config"
	"github.com/gcmartins/clockingapp/internal/constants"
)

// NewSettingsDialog creates a tabbed settings dialog for Jira and Clockify credentials.
func NewSettingsDialog(win fyne.Window) dialog.Dialog {
	cfg := config.GetManager()

	// ── Jira tab ──────────────────────────────────────────────────────────────
	emailEntry := widget.NewEntry()
	emailEntry.SetText(cfg.Get(constants.KeyAtlassianEmail, ""))
	emailEntry.SetPlaceHolder("you@company.com")

	tokenEntry := widget.NewPasswordEntry()
	tokenEntry.SetText(cfg.Get(constants.KeyAtlassianToken, ""))
	tokenEntry.SetPlaceHolder("Jira API token")

	urlEntry := widget.NewEntry()
	urlEntry.SetText(cfg.Get(constants.KeyAtlassianURL, ""))
	urlEntry.SetPlaceHolder("https://yourcompany.atlassian.net")

	jiraForm := container.NewVBox(
		widget.NewForm(
			widget.NewFormItem("Email", emailEntry),
			widget.NewFormItem("API Token", tokenEntry),
			widget.NewFormItem("Atlassian URL", urlEntry),
		),
	)

	// ── Clockify tab ──────────────────────────────────────────────────────────
	wsEntry := widget.NewEntry()
	wsEntry.SetText(cfg.Get(constants.KeyClockifyWS, ""))
	wsEntry.SetPlaceHolder("Workspace ID")

	apiKeyEntry := widget.NewPasswordEntry()
	apiKeyEntry.SetText(cfg.Get(constants.KeyClockifyAPIKey, ""))
	apiKeyEntry.SetPlaceHolder("Clockify API key")

	clockifyForm := container.NewVBox(
		widget.NewForm(
			widget.NewFormItem("Workspace ID", wsEntry),
			widget.NewFormItem("API Key", apiKeyEntry),
		),
	)

	tabs := container.NewAppTabs(
		container.NewTabItem("Jira", jiraForm),
		container.NewTabItem("Clockify", clockifyForm),
	)

	save := func() error {
		updated := map[string]string{
			constants.KeyAtlassianEmail: emailEntry.Text,
			constants.KeyAtlassianToken: tokenEntry.Text,
			constants.KeyAtlassianURL:   urlEntry.Text,
			constants.KeyClockifyWS:     wsEntry.Text,
			constants.KeyClockifyAPIKey: apiKeyEntry.Text,
		}
		return cfg.UpdateAll(updated)
	}

	d := dialog.NewCustomConfirm("Settings", "Save", "Cancel", tabs, func(ok bool) {
		if !ok {
			return
		}
		if err := save(); err != nil {
			dialog.ShowError(err, win)
		}
	}, win)

	d.Resize(fyne.NewSize(500, 300))
	return d
}
