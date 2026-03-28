package constants

// CSV file names
const (
	ClockingCSV  = "work_hours.csv"
	FixedTaskCSV = "fixed_tasks.csv"
	OpenTaskCSV  = "open_tasks.csv"
)

// CSV column headers
var ClockingHeaders = []string{"Date", "Task", "Check In", "Check Out", "Message"}
var TaskHeaders = []string{"Task", "Description"}

// Jira open statuses to fetch
var JiraOpenStatuses = []string{"Backlog", "Review", "In Progress", "To Do", "Triage", "Blocked"}

// Overtime threshold
const OvertimeHours = 8

// Config keys
const (
	KeyAtlassianEmail = "ATLASSIAN_EMAIL"
	KeyAtlassianToken = "ATLASSIAN_TOKEN"
	KeyAtlassianURL   = "ATLASSIAN_URL"
	KeyClockifyWS     = "CLOCKIFY_WORKSPACE"
	KeyClockifyAPIKey = "CLOCKIFY_API_KEY"
)

// Date/time formats
const (
	DateFormat    = "2006-01-02"
	TimeFormat    = "15:04"
	DateTimeFmt   = "2006-01-02T15:04:05Z"
)
