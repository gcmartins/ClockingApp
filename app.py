import datetime
from typing import Optional

import pandas as pd
import os.path

from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSystemTrayIcon, \
    QMenu, QAction
from PyQt5.QtCore import QTimer
from pandas import DataFrame

task_csv = 'task.csv'
clocking_csv = 'work_hours.csv'
header = ["Date", "Task", "Check In", "Check Out"]


class TaskUI:
    def __init__(self, id: str, description: str, button: QPushButton):
        self.id = id
        self.description = description
        self.button = button
        self.button.setToolTip(self.description)
        self.duration: datetime.timedelta = datetime.timedelta(0)


class WorkHoursApp(QWidget):
    def __init__(self):
        super().__init__()
        self.started_task_id: Optional[str] = None
        self._dataframe: Optional[DataFrame] = None
        self.load_dataframe()
        self._is_checked_out = True
        self._overtime_message_showed = False

        self.timer = QTimer()
        self.worked_hours = datetime.timedelta(0)

        self.setup_ui()

        self.timer.timeout.connect(self.update_time)
        self.timer.start(1000)

        # Initialize tray icon
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon('clock.png'))
        self.tray_icon.setToolTip('WorkHoursApp')
        self.tray_icon.activated.connect(self.tray_icon_activated)

        # Create context menu for tray icon
        self.tray_menu = QMenu()
        open_action = QAction("Open", self)
        open_action.triggered.connect(self.showNormal)
        self.tray_menu.addAction(open_action)
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(QApplication.quit)
        self.tray_menu.addAction(exit_action)

        # Set context menu for tray icon
        self.tray_icon.setContextMenu(self.tray_menu)

        # Show tray icon
        self.tray_icon.show()

    def closeEvent(self, event):
        event.ignore()
        self.hide()

    def load_dataframe(self):
        self._dataframe = pd.read_csv(clocking_csv, parse_dates=["Date", "Check In", "Check Out"])

    def tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self.showNormal()

    def setup_ui(self):
        self.setWindowTitle("Work Hours App")
        self.setMinimumSize(200, 200)

        self.lbl_time = QLabel(self.format_timedelta(self.worked_hours))
        self.create_task_buttons()
        self.btn_stop = QPushButton("STOP")

        self.update_buttons()

        vbox = QVBoxLayout()
        vbox.addWidget(self.lbl_time)
        for _, task in self.task_buttons.items():
            vbox.addWidget(task.button)
        vbox.addWidget(self.btn_stop)

        self.setLayout(vbox)

        self.btn_stop.clicked.connect(self.record_check_out)

    def create_task_buttons(self):
        task_df = pd.read_csv(task_csv, names=["Task", "Description"], header=0)
        self.task_buttons = {}
        for _, task in task_df.iterrows():
            task_id = task['Task']
            btn_check_in = QPushButton(task_id)
            btn_check_in.clicked.connect(self.record_check_in(task_id))
            self.task_buttons[task_id] = TaskUI(task_id, task['Description'], btn_check_in)

    def update_buttons(self):
        self.get_today_worked_hours()
        if self.started_task_id:
            self.task_buttons[self.started_task_id].button.setEnabled(self._is_checked_out)

        self.btn_stop.setEnabled(not self._is_checked_out)

    def record_check_in(self, task_id: str):
        def do_check_in():
            if not self._is_checked_out:
                self.record_check_out()
            with open(clocking_csv, "a") as f:
                current_time = datetime.datetime.now()
                f.write("{},{},{},\n".format(current_time.date(), task_id, current_time.time().strftime("%H:%M:%S")))
            self.load_dataframe()
            self.started_task_id = task_id
            self.update_buttons()
        return do_check_in

    def record_check_out(self):
        with open(clocking_csv, "r+") as f:
            lines = f.readlines()
            if len(lines) == 0:
                return
            last_line = lines[-1].rstrip('\n').split(',')
            if len(last_line) == 4 and last_line[3] == '':
                last_line[3] = str(datetime.datetime.now().time().strftime("%H:%M:%S"))
                lines[-1] = ','.join(last_line) + '\n'
                f.seek(0)
                f.writelines(lines)
            else:
                return
        self.load_dataframe()
        self.update_buttons()

    def update_time(self):
        self.worked_hours = self.get_today_worked_hours()
        self.lbl_time.setText(self.format_timedelta(self.worked_hours))
        self.warn_if_overtime()

    def get_today_worked_hours(self) -> datetime.timedelta:
        df = self._dataframe
        if len(df) == 0:
            return datetime.timedelta(0)
        today = datetime.date.today()
        today_data = df[(df["Date"].dt.date == today) & (pd.isna(df['Check Out']) == False)]
        duration = today_data["Check Out"] - today_data["Check In"]
        todays_hours = duration.sum()

        nan_check_out = df[pd.isna(df['Check Out'])]
        self._is_checked_out = True
        if not nan_check_out.empty:
            self._is_checked_out = False
            self.started_task_id = nan_check_out["Task"].iloc[0]
            not_completed_hours = datetime.datetime.now() - nan_check_out["Check In"].iloc[0]
            return todays_hours + not_completed_hours
        else:
            return todays_hours

    def format_timedelta(self, td: datetime.timedelta) -> str:
        seconds = td.seconds
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return "{:02d}:{:02d}:{:02d}".format(hours, minutes, seconds)

    def warn_if_overtime(self) -> None:
        todays_hours = self.get_today_worked_hours()
        if todays_hours >= datetime.timedelta(hours=8):
            self.lbl_time.setStyleSheet("color: red")
            if not self._overtime_message_showed:
                self.show_overtime_message(todays_hours)
                self._overtime_message_showed = True
        else:
            self.lbl_time.setStyleSheet("color: black")

    def show_overtime_message(self, todays_hours):
        self.tray_icon.showMessage(
            'Work Overtime',
            "You have worked {} today.".format(self.format_timedelta(todays_hours)),
            QSystemTrayIcon.Warning,
        )


if __name__ == '__main__':
    if not os.path.isfile(clocking_csv):
        with open(clocking_csv, "w") as f:
            f.write(','.join(header) + '\n')
    app = QApplication([])
    widget = WorkHoursApp()
    widget.show()
    app.exec_()
