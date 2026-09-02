from datetime import datetime
from functools import cache

import requests

from services.config_manager import get_config_manager
from services.exceptions import ClockingException
from services.jira_api import get_project_name

KIMAI_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S"


class KimaiConfig:
    def __init__(self, url, api_token):
        self.url = url.rstrip('/') + '/api'
        self.api_token = api_token

    @property
    def headers(self):
        return {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.api_token}',
        }


def _get_config():
    """Get Kimai configuration from config manager"""
    config = get_config_manager()
    return KimaiConfig(
        config.get('KIMAI_URL'),
        config.get('KIMAI_API_TOKEN')
    )


@cache
def find_kimai_project(project_name: str) -> int:
    config = _get_config()
    projects_url = f'{config.url}/projects'
    params = {'term': project_name}
    response = requests.get(projects_url, headers=config.headers, params=params)
    projects = response.json()

    if not response.ok or len(projects) == 0:
        raise ClockingException()

    return projects[0]['id']


@cache
def find_or_create_kimai_activity(project_id: int, activity_name: str) -> int:
    config = _get_config()
    activities_url = f'{config.url}/activities'
    params = {'project': project_id, 'term': activity_name}
    response = requests.get(activities_url, headers=config.headers, params=params)
    activities = response.json()

    if len(activities):
        return activities[0]['id']

    data = {'name': activity_name, 'project': project_id, 'visible': True}
    response = requests.post(activities_url, json=data, headers=config.headers)

    if not response.ok:
        raise ClockingException()

    return response.json()['id']


def format_kimai_datetime(dt: datetime) -> str:
    return dt.strftime(KIMAI_DATETIME_FORMAT)


def log_time_in_kimai(
    project_id: int,
    activity_id: int,
    description: str,
    start_time: datetime,
    end_time: datetime,
) -> bool:
    config = _get_config()
    url = f'{config.url}/timesheets'
    data = {
        'begin': format_kimai_datetime(start_time),
        'end': format_kimai_datetime(end_time),
        'project': project_id,
        'activity': activity_id,
        'description': description,
    }
    response = requests.post(url, json=data, headers=config.headers)
    return response.ok


def clear_kimai_cache() -> None:
    """Clear cached Kimai API results (call after credential updates)."""
    find_kimai_project.cache_clear()
    find_or_create_kimai_activity.cache_clear()


def push_worklog_to_kimai(
    task_key: str,
    start_time: datetime,
    end_time: datetime,
) -> bool:

    try:
        project_key = task_key.split('-')[0]
        project_name = get_project_name(project_key)
        project_id = find_kimai_project(project_name)

        activity_id = find_or_create_kimai_activity(project_id, task_key)
    except ClockingException:
        return False

    return log_time_in_kimai(project_id, activity_id, task_key, start_time, end_time)
