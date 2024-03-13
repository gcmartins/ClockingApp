import datetime
import json
import os
from typing import List

import requests
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth

load_dotenv()
AUTH = HTTPBasicAuth(os.getenv('JIRA_EMAIL'), os.getenv('JIRA_TOKEN'))

JIRA_URL = f"{os.getenv('JIRA_URL')}/rest/api/3"

GET_HEADERS = {
    'Accept': 'application/json'
}

POST_HEADERS = {
    'Accept': 'application/json',
    'Content-Type': 'application/json',
}

OPEN_ISSUE_STATUS = ['Backlog', 'Review', 'In Progress', 'To Do']


def format_timedelta(td: datetime.timedelta) -> str:
    seconds = td.seconds
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return "{:02d}:{:02d}:{:02d}".format(hours, minutes, seconds)


def format_timedelta_jira(td: datetime.timedelta) -> str:
    seconds = td.seconds
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return "{:02d}h {:02d}m".format(hours, minutes)


def push_worklog_to_jira(issue_key: str, start_datetime: datetime.datetime, duration: datetime.timedelta) -> bool:
    payload = json.dumps({
        'timeSpentSeconds': duration.total_seconds(),
        'started': start_datetime.strftime("%Y-%m-%dT%H:%M:%S.000+0000")
    })

    response = requests.request(
        'POST',
        f'{JIRA_URL}/issue/{issue_key}/worklog',
        data=payload,
        headers=POST_HEADERS,
        auth=AUTH
    )

    return response.ok

def get_jira_open_issues() -> List[dict]:
    user_name = os.getenv("JIRA_EMAIL")
    response = requests.request(
        'GET',
        f'{JIRA_URL}/search?jql=assignee="{user_name}"',
        headers=POST_HEADERS,
        auth=AUTH
    )
    r = response.json()

    open_issues = []
    for issue in r['issues']:
        status = issue['fields']['status']['name']
        if status in OPEN_ISSUE_STATUS:
            summary = issue['fields']['summary']
            open_issues.append({'task': issue['key'], 'description': summary})

    return open_issues
