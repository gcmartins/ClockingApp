import datetime
from typing import Optional

import pandas as pd
import os.path

from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSystemTrayIcon, \
    QMenu, QAction
from PyQt5.QtCore import QTimer
from pandas import DataFrame

filename = 'work_hours.csv'
header = ["Date", "Check In", "Check Out"]


class WorkHoursApp(QWidget):
    def __init__(self):
        super().__init__()
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

    def load_dataframe(self):
        self._dataframe = pd.read_csv(filename, parse_dates=["Check In", "Check Out", "Date"])

    def closeEvent(self, event):
        event.ignore()
        self.hide()

    def tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self.showNormal()

    def setup_ui(self):
        self.setWindowTitle("Work Hours App")

        self.lbl_time = QLabel(self.format_timedelta(self.worked_hours))
        self.btn_check_in = QPushButton("Check In")
        self.btn_check_out = QPushButton("Check Out")

        self.update_buttons()

        hbox = QHBoxLayout()
        hbox.addWidget(self.btn_check_in)
        hbox.addWidget(self.btn_check_out)

        vbox = QVBoxLayout()
        vbox.addWidget(self.lbl_time)
        vbox.addLayout(hbox)

        self.setLayout(vbox)

        self.btn_check_in.clicked.connect(self.record_check_in)
        self.btn_check_out.clicked.connect(self.record_check_out)

    def update_buttons(self):
        self.get_today_worked_hours()
        if self._is_checked_out:
            self.btn_check_in.setEnabled(True)
            self.btn_check_out.setEnabled(False)
        else:
            self.btn_check_in.setEnabled(False)
            self.btn_check_out.setEnabled(True)

    def record_check_in(self):
        with open(filename, "a") as f:
            current_time = datetime.datetime.now()
            f.write("{},{},{}\n".format(current_time.date(), current_time.time(), ""))
        self.load_dataframe()
        self.update_buttons()

    def record_check_out(self):
        with open(filename, "r+") as f:
            lines = f.readlines()
            if len(lines) == 0:
                return
            last_line = lines[-1].rstrip('\n').split(',')
            if len(last_line) == 3 and last_line[2] == '':
                last_line[2] = str(datetime.datetime.now().time())
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
    if not os.path.isfile(filename):
        with open(filename, "w") as f:
            f.write(','.join(header) + '\n')
    app = QApplication([])
    widget = WorkHoursApp()
    widget.show()
    app.exec_()
