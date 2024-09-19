import datetime
from typing import Optional, Callable

import pandas as pd
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QIcon, QTextCursor
from PyQt5.QtWidgets import QWidget, QMainWindow, QMenu, QSystemTrayIcon, QAction, QApplication, QLabel, QPushButton, QVBoxLayout, \
    QHBoxLayout, QSpacerItem, QSizePolicy, QPlainTextEdit, QWidget
from pandas import DataFrame

from models.task_ui import TaskUI
from services.constants import OPEN_TASK_CSV, TASK_HEADER, CLOCKING_CSV, FIXED_TASK_CSV
from services.jira_api import get_jira_open_issues
from services.utils import format_timedelta
from windows.clocking_summary import ClockingSummary


def get_clocking_csv_text() -> str:
    with open(CLOCKING_CSV, "r") as f:
        return f.read()


def save_clocking_csv_file(text: str) -> None:
    with open(CLOCKING_CSV, "w") as f:
        f.write(text)


class MainClocking(QMainWindow):
    EXIT_CODE_REBOOT = 122

    def __init__(self) -> None:
        super().__init__()

        menubar = self.menuBar()
        menu = menubar.addMenu('Menu')

        summary_action = QAction("Clocking Summary", self)
        summary_action.triggered.connect(self.open_check_clocking)

        update_task_action = QAction("Update Open Tasks", self)
        # open_action.setShortcut('Ctrl+O')
        update_task_action.triggered.connect(self.update_open_tasks)

        close_action = QAction('Exit', self)
        close_action.setShortcut('Ctrl+Q')
        close_action.triggered.connect(QApplication.quit)

        menu.addAction(summary_action)
        menu.addAction(update_task_action)
        menu.addSeparator()
        menu.addAction(close_action) 

        # Initialize tray icon
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon('clock.png'))
        self.tray_icon.setToolTip('ClockingApp')
        self.tray_icon.activated.connect(self.tray_icon_activated)

        # Create context menu for tray icon
        self.tray_menu = QMenu()
        open_action = QAction("Clocking", self)
        open_action.triggered.connect(self.showNormal)
        self.tray_menu.addAction(open_action)
        check_clocking_action = QAction("Clocking Summary", self)
        check_clocking_action.triggered.connect(self.open_check_clocking)
        self.tray_menu.addAction(check_clocking_action)
        issues_action = QAction("Update Open Tasks", self)
        issues_action.triggered.connect(self.update_open_tasks)
        self.tray_menu.addAction(issues_action)
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(QApplication.quit)
        self.tray_menu.addAction(exit_action)

        # Set context menu for tray icon
        self.tray_icon.setContextMenu(self.tray_menu)

        # Show tray icon
        self.tray_icon.show()

        self.clocking_window = Clocking(self.tray_icon)
        self.setCentralWidget(self.clocking_window)
    
    def update_open_tasks(self):
        with open(OPEN_TASK_CSV, 'w') as f:
            lines = [','.join(TASK_HEADER) + '\n']
            for issue in get_jira_open_issues():
                lines.append(f'{issue["task"]},{issue["description"]}\n')

            f.writelines(lines)
        self.restart_app()

    def open_check_clocking(self):
        self.check_clocking_window = ClockingSummary(self.clocking_window.dataframe)
        self.check_clocking_window.show()

    def restart_app(self):
        QApplication.exit(self.EXIT_CODE_REBOOT)

    def closeEvent(self, event):
        event.ignore()
        self.hide()

    def tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self.showNormal()
        

class Clocking(QWidget):
    EXIT_CODE_REBOOT = 122
    def __init__(self, tray_icon: QSystemTrayIcon):
        super().__init__()
        self.tray_icon = tray_icon
        self.timer_clocking_label = None
        self.started_task_id: Optional[str] = None
        self.dataframe: Optional[DataFrame] = None
        self.load_dataframe()
        self._is_checked_out = True
        self._overtime_message_showed = False

        self.timer = QTimer()
        self.worked_hours = datetime.timedelta(0)

        self.setup_ui()

        self.timer.timeout.connect(self.update_time)
        self.timer.start(1000)

    def load_dataframe(self):
        self.dataframe = pd.read_csv(CLOCKING_CSV, parse_dates=["Date", "Check In", "Check Out"])

    def setup_ui(self):
        self.setWindowTitle("Clocking")
        self.setMinimumSize(200, 200)

        self.timer_clocking_label = QLabel(format_timedelta(self.worked_hours))
        self.create_task_buttons()
        self.btn_stop = QPushButton("STOP")

        self.update_buttons()

        vbox = QVBoxLayout()
        hbox = QHBoxLayout()
        hbox.addWidget(QLabel("Timer:"))
        hbox.addWidget(self.timer_clocking_label)
        hbox.addSpacerItem(QSpacerItem(100, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        vbox.addLayout(hbox)
        for _, task in self.task_buttons.items():
            hbox = QHBoxLayout()
            hbox.addWidget(task.button)
            hbox.addWidget(task.label)
            vbox.addLayout(hbox)
        vbox.addWidget(self.btn_stop)

        self.csv_text = QPlainTextEdit()
        self.update_csv_text()
        self.save_csv_btn = QPushButton("Update CSV")
        self.save_csv_btn.clicked.connect(self.save_csv_file)
        vbox.addWidget(self.csv_text)
        vbox.addWidget(self.save_csv_btn)

        self.setLayout(vbox)

        self.btn_stop.clicked.connect(self.record_check_out)

    def save_csv_file(self):
        save_clocking_csv_file(self.csv_text.toPlainText())
        self.load_dataframe()
        self.update_buttons()

    def update_csv_text(self):
        self.csv_text.setPlainText(get_clocking_csv_text())
        cursor = self.csv_text.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.csv_text.setTextCursor(cursor)

    def create_task_buttons(self):
        self.task_buttons = {}
        self.create_buttons_from_csv(OPEN_TASK_CSV)
        self.create_buttons_from_csv(FIXED_TASK_CSV)

    def create_buttons_from_csv(self, task_csv: str):
        task_df = pd.read_csv(task_csv, names=["Task", "Description"], header=0)
        for _, task in task_df.iterrows():
            task_id = task['Task']
            btn_check_in = QPushButton(task_id)
            btn_check_in.setFixedWidth(100)
            btn_check_in.clicked.connect(self.record_check_in(task_id))
            self.task_buttons[task_id] = TaskUI(task_id, task['Description'], btn_check_in)

    def update_buttons(self):
        self.get_today_worked_hours()
        for _, task in self.task_buttons.items():
            task.button.setEnabled(True)
        if self.started_task_id:
            self.task_buttons[self.started_task_id].button.setEnabled(self._is_checked_out)

        self.btn_stop.setEnabled(not self._is_checked_out)

    def record_check_in(self, task_id: str) -> Callable:
        def do_check_in():
            if not self._is_checked_out:
                self.record_check_out()
            with open(CLOCKING_CSV, "a") as f:
                current_time = datetime.datetime.now()
                f.write("{},{},{},\n".format(current_time.date(), task_id, current_time.time().strftime("%H:%M")))
            self.load_dataframe()
            self.started_task_id = task_id
            self.update_buttons()
            self.update_csv_text()
        return do_check_in

    def record_check_out(self):
        with open(CLOCKING_CSV, "r+") as f:
            lines = f.readlines()
            if len(lines) == 0:
                return
            last_line = lines[-1].rstrip('\n').split(',')
            if len(last_line) == 4 and last_line[3] == '':
                started_date = last_line[0]
                now_datetime = datetime.datetime.now()
                end_date = now_datetime.date().isoformat()
                end_time = now_datetime.time().strftime("%H:%M")
                if started_date == end_date:
                    last_line[3] = end_time
                    lines[-1] = ','.join(last_line) + '\n'
                else:
                    last_line[3] = '23:59'
                    lines[-1] = ','.join(last_line) + '\n'
                    task_key = last_line[1]
                    lines.append(f'{end_date},{task_key},00:00,{end_time}\n')
                f.seek(0)
                f.writelines(lines)
            else:
                return
        self.load_dataframe()
        self.update_buttons()
        self.update_csv_text()

    def update_time(self):
        self.worked_hours = self.get_today_worked_hours()
        self.timer_clocking_label.setText(format_timedelta(self.worked_hours))
        self.warn_if_overtime()

    def get_today_worked_hours(self) -> datetime.timedelta:
        df = self.dataframe
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

    def warn_if_overtime(self) -> None:
        todays_hours = self.worked_hours
        if todays_hours >= datetime.timedelta(hours=8):
            self.timer_clocking_label.setStyleSheet("color: red")
            if not self._overtime_message_showed:
                self.show_overtime_message(todays_hours)
                self._overtime_message_showed = True
        else:
            self.timer_clocking_label.setStyleSheet("color: black")

    def show_overtime_message(self, todays_hours):
        self.tray_icon.showMessage(
            'Work Overtime',
            "You have worked {} today.".format(format_timedelta(todays_hours)),
            QSystemTrayIcon.Warning,
        )
