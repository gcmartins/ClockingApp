import datetime

from PySide6.QtWidgets import QTextEdit, QVBoxLayout, QWidget

from services.database import ClockingRecord, get_task_descriptions


class EodReport(QWidget):
    def __init__(self, data: list[ClockingRecord]):
        super().__init__()
        self._data = data
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
            self.display_task_messages(task_messages)

    def get_task_messages(self, day: datetime.date) -> dict[str, list[str]] | None:
        today_data = [r for r in self._data if r.date == day.isoformat()]
        if not today_data:
            return None

        task_messages: dict[str, list[str]] = {}
        for r in today_data:
            if r.task not in task_messages:
                task_messages[r.task] = []
            if r.message:
                task_messages[r.task].append(r.message)

        return task_messages

    def display_task_messages(self, task_messages: dict[str, list[str]]):
        descriptions = get_task_descriptions()
        report = ''
        for task, messages in task_messages.items():
            description = descriptions.get(task, '')
            report += f'{task}:{description}\n'
            if messages:
                for m in messages:
                    for n in m.split("\\n"):
                        report += f'- {n}\n'
        self.report_text.append(report)
