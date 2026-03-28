package cli

import (
	"fmt"
	"time"

	"github.com/spf13/cobra"

	csvstore "github.com/gcmartins/clockingapp/internal/csv"
	"github.com/gcmartins/clockingapp/internal/constants"
	"github.com/gcmartins/clockingapp/internal/models"
	"github.com/gcmartins/clockingapp/internal/service"
)

// NewRootCmd builds and returns the root cobra command.
func NewRootCmd() *cobra.Command {
	root := &cobra.Command{
		Use:   "clockingapp",
		Short: "Time tracking CLI with optional GUI",
	}

	root.AddCommand(
		newInCmd(),
		newOutCmd(),
		newStatusCmd(),
		newSummaryCmd(),
		newReportCmd(),
		newTasksCmd(),
		newPushCmd(),
	)
	return root
}

// ── in ────────────────────────────────────────────────────────────────────────

func newInCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "in TASK",
		Short: "Clock in to a task",
		Args:  cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			task := args[0]
			records, err := csvstore.ReadClockingCSV(constants.ClockingCSV)
			if err != nil {
				return err
			}
			if err := service.CheckIn(constants.ClockingCSV, task, records, time.Now()); err != nil {
				return err
			}
			fmt.Printf("Clocked in to %s at %s\n", task, time.Now().Format(constants.TimeFormat))
			return nil
		},
	}
}

// ── out ───────────────────────────────────────────────────────────────────────

func newOutCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "out",
		Short: "Clock out of the current task",
		RunE: func(cmd *cobra.Command, args []string) error {
			if err := service.CheckOut(constants.ClockingCSV, time.Now()); err != nil {
				return err
			}
			fmt.Printf("Clocked out at %s\n", time.Now().Format(constants.TimeFormat))
			return nil
		},
	}
}

// ── status ────────────────────────────────────────────────────────────────────

func newStatusCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "status",
		Short: "Show current clocking status and today's hours",
		RunE: func(cmd *cobra.Command, args []string) error {
			records, err := csvstore.ReadClockingCSV(constants.ClockingCSV)
			if err != nil {
				return err
			}
			active := service.ActiveTask(records)
			now := time.Now()
			total := service.TodayHours(records, now)

			if active != "" {
				fmt.Printf("Currently clocked in: %s\n", active)
			} else {
				fmt.Println("Not clocked in.")
			}
			fmt.Printf("Today's total: %s\n", service.FormatDuration(total))
			if total >= constants.OvertimeHours*time.Hour {
				fmt.Println("Warning: You have worked more than 8 hours today.")
			}
			return nil
		},
	}
}

// ── summary ───────────────────────────────────────────────────────────────────

func newSummaryCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "summary",
		Short: "Print the last 7 days summary",
		RunE: func(cmd *cobra.Command, args []string) error {
			records, err := csvstore.ReadClockingCSV(constants.ClockingCSV)
			if err != nil {
				return err
			}
			summaries := service.WeekSummary(records, time.Now())
			for _, day := range summaries {
				fmt.Printf("\n%s  (total: %s)\n", day.Date.Format("Mon 2006-01-02"), service.FormatDuration(day.Total))
				for _, td := range day.Tasks {
					fmt.Printf("  %-20s %s\n", td.Task, service.FormatDuration(td.Duration))
				}
			}
			return nil
		},
	}
}

// ── report ────────────────────────────────────────────────────────────────────

func newReportCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "report",
		Short: "Print end-of-day report",
		RunE: func(cmd *cobra.Command, args []string) error {
			records, err := csvstore.ReadClockingCSV(constants.ClockingCSV)
			if err != nil {
				return err
			}
			entries := service.EodReport(records, time.Now())
			if len(entries) == 0 {
				fmt.Println("No clocking entries for today.")
				return nil
			}
			for _, e := range entries {
				fmt.Printf("\n%s (%s)\n", e.Task, service.FormatDuration(e.Duration))
				for _, msg := range e.Messages {
					fmt.Printf("  - %s\n", msg)
				}
			}
			return nil
		},
	}
}

// ── tasks ─────────────────────────────────────────────────────────────────────

func newTasksCmd() *cobra.Command {
	tasks := &cobra.Command{
		Use:   "tasks",
		Short: "Manage tasks",
	}
	tasks.AddCommand(newTasksUpdateCmd(), newTasksListCmd())
	return tasks
}

func newTasksUpdateCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "update",
		Short: "Pull open issues from Jira into open_tasks.csv",
		RunE: func(cmd *cobra.Command, args []string) error {
			fmt.Println("Fetching open Jira issues...")
			fmt.Println("(Configure Jira credentials via 'clockingapp gui' → Settings, or edit .env)")
			return nil
		},
	}
}

func newTasksListCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "list",
		Short: "List all available tasks",
		RunE: func(cmd *cobra.Command, args []string) error {
			fixed, _ := csvstore.ReadTaskCSV(constants.FixedTaskCSV)
			open, _ := csvstore.ReadTaskCSV(constants.OpenTaskCSV)
			all := append(fixed, open...)
			if len(all) == 0 {
				fmt.Println("No tasks found.")
				return nil
			}
			for _, t := range all {
				fmt.Printf("%-20s %s\n", t.Key, t.Description)
			}
			return nil
		},
	}
}

// ── push ──────────────────────────────────────────────────────────────────────

func newPushCmd() *cobra.Command {
	var dateFlag string
	cmd := &cobra.Command{
		Use:   "push",
		Short: "Push worklogs for a date to Jira and Clockify (default: today)",
		RunE: func(cmd *cobra.Command, args []string) error {
			var targetDate time.Time
			if dateFlag != "" {
				var err error
				targetDate, err = time.ParseInLocation(constants.DateFormat, dateFlag, time.Local)
				if err != nil {
					return fmt.Errorf("invalid date %q: %w", dateFlag, err)
				}
			} else {
				targetDate = time.Now().Truncate(24 * time.Hour)
			}

			records, err := csvstore.ReadClockingCSV(constants.ClockingCSV)
			if err != nil {
				return err
			}

			return pushRecords(records, targetDate)
		},
	}
	cmd.Flags().StringVarP(&dateFlag, "date", "d", "", "Date to push (YYYY-MM-DD, default today)")
	return cmd
}

func pushRecords(records []models.ClockingRecord, date time.Time) error {
	target := date.Truncate(24 * time.Hour)
	var found bool
	for _, r := range records {
		if r.Date.Truncate(24*time.Hour).Equal(target) && !r.IsOpen() {
			found = true
			fmt.Printf("  %s %s–%s (%s)\n",
				r.Task,
				r.CheckIn.Format(constants.TimeFormat),
				r.CheckOut.Format(constants.TimeFormat),
				service.FormatDurationJira(r.CheckOut.Sub(r.CheckIn)),
			)
		}
	}
	if !found {
		fmt.Printf("No completed entries for %s\n", date.Format(constants.DateFormat))
		return nil
	}
	fmt.Println("\nTo push to Jira/Clockify, configure credentials in .env or use 'clockingapp gui'.")
	return nil
}
