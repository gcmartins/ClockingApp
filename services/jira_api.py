import datetime
from functools import cache

from jira import JIRA

from services.config_manager import get_config_manager
from services.exceptions import ClockingException

OPEN_ISSUE_STATUS = ['Backlog', 'Review', 'In Progress', 'To Do', 'Triage', 'Blocked']


def get_jira():
    config = get_config_manager()
    user_email = config.get('ATLASSIAN_EMAIL')
    return JIRA(
        config.get('ATLASSIAN_URL'),
        basic_auth=(user_email, config.get('ATLASSIAN_TOKEN')),
    )


@cache
def get_project_name(project_key: str) -> str:
    try:
        project = get_jira().project(project_key, expand='name')
        return project.name
    except Exception as e:
        raise ClockingException('Failed to get Jira project name') from e


def clear_jira_cache() -> None:
    """Clear cached Jira API results (call after credential updates)."""
    get_project_name.cache_clear()


def push_worklog_to_jira(issue_key: str, start_datetime: datetime.datetime, duration: datetime.timedelta) -> bool:
    try:
        t = int(duration.total_seconds())
        timeSpent = str(t)

        get_jira().add_worklog(issue_key, timeSpentSeconds=timeSpent, started=start_datetime)
        return True
    except Exception as e:
        print(f"Error pushing worklog to Jira: {e}")

    return False


def get_jira_open_issues() -> list[dict]:
    config = get_config_manager()
    user_email = config.get('ATLASSIAN_EMAIL')
    issues = get_jira().search_issues(f'assignee="{user_email}"', fields=['status', 'summary'])

    open_issues = []
    for issue in issues:
        status = issue.get_field('status').name
        if status in OPEN_ISSUE_STATUS:
            summary: str = issue.get_field('summary')
            open_issues.append({'task': issue.key, 'description': summary})

    return open_issues
