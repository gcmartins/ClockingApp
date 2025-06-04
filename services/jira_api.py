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

OPEN_ISSUE_STATUS = ['Backlog', 'Review', 'In Progress', 'To Do', 'Triage']


class JiraConfig:
    def __init__(self, url, email, token):
        self.url = url
        self.email = email
        self.token = token

    @property
    def headers(self):
        return {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        }

    @property
    def auth(self):
        return HTTPBasicAuth(self.email, self.token)


_CONFIG = JiraConfig(f"{os.getenv('ATLASSIAN_URL')}/rest/api/3", os.getenv('ATLASSIAN_EMAIL'), os.getenv('ATLASSIAN_TOKEN'))


@cache
def get_project_name(project_key: str) -> str:
    response = requests.get(f'{_CONFIG.url}/project/{project_key}', auth=_CONFIG.auth)

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
        f'{_CONFIG.url}/issue/{issue_key}/worklog',
        data=payload,
        headers=_CONFIG.headers,
        auth=_CONFIG.auth
    )

    return response.ok


def get_jira_open_issues() -> List[dict]:
    response = requests.request(
        'GET',
        f'{_CONFIG.url}/search?jql=assignee="{_CONFIG.email}"',
        headers=_CONFIG.headers,
        auth=_CONFIG.auth
    )
    r = response.json()

    open_issues = []
    for issue in r['issues']:
        status = issue['fields']['status']['name']
        if status in OPEN_ISSUE_STATUS:
            summary: str = issue['fields']['summary']
            summary = f'"{summary}"'
            open_issues.append({'task': issue['key'], 'description': summary})

    return open_issues
