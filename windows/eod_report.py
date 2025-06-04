import datetime
from typing import Optional, Dict, List

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTextEdit

import pandas as pd

from services.constants import OPEN_TASK_CSV, TASK_HEADER, FIXED_TASK_CSV


class EodReport(QWidget):
    def __init__(self, dataframe):
        super().__init__()
        self._dataframe = dataframe
        self.setWindowTitle("EOD Report")
        self.setMinimumSize(600, 400)

        today = datetime.date.today()
        task_messages = self.get_task_messages(today)

        main_layout = QVBoxLayout()

        self.report_text = QTextEdit()
        self.report_text.setReadOnly(True)
        main_layout.addWidget(self.report_text)
        self.setLayout(main_layout)

        if task_messages:
            self.display_task_massages(task_messages)

    def get_task_messages(self, day: datetime.date) -> Optional[dict]:
        df = self._dataframe
        today_data = df[df["Date"].dt.date == day]

        if len(today_data) == 0:
            return None

        task_messages = {}

        for _, data in today_data.iterrows():
            task = data["Task"]
            message = data["Message"]
            if task_messages.get(task) is None:
                task_messages[task] = []

            if not pd.isnull(message):
                task_messages[task].append(message)

        return task_messages

    def display_task_massages(self, task_messages: Dict[str, List[str]]):
        task_descriptions = self.get_task_descriptions()

        report = ''
        for task, messages in task_messages.items():
            description = task_descriptions.get(task, '')
            report += f'{task}:{description}\n'
            if messages:
                for m in messages:
                    for n in m.split("\\n"):
                        report += f'- {n}\n'

        self.report_text.append(report)

    def get_task_descriptions(self):
        open_task_df = pd.read_csv(OPEN_TASK_CSV, names=TASK_HEADER, header=0)
        fixed_task_df = pd.read_csv(FIXED_TASK_CSV, names=TASK_HEADER, header=0)
        task_descriptions = {}
        for _, data in open_task_df.iterrows():
            task_descriptions[data["Task"]] = data["Description"]

        for _, data in fixed_task_df.iterrows():
            task_descriptions[data["Task"]] = data["Description"]

        return task_descriptions



