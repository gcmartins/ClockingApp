from typing import Optional

import pandas as pd
import datetime

from PyQt5 import QtGui
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton

from util import format_timedelta, format_timedelta_jira, push_worklog_to_jira


class CheckClocking(QWidget):
    def __init__(self, dataframe):
        super().__init__()
        self._dataframe = dataframe
        self.setWindowTitle("Clocking Summary")
        self.setMinimumSize(200, 200)

        today = datetime.date.today()
        week_tasks = self.compute_week_task_duration(today)

        main_layout = QVBoxLayout()

        hbox = QHBoxLayout()

        for task in week_tasks:
            vbox = QVBoxLayout()
            vbox.addWidget(QLabel(task['date']), alignment=Qt.AlignTop)
            clockings = QTextEdit(task['clockings'])
            clockings.setReadOnly(True)
            vbox.addWidget(clockings)
            jira_button = QPushButton('Push to JIRA')
            jira_button.clicked.connect(self.push_to_jira(task['date']))
            vbox.addWidget(jira_button)
            vbox.addWidget(QLabel(task['total']), alignment=Qt.AlignBottom)
            hbox.addLayout(vbox)

        main_layout.addLayout(hbox)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        main_layout.addWidget(self.log_text)
        self.setLayout(main_layout)

    def push_to_jira(self, day: str):
        date = datetime.date.fromisoformat(day)

        def do_push_to_jira():
            df = self._dataframe
            today_data = df[(df["Date"].dt.date == date) & (pd.isna(df['Check Out']) == False)]
            self.log_text.setText('Pushing to Jira ...<br>')
            for _, data in today_data.iterrows():
                task = data['Task']
                start_datetime: datetime.datetime = data['Check In']
                end_datetime: datetime.datetime = data['Check Out']
                duration = end_datetime - start_datetime
                start_datetime = datetime.datetime(date.year, date.month, date.day, start_datetime.hour, start_datetime.minute)
                ok = push_worklog_to_jira(task, start_datetime, duration)
                log_info = f'task: {task}, duration: {duration}, start: {start_datetime}'
                log_status = 'Success' if ok else 'Fail'
                log_color = 'blue' if ok else 'red'
                text_logging = f'<span style=\"color:{log_color};\">{log_info} --> {log_status}</span><br>'
                self.log_text.append(text_logging)
                QtGui.QGuiApplication.processEvents()

        return do_push_to_jira

    def compute_task_duration(self, day: datetime.date) -> Optional[dict]:
        df = self._dataframe
        today_data = df[(df["Date"].dt.date == day) & (pd.isna(df['Check Out']) == False)]
        today_data["Duration"] = today_data["Check Out"] - today_data["Check In"]
        task_duration = today_data.groupby('Task')['Duration'].sum()

        if len(task_duration) == 0:
            return None

        task_day = {'date': '{}'.format(day)}
        task_string = ''
        for task, duration in zip(task_duration.index, task_duration):
            task_string += '{} -- {}<br>'.format(task, format_timedelta_jira(duration))

        task_day['clockings'] = task_string

        task_day['total'] = 'Total -- {}<br>'.format(format_timedelta(task_duration.sum()))

        return task_day

    def compute_week_task_duration(self, date: datetime.date):
        current_date = date - datetime.timedelta(days=7)

        task_durations = []
        while current_date <= date:
            task_duration = self.compute_task_duration(current_date)
            if task_duration:
                task_durations.append(task_duration)
            current_date += datetime.timedelta(days=1)

        return task_durations