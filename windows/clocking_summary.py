import datetime

from PySide6 import QtGui
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QTextEdit, QVBoxLayout, QWidget

from services.clockify_api import push_worklog_to_clockify, update_time_entry_in_clockify
from services.config_manager import get_config_manager
from services.database import (
    ClockingRecord,
    get_clockings_for_date,
    get_task_durations_for_date,
    update_clockify_entry_id,
    update_jira_worklog_id,
)
from services.jira_api import push_worklog_to_jira, update_worklog_in_jira
from services.utils import format_timedelta, format_timedelta_jira

_FMT = "%Y-%m-%d %H:%M"


class ClockingSummary(QWidget):
    def __init__(self, data: list[ClockingRecord]):
        super().__init__()
        self._data = data
        self.setWindowTitle("Clocking Summary")
        self.setMinimumSize(200, 200)

        today = datetime.date.today()
        week_tasks = self.compute_week_task_duration(today)

        main_layout = QVBoxLayout()
        hbox = QHBoxLayout()

        for task in week_tasks:
            vbox = QVBoxLayout()
            vbox.addWidget(QLabel(task['date']), alignment=Qt.AlignmentFlag.AlignTop)
            clockings = QTextEdit(task['clockings'])
            clockings.setReadOnly(True)
            vbox.addWidget(clockings)

            buttons_layout = QHBoxLayout()
            push_button = QPushButton('Push Clockings')
            push_button.clicked.connect(self.push_clockings(task['date']))
            buttons_layout.addWidget(push_button)
            vbox.addLayout(buttons_layout)
            vbox.addWidget(QLabel(task['total']), alignment=Qt.AlignmentFlag.AlignBottom)
            hbox.addLayout(vbox)

        main_layout.addLayout(hbox)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        main_layout.addWidget(self.log_text)
        self.setLayout(main_layout)

    def push_clockings(self, day: str):
        def do_push_clockings():
            self.push_to_jira(day)
            self.push_to_clockify(day)
        return do_push_clockings

    def push_to_jira(self, day: str) -> None:
        config = get_config_manager()
        is_configured, _ = config.is_jira_configured()

        if not is_configured:
            self.log_text.append(
                '<span style="color:red;">Jira is not configured. '
                'Please configure it in Menu → Settings.</span>'
            )
            return

        date = datetime.date.fromisoformat(day)
        self.log_text.append(f'Pushing {day} clocking to Jira worklog ...')

        for r in get_clockings_for_date(day):
            assert r.check_out is not None
            check_in_dt = datetime.datetime.strptime(r.check_in, _FMT)
            check_out_dt = datetime.datetime.strptime(r.check_out, _FMT)
            duration = check_out_dt - check_in_dt
            start_dt = datetime.datetime(date.year, date.month, date.day,
                                         check_in_dt.hour, check_in_dt.minute)
            if r.jira_worklog_id:
                ok = update_worklog_in_jira(r.task, r.jira_worklog_id, start_dt, duration)
            else:
                worklog_id = push_worklog_to_jira(r.task, start_dt, duration)
                ok = worklog_id is not None
                if ok and r.id is not None:
                    update_jira_worklog_id(r.id, worklog_id)
            self.log_pushing_output(duration, ok, r.task)

        self.log_text.append('Done')

    def push_to_clockify(self, day: str) -> None:
        config = get_config_manager()
        is_configured, _ = config.is_clockify_configured()

        if not is_configured:
            self.log_text.append(
                '<span style="color:red;">Clockify is not configured. '
                'Please configure it in Menu → Settings.</span>'
            )
            return

        date = datetime.date.fromisoformat(day)
        self.log_text.append(f'Pushing {day} clocking to Clockify worklog ...')

        for r in get_clockings_for_date(day):
            assert r.check_out is not None
            check_in_dt = datetime.datetime.strptime(r.check_in, _FMT)
            check_out_dt = datetime.datetime.strptime(r.check_out, _FMT)
            duration = check_out_dt - check_in_dt
            start_dt = datetime.datetime(date.year, date.month, date.day,
                                         check_in_dt.hour, check_in_dt.minute)
            end_dt = datetime.datetime(date.year, date.month, date.day,
                                       check_out_dt.hour, check_out_dt.minute)
            if r.clockify_entry_id:
                ok = update_time_entry_in_clockify(r.clockify_entry_id, r.task, start_dt, end_dt)
            else:
                entry_id = push_worklog_to_clockify(r.task, start_dt, end_dt)
                ok = entry_id is not None
                if ok and r.id is not None:
                    update_clockify_entry_id(r.id, entry_id)
            self.log_pushing_output(duration, ok, r.task)

        self.log_text.append('Done')

    def log_pushing_output(self, duration, ok, task):
        log_info = f'Task: {task}, Duration: {format_timedelta_jira(duration)}'
        log_status = 'Success' if ok else 'Fail'
        log_color = 'blue' if ok else 'red'
        self.log_text.append(
            f'<span style="color:{log_color};">{log_info} --> {log_status}</span>'
        )
        QtGui.QGuiApplication.processEvents()

    def compute_task_duration(self, day: datetime.date) -> dict | None:
        durations = get_task_durations_for_date(day.isoformat())
        if not durations:
            return None

        task_string = ''
        for td in durations:
            delta = datetime.timedelta(seconds=td.total_seconds)
            task_string += f'{td.task} -- {format_timedelta_jira(delta)}<br>'

        total_seconds = sum(td.total_seconds for td in durations)
        total_delta = datetime.timedelta(seconds=total_seconds)

        return {
            'date': day.isoformat(),
            'clockings': task_string,
            'total': f'Total -- {format_timedelta(total_delta)}<br>',
        }

    def compute_week_task_duration(self, date: datetime.date):
        current_date = date - datetime.timedelta(days=7)
        task_durations = []
        while current_date <= date:
            task_duration = self.compute_task_duration(current_date)
            if task_duration:
                task_durations.append(task_duration)
            current_date += datetime.timedelta(days=1)
        return task_durations
