"""Tests for the task management workflow.

Covers:
- SQLite migration from legacy CSV files          (app._migrate_to_sqlite)
- Time-formatting utilities                        (services/utils.py)
- ClockingException                               (services/exceptions.py)
- TaskManagerDialog table/save logic              (windows/task_manager.py)
"""
import csv
import datetime
import os

import pytest

from services.constants import TASK_HEADER, TASK_TYPES
from services.database import ClockingRecord, TaskRecord, init_db, get_all_tasks, get_all_clockings
from services.exceptions import ClockingException
from services.utils import format_timedelta, format_timedelta_jira


# ---------------------------------------------------------------------------
# Fixture: isolated DB
# ---------------------------------------------------------------------------

@pytest.fixture
def db_env(tmp_path, monkeypatch):
    import services.database as db_module
    db_path = str(tmp_path / 'clocking.db')
    monkeypatch.setattr(db_module, 'DB_FILE', db_path)
    init_db()
    monkeypatch.chdir(tmp_path)
    return tmp_path


# ---------------------------------------------------------------------------
# services/utils.py
# ---------------------------------------------------------------------------

class TestFormatTimedelta:
    def test_zero(self):
        assert format_timedelta(datetime.timedelta(0)) == "00:00:00"

    def test_hours_minutes_seconds(self):
        assert format_timedelta(datetime.timedelta(hours=1, minutes=30, seconds=45)) == "01:30:45"

    def test_exact_hours(self):
        assert format_timedelta(datetime.timedelta(hours=8)) == "08:00:00"

    def test_near_full_day(self):
        assert format_timedelta(datetime.timedelta(hours=23, minutes=59, seconds=59)) == "23:59:59"

    def test_only_minutes(self):
        assert format_timedelta(datetime.timedelta(minutes=5)) == "00:05:00"


class TestFormatTimedeltaJira:
    def test_zero(self):
        assert format_timedelta_jira(datetime.timedelta(0)) == "00h 00m"

    def test_hours_and_minutes(self):
        assert format_timedelta_jira(datetime.timedelta(hours=2, minutes=15)) == "02h 15m"

    def test_seconds_are_ignored(self):
        assert format_timedelta_jira(datetime.timedelta(hours=1, minutes=30, seconds=59)) == "01h 30m"

    def test_single_digit_padded(self):
        assert format_timedelta_jira(datetime.timedelta(hours=3, minutes=5)) == "03h 05m"


# ---------------------------------------------------------------------------
# services/exceptions.py
# ---------------------------------------------------------------------------

class TestClockingException:
    def test_is_exception_subclass(self):
        assert issubclass(ClockingException, Exception)

    def test_can_be_raised_and_caught(self):
        with pytest.raises(ClockingException):
            raise ClockingException("something went wrong")

    def test_message_preserved(self):
        assert str(ClockingException("test message")) == "test message"

    def test_can_be_raised_without_message(self):
        with pytest.raises(ClockingException):
            raise ClockingException()


# ---------------------------------------------------------------------------
# app._migrate_to_sqlite
# ---------------------------------------------------------------------------

from app import _migrate_to_sqlite  # noqa: E402


class TestMigrateToSqlite:
    def test_noop_when_db_already_populated(self, db_env):
        from services.database import save_tasks
        save_tasks([TaskRecord('EXISTING', 'Already here', 'fixed')])
        # Write a tasks.csv that would add more rows if migration ran again
        (db_env / 'tasks.csv').write_text(
            "Task,Description,Task Type\nNEW-TASK,Should not appear,fixed\n"
        )
        _migrate_to_sqlite()
        tasks = get_all_tasks()
        assert len(tasks) == 1
        assert tasks[0].task == 'EXISTING'

    def test_creates_placeholder_when_no_legacy_files(self, db_env):
        _migrate_to_sqlite()
        tasks = get_all_tasks()
        assert len(tasks) == 1
        assert tasks[0].task == 'TASK-KEY'
        assert tasks[0].task_type == 'fixed'

    def test_migrates_from_tasks_csv(self, db_env):
        (db_env / 'tasks.csv').write_text(
            "Task,Description,Task Type\n"
            "TASK-1,First task,fixed\n"
            "TASK-2,Second task,open\n"
        )
        _migrate_to_sqlite()
        tasks = {t.task: t for t in get_all_tasks()}
        assert 'TASK-1' in tasks
        assert tasks['TASK-1'].task_type == 'fixed'
        assert 'TASK-2' in tasks
        assert tasks['TASK-2'].task_type == 'open'

    def test_migrates_fixed_tasks_only(self, db_env):
        (db_env / 'fixed_tasks.csv').write_text(
            "Task,Description\nFIXED-1,Fixed task one\nFIXED-2,Fixed task two\n"
        )
        _migrate_to_sqlite()
        tasks = {t.task: t for t in get_all_tasks()}
        assert tasks['FIXED-1'].task_type == 'fixed'
        assert tasks['FIXED-2'].task_type == 'fixed'

    def test_migrates_open_tasks_only(self, db_env):
        (db_env / 'open_tasks.csv').write_text(
            "Task,Description\nOPEN-1,Open task one\n"
        )
        _migrate_to_sqlite()
        tasks = {t.task: t for t in get_all_tasks()}
        assert tasks['OPEN-1'].task_type == 'open'

    def test_migrates_both_legacy_files(self, db_env):
        (db_env / 'fixed_tasks.csv').write_text("Task,Description\nFIXED-1,Fixed one\n")
        (db_env / 'open_tasks.csv').write_text("Task,Description\nOPEN-1,Open one\n")
        _migrate_to_sqlite()
        tasks = {t.task: t for t in get_all_tasks()}
        assert tasks['FIXED-1'].task_type == 'fixed'
        assert tasks['OPEN-1'].task_type == 'open'

    def test_skips_rows_with_empty_task(self, db_env):
        (db_env / 'fixed_tasks.csv').write_text(
            "Task,Description\n,Empty task id\nVALID-1,Valid task\n"
        )
        _migrate_to_sqlite()
        tasks = get_all_tasks()
        assert len(tasks) == 1
        assert tasks[0].task == 'VALID-1'

    def test_migrates_work_hours_csv(self, db_env):
        today = datetime.date.today().isoformat()
        (db_env / 'tasks.csv').write_text(
            "Task,Description,Task Type\nTASK-1,A task,fixed\n"
        )
        (db_env / 'work_hours.csv').write_text(
            f"Date,Task,Check In,Check Out,Message\n"
            f"{today},TASK-1,09:00,10:00,done\n"
        )
        _migrate_to_sqlite()
        clockings = get_all_clockings()
        assert len(clockings) == 1
        assert clockings[0].task == 'TASK-1'
        assert clockings[0].check_in == f"{today} 09:00"
        assert clockings[0].check_out == f"{today} 10:00"


# ---------------------------------------------------------------------------
# windows/task_manager.TaskManagerDialog
# ---------------------------------------------------------------------------

from windows.task_manager import TaskManagerDialog  # noqa: E402
from PySide6.QtWidgets import QTableWidgetItem, QMessageBox  # noqa: E402


@pytest.fixture()
def dialog(qt_app, db_env):
    """TaskManagerDialog against an isolated DB."""
    d = TaskManagerDialog()
    yield d
    d.destroy()


class TestTaskManagerDialogLoad:
    def test_empty_table_when_no_tasks(self, dialog):
        assert dialog._table.rowCount() == 0

    def test_loads_rows_from_db(self, qt_app, db_env):
        from services.database import save_tasks
        save_tasks([
            TaskRecord('TASK-1', 'First task', 'fixed'),
            TaskRecord('TASK-2', 'Second task', 'open'),
        ])
        d = TaskManagerDialog()
        assert d._table.rowCount() == 2
        assert d._table.item(0, TaskManagerDialog._COL_TASK).text() == 'TASK-1'
        assert d._table.item(1, TaskManagerDialog._COL_TASK).text() == 'TASK-2'
        d.destroy()

    def test_invalid_task_type_defaults_to_fixed(self, qt_app, db_env):
        # Insert directly with an unusual type bypassing the CHECK constraint
        # by using a raw connection; in practice we just test _insert_row fallback.
        d = TaskManagerDialog()
        d._insert_row('TASK-X', 'Some task', 'unknown_type')
        type_text = d._table.item(d._table.rowCount() - 1, TaskManagerDialog._COL_TYPE).text()
        assert type_text == 'fixed'
        d.destroy()


class TestTaskManagerDialogAddRow:
    def test_add_row_increments_count(self, dialog):
        initial = dialog._table.rowCount()
        dialog._add_row()
        assert dialog._table.rowCount() == initial + 1

    def test_add_row_defaults_to_fixed_type(self, dialog):
        dialog._add_row()
        last = dialog._table.rowCount() - 1
        assert dialog._table.item(last, TaskManagerDialog._COL_TYPE).text() == 'fixed'


class TestTaskManagerDialogCollectRows:
    def test_collect_returns_all_rows(self, dialog):
        dialog._table.setRowCount(0)
        dialog._insert_row('TASK-A', 'Alpha', 'fixed')
        dialog._insert_row('TASK-B', 'Beta', 'open')
        rows = dialog._collect_rows()
        assert len(rows) == 2
        assert rows[0] == ('TASK-A', 'Alpha', 'fixed')
        assert rows[1] == ('TASK-B', 'Beta', 'open')

    def test_collect_strips_whitespace(self, dialog):
        dialog._table.setRowCount(0)
        dialog._insert_row('  TASK-C  ', '  Gamma  ', 'closed')
        rows = dialog._collect_rows()
        assert rows[0] == ('TASK-C', 'Gamma', 'closed')


class TestTaskManagerDialogSave:
    def test_save_writes_correct_records_to_db(self, dialog, db_env):
        dialog._table.setRowCount(0)
        dialog._insert_row('TASK-1', 'Description one', 'fixed')
        dialog._insert_row('TASK-2', 'Description two', 'open')
        dialog._save()
        tasks = {t.task: t for t in get_all_tasks()}
        assert tasks['TASK-1'].description == 'Description one'
        assert tasks['TASK-1'].task_type == 'fixed'
        assert tasks['TASK-2'].task_type == 'open'

    def test_save_all_valid_task_types(self, dialog, db_env):
        dialog._table.setRowCount(0)
        for t in TASK_TYPES:
            dialog._insert_row(f'TASK-{t}', '', t)
        dialog._save()
        saved_types = {t.task: t.task_type for t in get_all_tasks()}
        for t in TASK_TYPES:
            assert saved_types[f'TASK-{t}'] == t

    def test_save_rejects_empty_task_field(self, dialog, db_env, monkeypatch):
        dialog._table.setRowCount(0)
        dialog._insert_row('', 'No key', 'fixed')
        shown_errors = []
        monkeypatch.setattr(
            QMessageBox, 'critical',
            staticmethod(lambda *args, **kwargs: shown_errors.append(args)),
        )
        dialog._save()
        assert shown_errors, "QMessageBox.critical should have been called"
        assert get_all_tasks() == [], "DB must not be written on validation failure"

    def test_save_rejects_invalid_task_type(self, dialog, db_env, monkeypatch):
        dialog._table.setRowCount(0)
        dialog._insert_row('TASK-1', 'desc', 'invalid_type')
        dialog._table.item(0, TaskManagerDialog._COL_TYPE).setText('invalid_type')
        shown_errors = []
        monkeypatch.setattr(
            QMessageBox, 'critical',
            staticmethod(lambda *args, **kwargs: shown_errors.append(args)),
        )
        dialog._save()
        assert shown_errors, "QMessageBox.critical should have been called"
