import datetime


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
