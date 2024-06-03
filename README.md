Clocking App
=====================

## Introduction

This is a small desktop application to help register clocking into a CSV file with the following features:
- Start, switch and stop clocking by click on Task buttons
- Update the CSV file synchronized with the timer and the button states 
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

## Integration with Jira
To perform actions related to Jira, you need to create a `.env` file with your credentials as the example below: 
```text
JIRA_EMAIL=your@email.com
JIRA_TOKEN=<YOUR JIRA TOKEN>
JIRA_URL=https://yourcompany.atlassian.net
```

## Integration with Clockify
To perform actions related to Clockify, you need to include the following credentials in the `.env` file as the example below: 
```text
CLOCKIFY_WORKSPACE=<YOUR CLOCKIFY WORKSPACE>
CLOCKIFY_API_KEY=<YOUR CLOCKIFY API KEY>
```