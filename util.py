import datetime
import json
import os

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


def push_worklog_to_jira(issue_key, start_datetime, end_datetime, comment):
    payload = json.dumps({
        'timeSpentSeconds': (end_datetime - start_datetime).total_seconds(),
        'comment': {
            'type': 'doc',
            'version': 1,
            'content': [
                {
                    'type': 'paragraph',
                    'content': [
                        {
                            'text': comment,
                            'type': 'text'
                        }
                    ]
                }
            ]
        },
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
