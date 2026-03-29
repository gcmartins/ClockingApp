import datetime
from typing import Optional, Callable

import pandas as pd
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QIcon, QAction
from PySide6.QtWidgets import (
    QWidget, QMainWindow, QMenu, QSystemTrayIcon, QApplication,
    QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QSpacerItem,
    QSizePolicy, QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView,
)
from pandas import DataFrame

from models.task_ui import TaskUI
from services import database as db
from services.jira_api import get_jira_open_issues
from services.utils import format_timedelta
from services.config_manager import get_config_manager
from windows.clocking_summary import ClockingSummary
from windows.eod_report import EodReport
from windows.settings import SettingsDialog

# Column indices for the records table
_COL_DATE = 0
_COL_TASK = 1
_COL_IN = 2
_COL_OUT = 3
_COL_MSG = 4
_COLUMNS = ["Date", "Task", "Check In", "Check Out", "Message"]


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

        self.tray_icon.setContextMenu(self.tray_menu)
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
                db.replace_tasks('open_tasks', [(i["task"], i["description"]) for i in issues])
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
        try:
            self.dataframe = db.get_work_hours_df()
        except Exception as e:
            QMessageBox.critical(None, "Database Error", f"Failed to load records: {str(e)}")
            self.dataframe = pd.DataFrame(columns=["Date", "Task", "Check In", "Check Out", "Message"])

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
        self.btn_stop.clicked.connect(self.record_check_out)

        # --- Records table ---
        self.records_table = QTableWidget()
        self.records_table.setColumnCount(len(_COLUMNS))
        self.records_table.setHorizontalHeaderLabels(_COLUMNS)
        self.records_table.horizontalHeader().setSectionResizeMode(
            _COL_MSG, QHeaderView.ResizeMode.Stretch
        )
        self.records_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.records_table.setEditTriggers(QTableWidget.EditTrigger.DoubleClicked)
        self.refresh_records_table()

        # Table action buttons
        tbl_btns = QHBoxLayout()
        self.btn_add_row = QPushButton("Add Row")
        self.btn_save = QPushButton("Save Changes")
        self.btn_delete_row = QPushButton("Delete Row")
        self.btn_refresh = QPushButton("Refresh")
        self.btn_add_row.clicked.connect(self._add_row)
        self.btn_save.clicked.connect(self._save_changes)
        self.btn_delete_row.clicked.connect(self._delete_row)
        self.btn_refresh.clicked.connect(self._refresh)
        tbl_btns.addWidget(self.btn_add_row)
        tbl_btns.addWidget(self.btn_save)
        tbl_btns.addWidget(self.btn_delete_row)
        tbl_btns.addWidget(self.btn_refresh)

        vbox.addWidget(self.records_table)
        vbox.addLayout(tbl_btns)

        self.setLayout(vbox)

    # ------------------------------------------------------------------
    # Records table helpers
    # ------------------------------------------------------------------

    def refresh_records_table(self):
        rows = db.get_work_hours_rows()
        self.records_table.setRowCount(len(rows))
        for r, (row_id, date, task, check_in, check_out, message) in enumerate(rows):
            self._set_table_row(r, row_id, date, task, check_in, check_out or '', message or '')

    def _set_table_row(self, r: int, row_id: Optional[int],
                       date: str, task: str, check_in: str,
                       check_out: str, message: str):
        date_item = QTableWidgetItem(date)
        if row_id is not None:
            date_item.setData(Qt.ItemDataRole.UserRole, row_id)
        self.records_table.setItem(r, _COL_DATE, date_item)

        task_item = QTableWidgetItem(task)
        task_item.setFlags(task_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.records_table.setItem(r, _COL_TASK, task_item)

        self.records_table.setItem(r, _COL_IN, QTableWidgetItem(check_in))
        self.records_table.setItem(r, _COL_OUT, QTableWidgetItem(check_out))
        self.records_table.setItem(r, _COL_MSG, QTableWidgetItem(message))

    def _add_row(self):
        today = datetime.date.today().isoformat()
        r = self.records_table.rowCount()
        self.records_table.insertRow(r)
        # No row_id yet — will be assigned on save
        self._set_table_row(r, None, today, '', '', '', '')
        # Task column needs to be editable for new rows
        task_item = self.records_table.item(r, _COL_TASK)
        task_item.setFlags(task_item.flags() | Qt.ItemFlag.ItemIsEditable)
        self.records_table.scrollToBottom()
        self.records_table.editItem(self.records_table.item(r, _COL_TASK))

    def _save_changes(self):
        for r in range(self.records_table.rowCount()):
            date_item = self.records_table.item(r, _COL_DATE)
            if date_item is None:
                continue
            row_id = date_item.data(Qt.ItemDataRole.UserRole)
            date = (date_item.text() or '').strip()
            task = (self.records_table.item(r, _COL_TASK).text() or '').strip()
            check_in = (self.records_table.item(r, _COL_IN).text() or '').strip()
            check_out = (self.records_table.item(r, _COL_OUT).text() or '').strip()
            message = (self.records_table.item(r, _COL_MSG).text() or '').strip()

            if not date or not task or not check_in:
                continue  # skip incomplete rows

            if row_id is not None:
                db.update_work_hours_row(row_id, date, task, check_in, check_out, message)
            else:
                new_id = db.insert_work_hours_row(date, task, check_in, check_out, message)
                date_item.setData(Qt.ItemDataRole.UserRole, new_id)
                # Make Task read-only now that it's persisted
                task_item = self.records_table.item(r, _COL_TASK)
                task_item.setFlags(task_item.flags() & ~Qt.ItemFlag.ItemIsEditable)

        self.load_dataframe()
        self.update_buttons()

    def _delete_row(self):
        selected = self.records_table.selectedItems()
        if not selected:
            return
        r = self.records_table.currentRow()
        check_out_item = self.records_table.item(r, _COL_OUT)
        if check_out_item and check_out_item.text().strip() == '':
            QMessageBox.warning(
                self,
                "Cannot Delete",
                "This row is an active clocking session. Please stop the timer before deleting it."
            )
            return

        date_item = self.records_table.item(r, _COL_DATE)
        row_id = date_item.data(Qt.ItemDataRole.UserRole) if date_item else None
        if row_id is not None:
            db.delete_work_hours_row(row_id)
        self.records_table.removeRow(r)
        self.load_dataframe()
        self.update_buttons()

    def _refresh(self):
        self.refresh_records_table()
        self.load_dataframe()
        self.update_buttons()

    # ------------------------------------------------------------------
    # Task buttons
    # ------------------------------------------------------------------

    def create_task_buttons(self):
        self.task_buttons = {}
        self._create_buttons_from_table('open_tasks')
        self._create_buttons_from_table('fixed_tasks')

    def _create_buttons_from_table(self, table: str):
        task_df = db.get_tasks_df(table)
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

    # ------------------------------------------------------------------
    # Clocking operations
    # ------------------------------------------------------------------

    def record_check_in(self, task_id: str) -> Callable:
        def do_check_in():
            if not self._is_checked_out:
                self.record_check_out()
            current_time = datetime.datetime.now()
            db.append_check_in(
                current_time.date().isoformat(),
                task_id,
                current_time.time().strftime("%H:%M"),
            )
            self.load_dataframe()
            self.started_task_id = task_id
            self.update_buttons()
            self.refresh_records_table()
        return do_check_in

    def record_check_out(self):
        session = db.get_active_session()
        if session is None:
            return
        row_id, started_date, task_key, _ = session
        now = datetime.datetime.now()
        end_date = now.date().isoformat()
        end_time = now.time().strftime("%H:%M")

        conn = db.get_connection()
        if started_date == end_date:
            with conn:
                conn.execute(
                    "UPDATE work_hours SET check_out = ? WHERE id = ?",
                    (end_time, row_id),
                )
        else:
            with conn:
                conn.execute(
                    "UPDATE work_hours SET check_out = '23:59' WHERE id = ?",
                    (row_id,),
                )
                conn.execute(
                    "INSERT INTO work_hours (date, task, check_in, check_out, message) VALUES (?, ?, '00:00', ?, '')",
                    (end_date, task_key, end_time),
                )

        self.load_dataframe()
        self.update_buttons()
        self.refresh_records_table()

    # ------------------------------------------------------------------
    # Timer & overtime
    # ------------------------------------------------------------------

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
