import csv
import datetime
import io
import os
from typing import Optional, Callable

import pandas as pd
from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon, QTextCursor, QAction
from PySide6.QtWidgets import QWidget, QMainWindow, QMenu, QSystemTrayIcon, QApplication, QLabel, QPushButton, QVBoxLayout, \
    QHBoxLayout, QSpacerItem, QSizePolicy, QPlainTextEdit, QWidget, QMessageBox
from pandas import DataFrame

from models.task_ui import TaskUI
from services.constants import OPEN_TASK_CSV, TASK_HEADER, CLOCKING_CSV, FIXED_TASK_CSV, CLOCKING_HEADER
from services.csv_validator import validate_clocking_csv_format
from services.jira_api import get_jira_open_issues
from services.utils import format_timedelta
from services.config_manager import get_config_manager
from windows.clocking_summary import ClockingSummary
from windows.eod_report import EodReport
from windows.settings import SettingsDialog


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
        self.setWindowTitle("Clocking App")

        menubar = self.menuBar()
        menu = menubar.addMenu('Menu')

        summary_action = QAction("Clocking Summary", self)
        summary_action.triggered.connect(self.open_check_clocking)

        update_task_action = QAction("Update Open Tasks", self)
        # open_action.setShortcut('Ctrl+O')
        update_task_action.triggered.connect(self.update_open_tasks)

        eod_report_action = QAction("EOD Report", self)
        eod_report_action.triggered.connect(self.generate_eod_report)

        settings_action = QAction("Settings", self)
        settings_action.triggered.connect(self.open_settings)

        close_action = QAction('Exit', self)
        close_action.setShortcut('Ctrl+Q')
        close_action.triggered.connect(QApplication.quit)

        menu.addAction(summary_action)
        menu.addAction(update_task_action)
        menu.addAction(eod_report_action)
        menu.addSeparator()
        menu.addAction(settings_action)
        menu.addSeparator()
        menu.addAction(close_action) 

        # Initialize tray icon
        self.tray_icon = QSystemTrayIcon(self)
        _icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'clock.png')
        self.tray_icon.setIcon(QIcon(_icon_path))
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
        config = get_config_manager()
        is_configured, _ = config.is_jira_configured()
        
        if not is_configured:
            QMessageBox.warning(
                self,
                "Jira Not Configured",
                "Please configure Jira API settings in Menu → Settings to use this feature."
            )
            return
        
        try:
            issues = get_jira_open_issues()
            if len(issues) != 0:
                output = io.StringIO()
                writer = csv.writer(output)
                writer.writerow(TASK_HEADER)
                for issue in issues:
                    writer.writerow([issue["task"], issue["description"]])
                with open(OPEN_TASK_CSV, 'w') as f:
                    f.write(output.getvalue())
            self.restart_app()
        except Exception as e:
            QMessageBox.critical(
                self,
                "Failed to Update Tasks",
                f"Error updating open tasks from Jira: {str(e)}"
            )

    def open_check_clocking(self):
        self.check_clocking_window = ClockingSummary(self.clocking_window.dataframe)
        self.check_clocking_window.show()

    def generate_eod_report(self):
        self.eod_report = EodReport(self.clocking_window.dataframe)
        self.eod_report.show()

    def open_settings(self):
        settings_dialog = SettingsDialog(self)
        if settings_dialog.exec() == SettingsDialog.DialogCode.Accepted:
            # Settings were saved, ask if user wants to restart
            reply = QMessageBox.question(
                self,
                "Restart Required",
                "Settings have been updated. Would you like to restart the application to apply changes?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.restart_app()

    def restart_app(self):
        QApplication.exit(self.EXIT_CODE_REBOOT)

    def closeEvent(self, event):
        event.ignore()
        self.hide()

    def tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
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
        # Validate CSV before loading
        try:
            csv_content = get_clocking_csv_text()
            is_valid, error = validate_clocking_csv_format(csv_content)
            if not is_valid:
                self.show_csv_error(f"CSV file is malformed: {error}")
                # Try to load anyway but user needs to fix it
                self.dataframe = pd.DataFrame(columns=CLOCKING_HEADER)
                return
            dataframe = pd.read_csv(CLOCKING_CSV)
            dataframe["Date"] = pd.to_datetime(dataframe["Date"], format="%Y-%m-%d", errors="coerce")

            # Build full datetimes using Date + HH:MM time strings for duration calculations.
            date_part = dataframe["Date"].dt.strftime("%Y-%m-%d")
            dataframe["Check In"] = pd.to_datetime(
                date_part + " " + dataframe["Check In"].astype("string"),
                format="%Y-%m-%d %H:%M",
                errors="coerce",
            )
            dataframe["Check Out"] = pd.to_datetime(
                date_part + " " + dataframe["Check Out"].astype("string"),
                format="%Y-%m-%d %H:%M",
                errors="coerce",
            )
            self.dataframe = dataframe
        except Exception as e:
            self.show_csv_error(f"Failed to load CSV file: {str(e)}")
            self.dataframe = pd.DataFrame(columns=CLOCKING_HEADER)

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
        hbox.addSpacerItem(QSpacerItem(100, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
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
        csv_content = self.csv_text.toPlainText()
        
        # Validate CSV format before saving
        is_valid, error_message = validate_clocking_csv_format(csv_content)
        
        if not is_valid:
            # Show error message to user
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Icon.Critical)
            msg_box.setWindowTitle("CSV Validation Error")
            msg_box.setText("Failed to save CSV file due to validation error.")
            msg_box.setDetailedText(error_message)
            msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg_box.exec()
            return
        
        # If validation passes, save the file
        save_clocking_csv_file(csv_content)
        self.load_dataframe()
        self.update_buttons()
        
        # Show success message
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Icon.Information)
        msg_box.setWindowTitle("CSV Saved")
        msg_box.setText("CSV file has been successfully validated and saved.")
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg_box.exec()

    def update_csv_text(self):
        self.csv_text.setPlainText(get_clocking_csv_text())
        cursor = self.csv_text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.csv_text.setTextCursor(cursor)

    def create_task_buttons(self):
        self.task_buttons = {}
        self.create_buttons_from_csv(OPEN_TASK_CSV)
        self.create_buttons_from_csv(FIXED_TASK_CSV)

    def create_buttons_from_csv(self, task_csv: str):
        task_df = pd.read_csv(task_csv, names=TASK_HEADER, header=0)
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
                f.write("{},{},{},,\n".format(current_time.date(), task_id, current_time.time().strftime("%H:%M")))
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
            if len(last_line) == 5 and last_line[3] == '':
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

    def show_csv_error(self, message: str):
        """Display CSV error to user."""
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Icon.Critical)
        msg_box.setWindowTitle("CSV Error")
        msg_box.setText(message)
        msg_box.setInformativeText("Please fix the CSV file manually or it may cause data corruption.")
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg_box.exec()

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
            self.timer_clocking_label.setStyleSheet("color: green")

    def show_overtime_message(self, todays_hours):
        self.tray_icon.showMessage(
            'Work Overtime',
            "You have worked {} today.".format(format_timedelta(todays_hours)),
            QSystemTrayIcon.MessageIcon.Warning,
        )
