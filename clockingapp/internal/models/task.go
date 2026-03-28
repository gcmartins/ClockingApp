package models

// Task represents a row in fixed_tasks.csv or open_tasks.csv.
type Task struct {
	Key         string
	Description string
}
