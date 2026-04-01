"""Tests for the Clocking widget (windows/clocking.py)."""
import datetime
from unittest.mock import MagicMock

import pytest

from PySide6.QtWidgets import QMessageBox

from services.constants import CLOCKING_HEADER
from services.database import ClockingRecord, TaskRecord, init_db, save_clockings, save_tasks


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TODAY = datetime.date.today().isoformat()
YESTERDAY = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()


def make_clocking(date, task, check_in, check_out=None, message=None, id=0):
    return ClockingRecord(
        id=id,
        date=date,
        task=task,
        check_in=f"{date} {check_in}",
        check_out=f"{date} {check_out}" if check_out else None,
        message=message,
    )


def make_tray_icon():
    return MagicMock()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db_env(tmp_path, monkeypatch):
    """Isolated SQLite DB in a temp directory; monkeypatches DB_FILE."""
    import services.database as db_module
    db_path = str(tmp_path / 'clocking.db')
    monkeypatch.setattr(db_module, 'DB_FILE', db_path)
    init_db()
    monkeypatch.setattr(QMessageBox, "exec", lambda self: QMessageBox.StandardButton.Ok)
    monkeypatch.setattr(QMessageBox, "critical",
                        staticmethod(lambda *a, **kw: QMessageBox.StandardButton.Ok))
    return tmp_path


@pytest.fixture
def clocking_env(db_env, qt_app):
    return db_env


# ---------------------------------------------------------------------------
# TestLoadData
# ---------------------------------------------------------------------------

class TestLoadData:
    def test_empty_db_creates_empty_data(self, clocking_env):
        from windows.clocking import Clocking
        widget = Clocking(make_tray_icon())
        assert widget.data == []
        widget.close()

    def test_valid_rows_load_correct_count(self, clocking_env):
        save_clockings([
            make_clocking(TODAY, 'TASK-1', '09:00', '10:00', id=1),
            make_clocking(TODAY, 'TASK-2', '11:00', '12:00', id=2),
        ])
        from windows.clocking import Clocking
        widget = Clocking(make_tray_icon())
        assert len(widget.data) == 2
        widget.close()

    def test_records_are_clocking_record_instances(self, clocking_env):
        save_clockings([make_clocking(TODAY, 'TASK-1', '09:00', '10:00', id=1)])
        from windows.clocking import Clocking
        widget = Clocking(make_tray_icon())
        assert isinstance(widget.data[0], ClockingRecord)
        widget.close()


# ---------------------------------------------------------------------------
# TestCreateTaskButtons
# ---------------------------------------------------------------------------

class TestCreateTaskButtons:
    def test_no_tasks_creates_empty_buttons_dict(self, clocking_env):
        from windows.clocking import Clocking
        widget = Clocking(make_tray_icon())
        assert widget.task_buttons == {}
        widget.close()

    def test_tasks_create_buttons_for_each(self, clocking_env):
        save_tasks([
            TaskRecord('TASK-1', 'Fix bugs', 'fixed'),
            TaskRecord('TASK-2', 'New feature', 'open'),
        ])
        from windows.clocking import Clocking
        widget = Clocking(make_tray_icon())
        assert 'TASK-1' in widget.task_buttons
        assert 'TASK-2' in widget.task_buttons
        widget.close()

    def test_button_label_matches_task_id(self, clocking_env):
        save_tasks([TaskRecord('TASK-1', 'Some description', 'fixed')])
        from windows.clocking import Clocking
        widget = Clocking(make_tray_icon())
        assert widget.task_buttons['TASK-1'].button.text() == 'TASK-1'
        widget.close()

    def test_task_ui_stores_description(self, clocking_env):
        save_tasks([TaskRecord('TASK-1', 'My task description', 'fixed')])
        from windows.clocking import Clocking
        widget = Clocking(make_tray_icon())
        assert widget.task_buttons['TASK-1'].description == 'My task description'
        widget.close()


# ---------------------------------------------------------------------------
# TestAddRow
# ---------------------------------------------------------------------------

class TestAddRow:
    def test_add_row_increments_row_count(self, clocking_env):
        from windows.clocking import Clocking
        widget = Clocking(make_tray_icon())
        initial = widget.clocking_table.rowCount()
        widget.add_row()
        assert widget.clocking_table.rowCount() == initial + 1
        widget.close()

    def test_add_row_sets_today_date_in_first_cell(self, clocking_env):
        from windows.clocking import Clocking
        widget = Clocking(make_tray_icon())
        widget.add_row()
        last_row = widget.clocking_table.rowCount() - 1
        date_cell = widget.clocking_table.item(last_row, 0)
        assert date_cell is not None
        assert date_cell.text() == TODAY
        widget.close()

    def test_add_row_other_cells_are_empty(self, clocking_env):
        from windows.clocking import Clocking
        widget = Clocking(make_tray_icon())
        widget.add_row()
        last_row = widget.clocking_table.rowCount() - 1
        for col in range(1, len(CLOCKING_HEADER)):
            item = widget.clocking_table.item(last_row, col)
            assert item is not None
            assert item.text() == ''
        widget.close()

    def test_multiple_add_rows(self, clocking_env):
        from windows.clocking import Clocking
        widget = Clocking(make_tray_icon())
        initial = widget.clocking_table.rowCount()
        widget.add_row()
        widget.add_row()
        widget.add_row()
        assert widget.clocking_table.rowCount() == initial + 3
        widget.close()


# ---------------------------------------------------------------------------
# TestGetTodayWorkedHours
# ---------------------------------------------------------------------------

class TestGetTodayWorkedHours:
    def test_empty_db_returns_zero(self, clocking_env):
        from windows.clocking import Clocking
        widget = Clocking(make_tray_icon())
        assert widget.get_today_worked_hours() == datetime.timedelta(0)
        widget.close()

    def test_completed_entry_returns_correct_duration(self, clocking_env):
        save_clockings([make_clocking(TODAY, 'TASK-1', '09:00', '10:30', id=1)])
        from windows.clocking import Clocking
        widget = Clocking(make_tray_icon())
        assert widget.get_today_worked_hours() == datetime.timedelta(hours=1, minutes=30)
        widget.close()

    def test_sums_multiple_completed_entries(self, clocking_env):
        save_clockings([
            make_clocking(TODAY, 'TASK-1', '09:00', '10:00', id=1),
            make_clocking(TODAY, 'TASK-2', '11:00', '12:00', id=2),
        ])
        from windows.clocking import Clocking
        widget = Clocking(make_tray_icon())
        assert widget.get_today_worked_hours() == datetime.timedelta(hours=2)
        widget.close()

    def test_excludes_entries_from_other_days(self, clocking_env):
        save_clockings([make_clocking(YESTERDAY, 'TASK-1', '09:00', '10:00', id=1)])
        from windows.clocking import Clocking
        widget = Clocking(make_tray_icon())
        assert widget.get_today_worked_hours() == datetime.timedelta(0)
        widget.close()

    def test_open_checkin_sets_is_checked_out_false(self, clocking_env):
        save_tasks([TaskRecord('TASK-1', 'Fix bugs', 'fixed')])
        save_clockings([make_clocking(TODAY, 'TASK-1', '09:00', id=1)])
        from windows.clocking import Clocking
        widget = Clocking(make_tray_icon())
        widget.get_today_worked_hours()
        assert widget._is_checked_out is False
        widget.close()

    def test_all_completed_sets_is_checked_out_true(self, clocking_env):
        save_clockings([make_clocking(TODAY, 'TASK-1', '09:00', '10:00', id=1)])
        from windows.clocking import Clocking
        widget = Clocking(make_tray_icon())
        widget.get_today_worked_hours()
        assert widget._is_checked_out is True
        widget.close()


# ---------------------------------------------------------------------------
# TestWarnIfOvertime
# ---------------------------------------------------------------------------

class TestWarnIfOvertime:
    def test_sets_red_style_at_8_hours(self, clocking_env):
        from windows.clocking import Clocking
        widget = Clocking(make_tray_icon())
        widget.worked_hours = datetime.timedelta(hours=8)
        widget._overtime_message_showed = True
        widget.warn_if_overtime()
        assert 'red' in widget.timer_clocking_label.styleSheet()
        widget.close()

    def test_sets_red_style_over_8_hours(self, clocking_env):
        from windows.clocking import Clocking
        widget = Clocking(make_tray_icon())
        widget.worked_hours = datetime.timedelta(hours=9)
        widget._overtime_message_showed = True
        widget.warn_if_overtime()
        assert 'red' in widget.timer_clocking_label.styleSheet()
        widget.close()

    def test_sets_green_style_under_8_hours(self, clocking_env):
        from windows.clocking import Clocking
        widget = Clocking(make_tray_icon())
        widget.worked_hours = datetime.timedelta(hours=7, minutes=59)
        widget.warn_if_overtime()
        assert 'green' in widget.timer_clocking_label.styleSheet()
        widget.close()

    def test_overtime_message_shown_only_once(self, clocking_env):
        from windows.clocking import Clocking
        widget = Clocking(make_tray_icon())
        widget.worked_hours = datetime.timedelta(hours=8)
        assert widget._overtime_message_showed is False
        widget.warn_if_overtime()
        assert widget._overtime_message_showed is True
        call_count = widget.tray_icon.showMessage.call_count
        widget.warn_if_overtime()
        assert widget.tray_icon.showMessage.call_count == call_count
        widget.close()


# ---------------------------------------------------------------------------
# TestCollectRows
# ---------------------------------------------------------------------------

class TestCollectRows:
    def test_collect_returns_clocking_records(self, clocking_env):
        from windows.clocking import Clocking
        widget = Clocking(make_tray_icon())
        widget.add_row()
        records = widget._collect_rows()
        assert isinstance(records[0], ClockingRecord)
        widget.close()

    def test_collect_includes_table_rows(self, clocking_env):
        save_clockings([make_clocking(TODAY, 'TASK-1', '09:00', '10:00', 'msg', id=1)])
        from windows.clocking import Clocking
        widget = Clocking(make_tray_icon())
        records = widget._collect_rows()
        assert any(r.task == 'TASK-1' for r in records)
        widget.close()
