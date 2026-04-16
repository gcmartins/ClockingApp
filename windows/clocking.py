import datetime
import logging
from collections.abc import Callable

import resources_rc  # noqa: F401

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpacerItem,
    QStyledItemDelegate,
    QSystemTrayIcon,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from services.clocking_validator import (
    validate_date_format,
    validate_message_format,
    validate_time_format,
)
from services.config_manager import get_config_manager
from services.constants import CLOCKING_HEADER
from services.database import (
    ClockingRecord,
    delete_clocking,
    get_all_clockings,
    get_all_tasks,
    get_open_clocking,
    get_tasks_by_type,
    get_today_completed_seconds,
    insert_clocking,
    mark_stale_open_tasks_closed,
    update_check_out,
    upsert_clocking,
    upsert_tasks,
)
from services.jira_api import get_jira_open_issues
from services.utils import format_timedelta
from windows.clocking_summary import ClockingSummary
from windows.eod_report import EodReport
from windows.settings import SettingsDialog
from windows.task_manager import TaskManagerDialog


class TaskUI:
    def __init__(self, id: str, description: str, button: QPushButton, link_url: str | None = None):
        self.id = id
        self.description = description
        self.button = button
        if link_url:
            self.label = QLabel(f'<a href="{link_url}">{description}</a>')
            self.label.setOpenExternalLinks(True)
        else:
            self.label = QLabel(description)


def get_all_task_ids() -> list:
    """Return task IDs from the DB (non-closed tasks first, then closed)."""
    try:
        return list(dict.fromkeys(t.task for t in get_all_tasks()))
    except Exception as e:
        logging.error(f"Error loading task list: {e}")
        return []


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
        rect = option.rect
        if self._task_ids:
            fm = editor.fontMetrics()
            max_text_width = max(fm.horizontalAdvance(t) for t in self._task_ids)
            min_width = max_text_width + 30  # extra space for the dropdown arrow
            if rect.width() < min_width:
                rect.setWidth(min_width)
        editor.setGeometry(rect)


class MainClocking(QMainWindow):
    EXIT_CODE_REBOOT = 122

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Clocking App")
        self.setWindowIcon(QIcon(':/clock.png'))

        menubar = self.menuBar()
        menu = menubar.addMenu('Menu')

        summary_action = QAction("Clocking Summary", self)
        summary_action.triggered.connect(self.open_check_clocking)

        update_task_action = QAction("Update Open Tasks", self)
        update_task_action.triggered.connect(self.update_open_tasks)

        manage_tasks_action = QAction("Manage Tasks", self)
        manage_tasks_action.triggered.connect(self.open_task_manager)

        eod_report_action = QAction("EOD Report", self)
        eod_report_action.triggered.connect(self.generate_eod_report)

        settings_action = QAction("Settings", self)
        settings_action.triggered.connect(self.open_settings)

        close_action = QAction('Exit', self)
        close_action.setShortcut('Ctrl+Q')
        close_action.triggered.connect(QApplication.quit)

        menu.addAction(summary_action)
        menu.addAction(update_task_action)
        menu.addAction(manage_tasks_action)
        menu.addAction(eod_report_action)
        menu.addSeparator()
        menu.addAction(settings_action)
        menu.addSeparator()
        menu.addAction(close_action)

        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon(':/clock.png'))
        self.tray_icon.setToolTip('ClockingApp')
        self.tray_icon.activated.connect(self.tray_icon_activated)

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

        self.clocking_window = Clocking(self.tray_icon, manage_tasks_callback=self.open_task_manager)
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
            active_ids = {issue["task"] for issue in issues}
            mark_stale_open_tasks_closed(active_ids)
            upsert_tasks(issues)
            self.restart_app()
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Failed to Update Tasks",
                f"Error updating open tasks from Jira: {str(e)}"
            )

    def open_task_manager(self):
        dialog = TaskManagerDialog(self)
        if dialog.exec() == TaskManagerDialog.DialogCode.Accepted:
            self.restart_app()

    def open_check_clocking(self):
        self.check_clocking_window = ClockingSummary(self.clocking_window.data)
        self.check_clocking_window.show()

    def generate_eod_report(self):
        self.eod_report = EodReport(self.clocking_window.data)
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

    def __init__(self, tray_icon: QSystemTrayIcon, manage_tasks_callback: Callable | None = None):
        super().__init__()
        self.tray_icon = tray_icon
        self._manage_tasks_callback = manage_tasks_callback
        self.timer_clocking_label: QLabel | None = None
        self.started_task_id: str | None = None
        self.data: list[ClockingRecord] = []
        self.load_data()
        self._is_checked_out = True
        self._overtime_message_showed = False

        self.timer = QTimer()
        self.worked_hours = datetime.timedelta(0)

        self.setup_ui()

        self.timer.timeout.connect(self.update_time)
        self.timer.start(1000)

    def load_data(self):
        """Load all clocking records from the DB into self.data."""
        try:
            self.data = get_all_clockings()
        except Exception as e:
            self.show_db_error(f"Failed to load clocking data: {str(e)}")
            self.data = []

    def setup_ui(self):
        self.setWindowTitle("Clocking")
        self.setMinimumSize(500, 200)

        self.timer_clocking_label = QLabel(format_timedelta(self.worked_hours))
        self.create_task_buttons()
        self.btn_stop = QPushButton("STOP")

        self.update_buttons()

        vbox = QVBoxLayout()
        hbox = QHBoxLayout()
        hbox.addWidget(QLabel("Timer:"))
        hbox.addWidget(self.timer_clocking_label)
        hbox.addSpacerItem(QSpacerItem(100, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        if self._manage_tasks_callback:
            manage_tasks_btn = QPushButton("Manage Tasks")
            manage_tasks_btn.clicked.connect(self._manage_tasks_callback)
            hbox.addWidget(manage_tasks_btn)
        vbox.addLayout(hbox)
        tasks_container = QWidget()
        tasks_layout = QVBoxLayout(tasks_container)
        tasks_layout.setContentsMargins(0, 0, 0, 0)
        for _, task in self.task_buttons.items():
            hbox = QHBoxLayout()
            hbox.addWidget(task.button)
            hbox.addWidget(task.label)
            tasks_layout.addLayout(hbox)

        tasks_scroll = QScrollArea()
        tasks_scroll.setWidget(tasks_container)
        tasks_scroll.setWidgetResizable(True)
        tasks_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        vbox.addWidget(tasks_scroll)
        vbox.addWidget(self.btn_stop)

        task_ids = get_all_task_ids()
        self._task_delegate = TaskComboDelegate(task_ids, self)

        self.clocking_table = QTableWidget()
        self.clocking_table.setColumnCount(len(CLOCKING_HEADER))
        self.clocking_table.setHorizontalHeaderLabels(CLOCKING_HEADER)
        self.clocking_table.setItemDelegateForColumn(1, self._task_delegate)
        header = self.clocking_table.horizontalHeader()
        for col in range(len(CLOCKING_HEADER)):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        message_col = CLOCKING_HEADER.index("Message")
        header.setSectionResizeMode(message_col, QHeaderView.ResizeMode.Stretch)
        self.clocking_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.clocking_table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked |
            QAbstractItemView.EditTrigger.SelectedClicked |
            QAbstractItemView.EditTrigger.EditKeyPressed
        )
        self.update_table()
        self.clocking_table.itemChanged.connect(self._auto_save)

        self.add_row_btn = QPushButton("Add Row")
        self.add_row_btn.clicked.connect(self.add_row)
        self.delete_row_btn = QPushButton("Delete Row")
        self.delete_row_btn.clicked.connect(self.delete_row)

        btn_hbox = QHBoxLayout()
        btn_hbox.addWidget(self.add_row_btn)
        btn_hbox.addWidget(self.delete_row_btn)

        vbox.addWidget(self.clocking_table)
        vbox.addLayout(btn_hbox)

        self.setLayout(vbox)

        self.btn_stop.clicked.connect(self.record_check_out)

    def _collect_row(self, row_idx: int) -> ClockingRecord:
        """Build a ClockingRecord from a single table row."""
        def cell(col):
            item = self.clocking_table.item(row_idx, col)
            return item.text().strip() if item else ""

        date = cell(0)
        task = cell(1)
        check_in_time = cell(2)   # HH:MM
        check_out_time = cell(3)  # HH:MM or ""
        message = cell(4) or None

        check_in = f"{date} {check_in_time}" if date and check_in_time else ""
        check_out = f"{date} {check_out_time}" if date and check_out_time else None

        item_date = self.clocking_table.item(row_idx, 0)
        existing_id = item_date.data(Qt.ItemDataRole.UserRole) if item_date else None

        return ClockingRecord(
            date=date,
            task=task,
            check_in=check_in,
            check_out=check_out,
            message=message,
            id=existing_id,
        )

    def _collect_rows(self) -> list[ClockingRecord]:
        """Build a list of ClockingRecord from all table rows."""
        return [self._collect_row(i) for i in range(self.clocking_table.rowCount())]

    def _validate_record(self, r: ClockingRecord, row_num: int) -> list[str]:
        """Return a list of validation error strings for the given record."""
        errors = []
        if not r.date:
            errors.append(f"Row {row_num}: Date is empty.")
        elif not validate_date_format(r.date):
            errors.append(f"Row {row_num}: Invalid date '{r.date}'. Expected YYYY-MM-DD.")

        if not r.check_in:
            errors.append(f"Row {row_num}: Check-in time is missing.")
        else:
            if not validate_time_format(r.check_in_time):
                errors.append(f"Row {row_num}: Invalid check-in time '{r.check_in_time}'. Expected HH:MM.")

        if r.check_out:
            check_out_time = r.check_out_time
            if not validate_time_format(check_out_time or ""):
                errors.append(f"Row {row_num}: Invalid check-out time '{check_out_time}'. Expected HH:MM.")
            elif r.check_in and r.check_out < r.check_in:
                errors.append(f"Row {row_num}: Check-out must be after check-in.")

        if not validate_message_format(r.message or ""):
            errors.append(f"Row {row_num}: Invalid message format.")

        if not r.task:
            errors.append(f"Row {row_num}: Task is empty.")

        return errors

    def _revert_row(self, row_idx: int, record: ClockingRecord) -> None:
        """Restore a table row to the given saved record's values."""
        self.clocking_table.blockSignals(True)
        item_date = QTableWidgetItem(record.date)
        item_date.setData(Qt.ItemDataRole.UserRole, record.id)
        self.clocking_table.setItem(row_idx, 0, item_date)
        self.clocking_table.setItem(row_idx, 1, QTableWidgetItem(record.task))
        self.clocking_table.setItem(row_idx, 2, QTableWidgetItem(record.check_in_time))
        self.clocking_table.setItem(row_idx, 3, QTableWidgetItem(record.check_out_time or ""))
        self.clocking_table.setItem(row_idx, 4, QTableWidgetItem(record.message or ""))
        self.clocking_table.blockSignals(False)

    def _auto_save(self, item: QTableWidgetItem) -> None:
        """Upsert the single row that changed instead of rewriting the whole table."""
        row_idx = item.row()
        record = self._collect_row(row_idx)

        # New (unsaved) row: wait until the required fields are all present
        if not record.id and not (record.date and record.task and record.check_in):
            return

        errors = self._validate_record(record, row_idx + 1)
        if errors:
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Icon.Critical)
            msg_box.setWindowTitle("Validation Error")
            msg_box.setText("Failed to save due to validation errors.")
            msg_box.setDetailedText("\n".join(errors))
            msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg_box.exec()
            if row_idx < len(self.data):
                self._revert_row(row_idx, self.data[row_idx])
            return

        try:
            saved_id = upsert_clocking(record)
        except Exception as e:
            self.show_db_error(f"Failed to save clocking data: {str(e)}")
            if row_idx < len(self.data):
                self._revert_row(row_idx, self.data[row_idx])
            return

        saved = ClockingRecord(
            date=record.date,
            task=record.task,
            check_in=record.check_in,
            check_out=record.check_out,
            message=record.message,
            id=saved_id,
        )
        # Store the assigned id into the cell so subsequent edits can find it
        self.clocking_table.blockSignals(True)
        item_date = self.clocking_table.item(row_idx, 0)
        if item_date:
            item_date.setData(Qt.ItemDataRole.UserRole, saved_id)
        self.clocking_table.blockSignals(False)

        if row_idx < len(self.data):
            self.data[row_idx] = saved
        else:
            self.data.append(saved)
        self.update_buttons()

    def update_table(self):
        """Repopulate the clocking table from self.data."""
        self.clocking_table.blockSignals(True)
        self.clocking_table.setRowCount(0)
        for r in self.data:
            row_idx = self.clocking_table.rowCount()
            self.clocking_table.insertRow(row_idx)
            item_date = QTableWidgetItem(r.date)
            item_date.setData(Qt.ItemDataRole.UserRole, r.id)
            self.clocking_table.setItem(row_idx, 0, item_date)
            self.clocking_table.setItem(row_idx, 1, QTableWidgetItem(r.task))
            self.clocking_table.setItem(row_idx, 2, QTableWidgetItem(r.check_in_time))
            self.clocking_table.setItem(row_idx, 3, QTableWidgetItem(r.check_out_time or ""))
            self.clocking_table.setItem(row_idx, 4, QTableWidgetItem(r.message or ""))
        self.clocking_table.blockSignals(False)
        if self.clocking_table.rowCount() > 0:
            self.clocking_table.scrollToBottom()

    def add_row(self):
        row_idx = self.clocking_table.rowCount()
        self.clocking_table.blockSignals(True)
        self.clocking_table.insertRow(row_idx)
        self.clocking_table.setItem(row_idx, 0, QTableWidgetItem(datetime.date.today().isoformat()))
        for col_idx in range(1, len(CLOCKING_HEADER)):
            self.clocking_table.setItem(row_idx, col_idx, QTableWidgetItem(""))
        self.clocking_table.blockSignals(False)
        self.clocking_table.scrollToBottom()
        self.clocking_table.setCurrentCell(row_idx, 1)

    def delete_row(self):
        selected_rows = sorted(
            set(index.row() for index in self.clocking_table.selectedIndexes()),
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
        self.clocking_table.blockSignals(True)
        for row_idx in selected_rows:
            record_id = self.data[row_idx].id if row_idx < len(self.data) else None
            if record_id:
                try:
                    delete_clocking(record_id)
                except Exception as e:
                    self.clocking_table.blockSignals(False)
                    self.show_db_error(f"Failed to delete row: {str(e)}")
                    return
            if row_idx < len(self.data):
                self.data.pop(row_idx)
            self.clocking_table.removeRow(row_idx)
        self.clocking_table.blockSignals(False)
        self.update_buttons()

    def create_task_buttons(self):
        self.task_buttons = {}
        self.create_buttons_from_db()

    def _jira_link_for_task(self, task_id: str) -> str | None:
        config = get_config_manager()
        prefix_str = config.get('JIRA_TASK_PREFIX', '')
        if not prefix_str:
            return None
        base_url = config.get('ATLASSIAN_URL', '').rstrip('/')
        if not base_url:
            return None
        prefixes = [p.strip() for p in prefix_str.split(',') if p.strip()]
        for prefix in prefixes:
            if task_id.upper().startswith(prefix.upper() + '-'):
                return f"{base_url}/browse/{task_id}"
        return None

    def create_buttons_from_db(self):
        try:
            tasks = get_tasks_by_type('open')
            tasks.extend(get_tasks_by_type('fixed'))
        except Exception as e:
            logging.error(f"Error loading tasks from DB: {e}")
            return
        for task_rec in tasks:
            btn_check_in = QPushButton(task_rec.task)
            btn_check_in.setFixedWidth(100)
            btn_check_in.clicked.connect(self.record_check_in(task_rec.task))
            link_url = self._jira_link_for_task(task_rec.task)
            self.task_buttons[task_rec.task] = TaskUI(
                task_rec.task, task_rec.description, btn_check_in, link_url
            )

    def update_buttons(self):
        self.get_today_worked_hours()
        for _, task in self.task_buttons.items():
            task.button.setEnabled(True)
        if self.started_task_id and self.started_task_id in self.task_buttons:
            self.task_buttons[self.started_task_id].button.setEnabled(self._is_checked_out)

        self.btn_stop.setEnabled(not self._is_checked_out)

    def record_check_in(self, task_id: str) -> Callable:
        def do_check_in():
            if not self._is_checked_out:
                self.record_check_out()
            now = datetime.datetime.now()
            date_str = now.date().isoformat()
            check_in_str = f"{date_str} {now.strftime('%H:%M')}"
            insert_clocking(date_str, task_id, check_in_str)
            self.load_data()
            self.started_task_id = task_id
            self.update_buttons()
            self.update_table()
        return do_check_in

    def record_check_out(self):
        open_rec = get_open_clocking()
        if open_rec is None:
            return
        now = datetime.datetime.now()
        started_date = open_rec.date
        end_date = now.date().isoformat()
        end_time = now.strftime("%H:%M")

        assert open_rec.id is not None
        if started_date == end_date:
            update_check_out(open_rec.id, f"{end_date} {end_time}")
        else:
            # Cross-day: close at 23:59, open new row at 00:00
            update_check_out(open_rec.id, f"{started_date} 23:59")
            insert_clocking(end_date, open_rec.task, f"{end_date} 00:00", f"{end_date} {end_time}")

        self.load_data()
        self.update_buttons()
        self.update_table()

    def show_db_error(self, message: str):
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Icon.Critical)
        msg_box.setWindowTitle("Database Error")
        msg_box.setText(message)
        msg_box.setInformativeText("Your data may not have been saved. Please check the application.")
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg_box.exec()

    def update_time(self):
        self.worked_hours = self.get_today_worked_hours()
        assert self.timer_clocking_label is not None
        self.timer_clocking_label.setText(format_timedelta(self.worked_hours))
        self.warn_if_overtime()

    def get_today_worked_hours(self) -> datetime.timedelta:
        today_str = datetime.date.today().isoformat()
        completed_seconds = get_today_completed_seconds(today_str)
        todays_hours = datetime.timedelta(seconds=completed_seconds)

        open_rec = get_open_clocking()
        self._is_checked_out = True
        if open_rec is not None:
            self._is_checked_out = False
            self.started_task_id = open_rec.task
            check_in_dt = datetime.datetime.strptime(open_rec.check_in, "%Y-%m-%d %H:%M")
            not_completed = datetime.datetime.now() - check_in_dt
            return todays_hours + not_completed
        else:
            return todays_hours

    def warn_if_overtime(self) -> None:
        todays_hours = self.worked_hours
        assert self.timer_clocking_label is not None
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
            f"You have worked {format_timedelta(todays_hours)} today.",
            QSystemTrayIcon.MessageIcon.Warning,
        )
