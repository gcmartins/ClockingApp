import datetime

import pytest

from services.constants import TASK_TYPES
from services.database import TaskRecord, get_all_tasks, init_db
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
# windows/task_manager.TaskManagerDialog
# ---------------------------------------------------------------------------

from PySide6.QtWidgets import QMessageBox  # noqa: E402

from windows.task_manager import TaskManagerDialog  # noqa: E402


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
