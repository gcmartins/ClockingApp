"""Tests for the task management workflow.

Covers:
- CSV migration from legacy split files into tasks.csv  (app._migrate_tasks_csv)
- Time-formatting utilities                              (services/utils.py)
- ClockingException                                     (services/exceptions.py)
- TaskManagerDialog table/save logic                    (windows/task_manager.py)
"""
import csv
import datetime
import os

import pytest

from services.constants import TASK_HEADER, TASK_TYPES, TASKS_CSV
from services.exceptions import ClockingException
from services.utils import format_timedelta, format_timedelta_jira


# ---------------------------------------------------------------------------
# services/utils.py
# ---------------------------------------------------------------------------

class TestFormatTimedelta:
    def test_zero(self):
        assert format_timedelta(datetime.timedelta(0)) == "00:00:00"

    def test_hours_minutes_seconds(self):
        td = datetime.timedelta(hours=1, minutes=30, seconds=45)
        assert format_timedelta(td) == "01:30:45"

    def test_exact_hours(self):
        assert format_timedelta(datetime.timedelta(hours=8)) == "08:00:00"

    def test_near_full_day(self):
        td = datetime.timedelta(hours=23, minutes=59, seconds=59)
        assert format_timedelta(td) == "23:59:59"

    def test_only_minutes(self):
        assert format_timedelta(datetime.timedelta(minutes=5)) == "00:05:00"


class TestFormatTimedeltaJira:
    def test_zero(self):
        assert format_timedelta_jira(datetime.timedelta(0)) == "00h 00m"

    def test_hours_and_minutes(self):
        td = datetime.timedelta(hours=2, minutes=15)
        assert format_timedelta_jira(td) == "02h 15m"

    def test_seconds_are_ignored(self):
        td = datetime.timedelta(hours=1, minutes=30, seconds=59)
        assert format_timedelta_jira(td) == "01h 30m"

    def test_single_digit_padded(self):
        td = datetime.timedelta(hours=3, minutes=5)
        assert format_timedelta_jira(td) == "03h 05m"


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
        exc = ClockingException("test message")
        assert str(exc) == "test message"

    def test_can_be_raised_without_message(self):
        with pytest.raises(ClockingException):
            raise ClockingException()


# ---------------------------------------------------------------------------
# app._migrate_tasks_csv
# ---------------------------------------------------------------------------

# Import once; app.py is guarded with `if __name__ == '__main__'` so the GUI
# is never started. Qt is already available via conftest.
from app import _migrate_tasks_csv  # noqa: E402


def _read_tasks_csv(path):
    """Helper – returns (header, rows) from a tasks.csv path."""
    with open(path, newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        rows = list(reader)
    return header, rows


class TestMigrateTasksCSV:
    def test_noop_when_tasks_csv_exists(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / TASKS_CSV).write_text("existing content")

        _migrate_tasks_csv()

        assert (tmp_path / TASKS_CSV).read_text() == "existing content"

    def test_creates_placeholder_when_no_legacy_files(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        _migrate_tasks_csv()

        header, rows = _read_tasks_csv(tmp_path / TASKS_CSV)
        assert header == TASK_HEADER
        assert len(rows) == 1
        assert rows[0][0] == "TASK-KEY"
        assert rows[0][2] == "fixed"

    def test_migrates_fixed_tasks_only(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "fixed_tasks.csv").write_text(
            "Task,Description\nFIXED-1,Fixed task one\nFIXED-2,Fixed task two\n"
        )

        _migrate_tasks_csv()

        header, rows = _read_tasks_csv(tmp_path / TASKS_CSV)
        assert header == TASK_HEADER
        assert len(rows) == 2
        assert rows[0] == ["FIXED-1", "Fixed task one", "fixed"]
        assert rows[1] == ["FIXED-2", "Fixed task two", "fixed"]

    def test_migrates_open_tasks_only(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "open_tasks.csv").write_text(
            "Task,Description\nOPEN-1,Open task one\n"
        )

        _migrate_tasks_csv()

        _, rows = _read_tasks_csv(tmp_path / TASKS_CSV)
        assert rows[0] == ["OPEN-1", "Open task one", "open"]

    def test_migrates_both_legacy_files(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "fixed_tasks.csv").write_text(
            "Task,Description\nFIXED-1,Fixed one\n"
        )
        (tmp_path / "open_tasks.csv").write_text(
            "Task,Description\nOPEN-1,Open one\n"
        )

        _migrate_tasks_csv()

        _, rows = _read_tasks_csv(tmp_path / TASKS_CSV)
        by_id = {r[0]: r[2] for r in rows}
        assert by_id["FIXED-1"] == "fixed"
        assert by_id["OPEN-1"] == "open"

    def test_skips_rows_with_empty_task(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "fixed_tasks.csv").write_text(
            "Task,Description\n,Empty task id\nVALID-1,Valid task\n"
        )

        _migrate_tasks_csv()

        _, rows = _read_tasks_csv(tmp_path / TASKS_CSV)
        assert len(rows) == 1
        assert rows[0][0] == "VALID-1"

    def test_skips_rows_with_insufficient_columns(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "fixed_tasks.csv").write_text(
            "Task,Description\nONLY-ONE-COL\nVALID-1,Valid task\n"
        )

        _migrate_tasks_csv()

        _, rows = _read_tasks_csv(tmp_path / TASKS_CSV)
        assert len(rows) == 1
        assert rows[0][0] == "VALID-1"


# ---------------------------------------------------------------------------
# windows/task_manager.TaskManagerDialog
# ---------------------------------------------------------------------------

from windows.task_manager import TaskManagerDialog  # noqa: E402
from PySide6.QtWidgets import QTableWidgetItem, QMessageBox  # noqa: E402


@pytest.fixture()
def dialog(qt_app, tmp_path, monkeypatch):
    """TaskManagerDialog initialised against a temporary working directory."""
    monkeypatch.chdir(tmp_path)
    d = TaskManagerDialog()
    yield d
    d.destroy()


class TestTaskManagerDialogLoad:
    def test_empty_table_when_no_csv(self, dialog):
        assert dialog._table.rowCount() == 0

    def test_loads_rows_from_csv(self, qt_app, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / TASKS_CSV).write_text(
            "Task,Description,Task Type\n"
            "TASK-1,First task,fixed\n"
            "TASK-2,Second task,open\n"
        )

        d = TaskManagerDialog()
        assert d._table.rowCount() == 2
        assert d._table.item(0, TaskManagerDialog._COL_TASK).text() == "TASK-1"
        assert d._table.item(1, TaskManagerDialog._COL_TASK).text() == "TASK-2"
        d.destroy()

    def test_invalid_task_type_in_csv_defaults_to_fixed(self, qt_app, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / TASKS_CSV).write_text(
            "Task,Description,Task Type\n"
            "TASK-X,Some task,unknown_type\n"
        )

        d = TaskManagerDialog()
        type_text = d._table.item(0, TaskManagerDialog._COL_TYPE).text()
        assert type_text == "fixed"
        d.destroy()


class TestTaskManagerDialogAddRow:
    def test_add_row_increments_count(self, dialog):
        initial = dialog._table.rowCount()
        dialog._add_row()
        assert dialog._table.rowCount() == initial + 1

    def test_add_row_defaults_to_fixed_type(self, dialog):
        dialog._add_row()
        last = dialog._table.rowCount() - 1
        assert dialog._table.item(last, TaskManagerDialog._COL_TYPE).text() == "fixed"


class TestTaskManagerDialogCollectRows:
    def test_collect_returns_all_rows(self, dialog):
        dialog._table.setRowCount(0)
        dialog._insert_row("TASK-A", "Alpha", "fixed")
        dialog._insert_row("TASK-B", "Beta", "open")

        rows = dialog._collect_rows()

        assert len(rows) == 2
        assert rows[0] == ("TASK-A", "Alpha", "fixed")
        assert rows[1] == ("TASK-B", "Beta", "open")

    def test_collect_strips_whitespace(self, dialog):
        dialog._table.setRowCount(0)
        dialog._insert_row("  TASK-C  ", "  Gamma  ", "closed")

        rows = dialog._collect_rows()

        assert rows[0] == ("TASK-C", "Gamma", "closed")


class TestTaskManagerDialogSave:
    def test_save_writes_correct_csv(self, dialog, tmp_path):
        dialog._table.setRowCount(0)
        dialog._insert_row("TASK-1", "Description one", "fixed")
        dialog._insert_row("TASK-2", "Description two", "open")

        dialog._save()

        csv_path = tmp_path / TASKS_CSV
        assert csv_path.exists()
        with open(csv_path, newline="") as f:
            reader = csv.reader(f)
            header = next(reader)
            rows = list(reader)

        assert header == TASK_HEADER
        assert rows[0] == ["TASK-1", "Description one", "fixed"]
        assert rows[1] == ["TASK-2", "Description two", "open"]

    def test_save_all_valid_task_types(self, dialog, tmp_path):
        dialog._table.setRowCount(0)
        for t in TASK_TYPES:
            dialog._insert_row(f"TASK-{t}", "", t)

        dialog._save()

        with open(tmp_path / TASKS_CSV, newline="") as f:
            reader = csv.reader(f)
            next(reader)
            rows = list(reader)

        saved_types = [r[2] for r in rows]
        assert saved_types == list(TASK_TYPES)

    def test_save_rejects_empty_task_field(self, dialog, tmp_path, monkeypatch):
        dialog._table.setRowCount(0)
        dialog._insert_row("", "No key", "fixed")

        shown_errors = []
        monkeypatch.setattr(
            QMessageBox,
            "critical",
            staticmethod(lambda *args, **kwargs: shown_errors.append(args)),
        )

        dialog._save()

        assert shown_errors, "QMessageBox.critical should have been called"
        assert not (tmp_path / TASKS_CSV).exists(), "CSV must not be written on validation failure"

    def test_save_rejects_invalid_task_type(self, dialog, tmp_path, monkeypatch):
        dialog._table.setRowCount(0)
        dialog._insert_row("TASK-1", "desc", "invalid_type")
        # Bypass the delegate by directly setting text on the item
        dialog._table.item(0, TaskManagerDialog._COL_TYPE).setText("invalid_type")

        shown_errors = []
        monkeypatch.setattr(
            QMessageBox,
            "critical",
            staticmethod(lambda *args, **kwargs: shown_errors.append(args)),
        )

        dialog._save()

        assert shown_errors, "QMessageBox.critical should have been called"
