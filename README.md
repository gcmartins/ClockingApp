Clocking App
=====================

## Introduction

A desktop time tracking application that stores clockings in a local SQLite database. Key features:

- Start, switch, and stop clocking by clicking task buttons
- Real-time timer synchronized with the database and button states
- Notification when the workday timer reaches 8 hours of work
- Manage tasks (create, edit, delete) with fixed or Jira-linked types
- View clocking history and a 7-day summary report
- Generate end-of-day (EOD) reports with per-task messages
- Push time entries to Jira worklogs and/or Clockify
- Pull assigned Jira issues to populate available tasks
- System tray support for quick minimize/restore

## Requirements

- **Python 3.10+**
- **[uv](https://docs.astral.sh/uv/)** — Python package and project manager

## Installation

Clone the repository and run the setup script:

```shell
git clone git@github.com:gcmartins/ClockingApp.git
cd ClockingApp
source setup.sh
```

The `setup.sh` script will:
1. Create a virtual environment and install dependencies via `uv sync`
2. Generate a `Clocking.desktop` launcher file you can place anywhere to launch the application

## Running the Application

```shell
python app.py
```

Or use the generated `Clocking.desktop` launcher.

## Running Tests

```shell
pytest           # Run all tests
pytest --cov     # With coverage report
pytest -v        # Verbose output
```

## Configuration

The application works without any API configuration for basic time tracking.

### Optional API Integration

To enable Jira and/or Clockify integration, open **Menu → Settings** and fill in the relevant credentials. You can also create a `.env` file manually in the project directory:

```text
ATLASSIAN_EMAIL=your@email.com
ATLASSIAN_TOKEN=<YOUR_JIRA_TOKEN>
ATLASSIAN_URL=https://yourcompany.atlassian.net
CLOCKIFY_WORKSPACE=<YOUR_CLOCKIFY_WORKSPACE_ID>
CLOCKIFY_API_KEY=<YOUR_CLOCKIFY_API_KEY>
JIRA_TASK_PREFIX=PREFIX1, PREFIX2   # Optional — filter pulled tasks by prefix
```

### Jira Integration (Optional)

Configure via **Menu → Settings → Jira** or the `.env` file:

| Field | Description |
|---|---|
| `ATLASSIAN_EMAIL` | Your Atlassian account email |
| `ATLASSIAN_TOKEN` | API token from [Atlassian API Tokens](https://id.atlassian.com/manage-profile/security/api-tokens) |
| `ATLASSIAN_URL` | Your company's Atlassian URL (e.g., `https://yourcompany.atlassian.net`) |
| `JIRA_TASK_PREFIX` | *(Optional)* Comma-separated prefixes to filter pulled issues |

**Enabled features:** Pull assigned Jira issues, push worklogs to Jira.

### Clockify Integration (Optional)

Configure via **Menu → Settings → Clockify** or the `.env` file:

| Field | Description |
|---|---|
| `CLOCKIFY_WORKSPACE` | Your Clockify workspace ID |
| `CLOCKIFY_API_KEY` | API key from [Clockify Settings](https://app.clockify.me/user/settings) |

**Enabled features:** Push time entries to Clockify (auto-creates projects and tasks as needed).

## Menu Reference

| Menu Item | Description |
|---|---|
| **Clocking Summary** | 7-day summary view with per-task durations and push-to-Jira/Clockify buttons |
| **Update Open Tasks** | Fetch assigned Jira issues and sync them as available tasks |
| **Manage Tasks** | Create, edit, or delete tasks |
| **EOD Report** | Generate an end-of-day report with task messages |
| **Settings** | Configure Jira and Clockify credentials |
| **Exit** | Quit the application (`Ctrl+Q`) |
