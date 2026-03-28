package main

import (
	"fmt"
	"os"

	"github.com/spf13/cobra"

	"github.com/gcmartins/clockingapp/cmd/cli"
	csvstore "github.com/gcmartins/clockingapp/internal/csv"
)

func main() {
	// Initialise CSV files in the working directory.
	if err := csvstore.InitCSVFiles(); err != nil {
		fmt.Fprintf(os.Stderr, "init error: %v\n", err)
		os.Exit(1)
	}

	root := cli.NewRootCmd()
	root.AddCommand(newGuiCmd())
	if err := root.Execute(); err != nil {
		os.Exit(1)
	}
}

func newGuiCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "gui",
		Short: "Launch the graphical interface (requires build tag: -tags gui)",
		RunE: func(cmd *cobra.Command, args []string) error {
			return launchGUI()
		},
	}
}
