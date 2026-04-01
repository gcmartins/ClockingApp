Clocking App
=====================

## Introduction

This is a small desktop application to help register clocking into a SQLite file with the following features:
- Start, switch and stop clocking by click on Task buttons
- Update the SQLite file synchronized with the timer and the button states 
- Push the clockings to Jira worklog 
- Pull the actual assigned Jira issues to be clocked in the application
- Notification when the workday timer reaches 8h of work.

## Requirements

- **Python 3.10** (tested on this version, but smaller ones could also work)
- **venv** Python module (it comes by default in python installation but some linux distribution it needs to be manually 
installed)

## Installing the environment and create a launcher
Using the terminal, you can execute the following commands to quickly install the environment and configure launcher for the application. 

```shell
$ git clone git@github.com:gcmartins/ClockingApp.git
$ cd ClockingApp
$ source setup.sh
```

The `setup.sh` script will install the environment and create a launcher file (`Clocking.desktop`) that you can place anywhere to execute the application.

## Configuration

The application works without any API configuration for basic time tracking.

### Optional API Integration
To enable additional features like Jira worklog and Clockify integration, you can optionally configure one or both services:

- **Jira** - For pulling assigned issues and logging work to Jira
- **Clockify** - For pushing time entries to Clockify

### Managing Settings
You can access the settings at any time through:
- Menu: **Menu → Settings**
- The settings dialog allows you to update your API credentials for both Jira and Clockify

### Jira Integration (Optional)
To use Jira features (Update Open Tasks, Push to Jira), configure:
- **Email**: Your Atlassian account email
- **API Token**: Your Jira API token (get it from [Atlassian API Tokens](https://id.atlassian.com/manage-profile/security/api-tokens))
- **Atlassian URL**: Your company's Atlassian URL (e.g., `https://yourcompany.atlassian.net`)

**Features enabled**: Pull assigned Jira issues, push worklogs to Jira

### Clockify Integration (Optional)
To use Clockify features (Push to Clockify), configure:
- **Workspace ID**: Your Clockify workspace ID
- **API Key**: Your Clockify API key (get it from [Clockify Settings](https://app.clockify.me/user/settings))

**Features enabled**: Push time entries to Clockify

### Manual Configuration (Optional)
If you prefer, you can also manually create a `.env` file in the application directory with the following format:
```text
ATLASSIAN_EMAIL=your@email.com
ATLASSIAN_TOKEN=<YOUR JIRA TOKEN>
ATLASSIAN_URL=https://yourcompany.atlassian.net
CLOCKIFY_WORKSPACE=<YOUR CLOCKIFY WORKSPACE>
CLOCKIFY_API_KEY=<YOUR CLOCKIFY API KEY>
```