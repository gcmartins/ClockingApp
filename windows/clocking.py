import csv
import datetime
import io
from typing import Optional, Callable

import pandas as pd
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QIcon, QAction
from PySide6.QtWidgets import (
    QWidget, QMainWindow, QMenu, QSystemTrayIcon, QApplication, QLabel,
    QPushButton, QVBoxLayout, QHBoxLayout, QSpacerItem, QSizePolicy,
    QMessageBox, QTableWidget, QTableWidgetItem, QComboBox,
    QAbstractItemView, QStyledItemDelegate, QHeaderView
)
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


def get_all_task_ids() -> list:
    """Return deduplicated task IDs from fixed_tasks.csv then open_tasks.csv."""
    ids = []
    for csv_path in (FIXED_TASK_CSV, OPEN_TASK_CSV):
        try:
            df = pd.read_csv(csv_path, names=TASK_HEADER, header=0)
            ids.extend(df["Task"].dropna().astype(str).tolist())
        except FileNotFoundError:
            pass  # It's okay if a task file doesn't exist.
        except Exception as e:
            # Consider using a proper logger instead of print
            print(f"Error processing task file {csv_path}: {e}")
    return list(dict.fromkeys(ids))


class TaskComboDelegate(QStyledItemDelegate):
    """Delegate that shows an editable QComboBox for the Task column."""

    def __init__(self, task_ids: list, parent=None):
        super().__init__(parent)
        self._task_ids = task_ids

    def createEditor(self, parent, option, index):
        combo = QComboBox(parent)
        combo.addItems(self._task_ids)
        combo.setEditable(True)
        return combo

    def setEditorData(self, editor, index):
        value = index.data(Qt.ItemDataRole.EditRole) or ""
        i = editor.findText(value)
        if i >= 0:
            editor.setCurrentIndex(i)
        else:
            editor.setEditText(value)

    def setModelData(self, editor, model, index):
        model.setData(index, editor.currentText(), Qt.ItemDataRole.EditRole)

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)


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

        task_ids = get_all_task_ids()
        self._task_delegate = TaskComboDelegate(task_ids, self)

        self.csv_table = QTableWidget()
        self.csv_table.setColumnCount(len(CLOCKING_HEADER))
        self.csv_table.setHorizontalHeaderLabels(CLOCKING_HEADER)
        self.csv_table.setItemDelegateForColumn(1, self._task_delegate)
        header = self.csv_table.horizontalHeader()
        for col in range(len(CLOCKING_HEADER)):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        message_col = CLOCKING_HEADER.index("Message")
        header.setSectionResizeMode(message_col, QHeaderView.ResizeMode.Stretch)
        self.csv_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.csv_table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked |
            QAbstractItemView.EditTrigger.SelectedClicked |
            QAbstractItemView.EditTrigger.EditKeyPressed
        )
        self.update_csv_table()

        self.add_row_btn = QPushButton("Add Row")
        self.add_row_btn.clicked.connect(self.add_row)
        self.delete_row_btn = QPushButton("Delete Row")
        self.delete_row_btn.clicked.connect(self.delete_row)
        self.save_csv_btn = QPushButton("Update CSV")
        self.save_csv_btn.clicked.connect(self.save_csv_file)

        btn_hbox = QHBoxLayout()
        btn_hbox.addWidget(self.add_row_btn)
        btn_hbox.addWidget(self.delete_row_btn)
        btn_hbox.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        btn_hbox.addWidget(self.save_csv_btn)

        vbox.addWidget(self.csv_table)
        vbox.addLayout(btn_hbox)

        self.setLayout(vbox)

        self.btn_stop.clicked.connect(self.record_check_out)

    def save_csv_file(self):
        output = io.StringIO()
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(CLOCKING_HEADER)
        for row_idx in range(self.csv_table.rowCount()):
            row_data = []
            for col_idx in range(len(CLOCKING_HEADER)):
                item = self.csv_table.item(row_idx, col_idx)
                row_data.append(item.text().strip() if item else "")
            writer.writerow(row_data)
        csv_content = output.getvalue()

        is_valid, error_message = validate_clocking_csv_format(csv_content)
        if not is_valid:
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Icon.Critical)
            msg_box.setWindowTitle("CSV Validation Error")
            msg_box.setText("Failed to save CSV file due to validation error.")
            msg_box.setDetailedText(error_message)
            msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg_box.exec()
            return

        save_clocking_csv_file(csv_content)
        self.load_dataframe()
        self.update_buttons()
        self.update_csv_table()

        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Icon.Information)
        msg_box.setWindowTitle("CSV Saved")
        msg_box.setText("CSV file has been successfully validated and saved.")
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg_box.exec()

    def update_csv_table(self):
        try:
            csv_content = get_clocking_csv_text()
        except FileNotFoundError:
            self.csv_table.setRowCount(0)
            return
        reader = csv.reader(io.StringIO(csv_content))
        rows = list(reader)
        data_rows = [r for r in rows[1:] if any(field.strip() for field in r)]
        self.csv_table.setRowCount(0)
        for row_data in data_rows:
            while len(row_data) < len(CLOCKING_HEADER):
                row_data.append("")
            row_idx = self.csv_table.rowCount()
            self.csv_table.insertRow(row_idx)
            for col_idx, value in enumerate(row_data[:len(CLOCKING_HEADER)]):
                self.csv_table.setItem(row_idx, col_idx, QTableWidgetItem(value.strip()))
        if self.csv_table.rowCount() > 0:
            self.csv_table.scrollToBottom()

    def add_row(self):
        row_idx = self.csv_table.rowCount()
        self.csv_table.insertRow(row_idx)
        self.csv_table.setItem(row_idx, 0, QTableWidgetItem(datetime.date.today().isoformat()))
        for col_idx in range(1, len(CLOCKING_HEADER)):
            self.csv_table.setItem(row_idx, col_idx, QTableWidgetItem(""))
        self.csv_table.scrollToBottom()
        self.csv_table.setCurrentCell(row_idx, 1)

    def delete_row(self):
        selected_rows = sorted(
            set(index.row() for index in self.csv_table.selectedIndexes()),
            reverse=True,
        )
        if not selected_rows:
            QMessageBox.information(self, "No Selection", "Please select a row to delete.")
            return
        confirm = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Delete {len(selected_rows)} row(s)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        for row_idx in selected_rows:
            self.csv_table.removeRow(row_idx)

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
            self.update_csv_table()
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
                    lines.append(f'{end_date},{task_key},00:00,{end_time},\n')
                f.seek(0)
                f.writelines(lines)
            else:
                return
        self.load_dataframe()
        self.update_buttons()
        self.update_csv_table()

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
