import os
from datetime import datetime
from functools import cache
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv

from services.exceptions import ClockingException
from services.jira_api import get_project_name

load_dotenv()


class ClockifyConfig:
    def __init__(self, workspace, api_key):
        self.url = "https://api.clockify.me/api/v1/workspaces"
        self.workspace = workspace
        self.api_key = api_key

    @property
    def headers(self):
        return {
            'content-type': 'application/json',
            'X-Api-Key': self.api_key,
        }


_CONFIG = ClockifyConfig(os.getenv('CLOCKIFY_WORKSPACE'), os.getenv('CLOCKIFY_API_KEY'))


@cache
def find_clockify_project(project_name: str) -> str:
    projects_url = f'{_CONFIG.url}/{_CONFIG.workspace}/projects'
    params = {'name': project_name, 'strict-name-search': True}
    response = requests.get(projects_url, headers=_CONFIG.headers, params=params)
    projects = response.json()

    if not response.ok or len(projects) == 0:
        raise ClockingException()

    return projects[0]['id']


@cache
def find_or_create_clockify_task(project_id: str, task_name: str) -> str:
    tasks_url = f'{_CONFIG.url}/{_CONFIG.workspace}/projects/{project_id}/tasks'
    params = {'name': task_name, 'strict-name-search': True}
    response = requests.get(tasks_url, headers=_CONFIG.headers, params=params)
    tasks = response.json()

    if len(tasks):
        return tasks[0]['id']

    data = {'name': task_name}
    response = requests.post(tasks_url, json=data, headers=_CONFIG.headers)

    if not response.ok:
        raise ClockingException()

    task_id = response.json()['id']
    return task_id


def convert_datetime_to_utc(dt: datetime) -> str:
    dt_in_user_tz = dt.astimezone(ZoneInfo('UTC'))
    formatted_datetime = dt_in_user_tz.strftime('%Y-%m-%dT%H:%M:%S') + 'Z'
    return formatted_datetime


def log_time_in_clockify(
        project_id: str,
        task_id: str,
        task_key: str,
        start_time: datetime,
        end_time: datetime,
) -> bool:
    url = f'{_CONFIG.url}/{_CONFIG.workspace}/time-entries'
    data = {
        'start': convert_datetime_to_utc(start_time),
        'end': convert_datetime_to_utc(end_time),
        'billable': 'true',
        'description': task_key,
        'projectId': project_id,
        'taskId': task_id,
    }
    response = requests.post(url, json=data, headers=_CONFIG.headers)

    return response.ok


def push_worklog_to_clockify(
    task_key: str,
    start_time: datetime,
    end_time: datetime,
) -> bool:

    try:
        project_key = task_key.split('-')[0]
        project_name = get_project_name(project_key)
        project_id = find_clockify_project(project_name)

        task_id = find_or_create_clockify_task(project_id, task_key)
    except ClockingException:
        return False

    return log_time_in_clockify(project_id, task_id, task_key, start_time, end_time)
