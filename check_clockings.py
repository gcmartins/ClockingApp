from typing import Optional

import pandas as pd
import datetime

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QTextEdit

from util import format_timedelta, format_timedelta_jira


class CheckClocking(QWidget):
    def __init__(self, dataframe):
        super().__init__()
        self._dataframe = dataframe
        self.setWindowTitle("Check Clocking")
        self.setMinimumSize(200, 200)

        today = datetime.date.today()
        week_tasks = self.compute_week_task_duration(today)

        hbox = QHBoxLayout()

        for task in week_tasks:
            vbox = QVBoxLayout()
            vbox.addWidget(QLabel(task['date']), alignment=Qt.AlignTop)
            vbox.addWidget(QTextEdit(task['clockings']))
            vbox.addWidget(QLabel(task['total']), alignment=Qt.AlignBottom)

            hbox.addLayout(vbox)

        self.setLayout(hbox)

    def compute_task_duration(self, day: datetime.date) -> Optional[dict]:
        df = self._dataframe
        today_data = df[(df["Date"].dt.date == day) & (pd.isna(df['Check Out']) == False)]
        today_data["Duration"] = today_data["Check Out"] - today_data["Check In"]
        task_duration = today_data.groupby('Task')['Duration'].sum()

        if len(task_duration) == 0:
            return None

        task_day = {}
        task_day['date'] = '{}'.format(day)
        task_string = ''
        for task, duration in zip(task_duration.index, task_duration):
            task_string += '{} -- {}<br>'.format(task, format_timedelta_jira(duration))

        task_day['clockings'] = task_string

        task_day['total'] = '{} -- {}<br>'.format('Total', format_timedelta(task_duration.sum()))

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