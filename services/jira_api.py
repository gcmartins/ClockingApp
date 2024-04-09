import datetime
import json
import os
from functools import cache
from typing import List

import requests
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth

from services.exceptions import ClockingException

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


@cache
def get_project_name(project_key: str) -> str:
    response = requests.get(f'{JIRA_URL}/project/{project_key}', auth=AUTH)

    if response.ok:
        project_data = response.json()
        return project_data.get('name')
    else:
        raise ClockingException('Failed to get Jira project name', response)


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
