"""Tests for the Clocking widget (windows/clocking.py)."""
import datetime
from unittest.mock import MagicMock

import pandas as pd
import pytest

from PySide6.QtWidgets import QMessageBox

from services.constants import CLOCKING_HEADER, CLOCKING_CSV, TASKS_CSV, TASK_HEADER


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

HEADER_LINE = ",".join(CLOCKING_HEADER) + "\n"
TODAY = datetime.date.today().isoformat()
YESTERDAY = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()


def write_clocking_csv(tmp_path, lines):
    """Write work_hours.csv with a header and the given data lines."""
    csv_path = tmp_path / CLOCKING_CSV
    csv_path.write_text(HEADER_LINE + "".join(lines))


def write_tasks_csv(tmp_path, rows):
    """Write tasks.csv with header + given rows (list of 'task,desc,type\n' strings)."""
    tasks_path = tmp_path / TASKS_CSV
    header = ",".join(TASK_HEADER) + "\n"
    tasks_path.write_text(header + "".join(rows))


def make_tray_icon():
    return MagicMock()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def clocking_env(qt_app, tmp_path, monkeypatch):
    """
    Create an isolated environment with empty CSV files and return
    a helper that builds a Clocking widget.
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(QMessageBox, "exec", lambda self: QMessageBox.StandardButton.Ok)
    monkeypatch.setattr(QMessageBox, "critical",
                        staticmethod(lambda *a, **kw: QMessageBox.StandardButton.Ok))
    write_clocking_csv(tmp_path, [])
    write_tasks_csv(tmp_path, [])
    return tmp_path


# ---------------------------------------------------------------------------
# TestLoadDataframe
# ---------------------------------------------------------------------------

class TestLoadDataframe:
    def test_empty_csv_creates_empty_dataframe(self, clocking_env, monkeypatch, qt_app):
        from windows.clocking import Clocking
        widget = Clocking(make_tray_icon())
        assert widget.dataframe is not None
        assert len(widget.dataframe) == 0
        assert list(widget.dataframe.columns) == CLOCKING_HEADER
        widget.close()

    def test_valid_csv_loads_correct_row_count(self, clocking_env, qt_app):
        write_clocking_csv(clocking_env, [
            f"{TODAY},TASK-1,09:00,10:00,done\n",
            f"{TODAY},TASK-2,11:00,12:00,\n",
        ])
        from windows.clocking import Clocking
        widget = Clocking(make_tray_icon())
        assert len(widget.dataframe) == 2
        widget.close()

    def test_date_column_is_datetime(self, clocking_env, qt_app):
        write_clocking_csv(clocking_env, [f"{TODAY},TASK-1,09:00,10:00,\n"])
        from windows.clocking import Clocking
        widget = Clocking(make_tray_icon())
        assert pd.api.types.is_datetime64_any_dtype(widget.dataframe["Date"])
        widget.close()

    def test_invalid_csv_falls_back_to_empty_dataframe(self, clocking_env, qt_app, monkeypatch):
        csv_path = clocking_env / CLOCKING_CSV
        # Write malformed content (wrong number of columns, bad data)
        csv_path.write_text("Date,Task,Check In,Check Out,Message\nbad,data\n")
        shown = []
        monkeypatch.setattr(QMessageBox, "exec", lambda self: shown.append(True) or QMessageBox.StandardButton.Ok)

        from windows.clocking import Clocking
        widget = Clocking(make_tray_icon())
        assert len(widget.dataframe) == 0
        widget.close()


# ---------------------------------------------------------------------------
# TestCreateTaskButtons
# ---------------------------------------------------------------------------

class TestCreateTaskButtons:
    def test_no_tasks_csv_creates_empty_buttons_dict(self, clocking_env, qt_app):
        (clocking_env / TASKS_CSV).unlink()
        from windows.clocking import Clocking
        widget = Clocking(make_tray_icon())
        assert widget.task_buttons == {}
        widget.close()

    def test_tasks_csv_creates_buttons_for_each_task(self, clocking_env, qt_app):
        write_tasks_csv(clocking_env, [
            "TASK-1,Fix bugs,fixed\n",
            "TASK-2,New feature,open\n",
        ])
        from windows.clocking import Clocking
        widget = Clocking(make_tray_icon())
        assert "TASK-1" in widget.task_buttons
        assert "TASK-2" in widget.task_buttons
        widget.close()

    def test_button_label_matches_task_id(self, clocking_env, qt_app):
        write_tasks_csv(clocking_env, ["TASK-1,Some description,fixed\n"])
        from windows.clocking import Clocking
        widget = Clocking(make_tray_icon())
        btn = widget.task_buttons["TASK-1"].button
        assert btn.text() == "TASK-1"
        widget.close()

    def test_task_ui_stores_description(self, clocking_env, qt_app):
        write_tasks_csv(clocking_env, ["TASK-1,My task description,fixed\n"])
        from windows.clocking import Clocking
        widget = Clocking(make_tray_icon())
        assert widget.task_buttons["TASK-1"].description == "My task description"
        widget.close()


# ---------------------------------------------------------------------------
# TestAddRow
# ---------------------------------------------------------------------------

class TestAddRow:
    def test_add_row_increments_row_count(self, clocking_env, qt_app):
        from windows.clocking import Clocking
        widget = Clocking(make_tray_icon())
        initial = widget.csv_table.rowCount()
        widget.add_row()
        assert widget.csv_table.rowCount() == initial + 1
        widget.close()

    def test_add_row_sets_today_date_in_first_cell(self, clocking_env, qt_app):
        from windows.clocking import Clocking
        widget = Clocking(make_tray_icon())
        widget.add_row()
        last_row = widget.csv_table.rowCount() - 1
        date_cell = widget.csv_table.item(last_row, 0)
        assert date_cell is not None
        assert date_cell.text() == TODAY
        widget.close()

    def test_add_row_other_cells_are_empty(self, clocking_env, qt_app):
        from windows.clocking import Clocking
        widget = Clocking(make_tray_icon())
        widget.add_row()
        last_row = widget.csv_table.rowCount() - 1
        for col in range(1, len(CLOCKING_HEADER)):
            item = widget.csv_table.item(last_row, col)
            assert item is not None
            assert item.text() == ""
        widget.close()

    def test_multiple_add_rows(self, clocking_env, qt_app):
        from windows.clocking import Clocking
        widget = Clocking(make_tray_icon())
        initial = widget.csv_table.rowCount()
        widget.add_row()
        widget.add_row()
        widget.add_row()
        assert widget.csv_table.rowCount() == initial + 3
        widget.close()


# ---------------------------------------------------------------------------
# TestGetTodayWorkedHours
# ---------------------------------------------------------------------------

class TestGetTodayWorkedHours:
    def test_empty_dataframe_returns_zero(self, clocking_env, qt_app):
        from windows.clocking import Clocking
        widget = Clocking(make_tray_icon())
        result = widget.get_today_worked_hours()
        assert result == datetime.timedelta(0)
        widget.close()

    def test_completed_entry_returns_correct_duration(self, clocking_env, qt_app):
        write_clocking_csv(clocking_env, [f"{TODAY},TASK-1,09:00,10:30,\n"])
        from windows.clocking import Clocking
        widget = Clocking(make_tray_icon())
        result = widget.get_today_worked_hours()
        assert result == datetime.timedelta(hours=1, minutes=30)
        widget.close()

    def test_sums_multiple_completed_entries(self, clocking_env, qt_app):
        write_clocking_csv(clocking_env, [
            f"{TODAY},TASK-1,09:00,10:00,\n",
            f"{TODAY},TASK-2,11:00,12:00,\n",
        ])
        from windows.clocking import Clocking
        widget = Clocking(make_tray_icon())
        result = widget.get_today_worked_hours()
        assert result == datetime.timedelta(hours=2)
        widget.close()

    def test_excludes_entries_from_other_days(self, clocking_env, qt_app):
        write_clocking_csv(clocking_env, [
            f"{YESTERDAY},TASK-1,09:00,10:00,\n",
        ])
        from windows.clocking import Clocking
        widget = Clocking(make_tray_icon())
        result = widget.get_today_worked_hours()
        assert result == datetime.timedelta(0)
        widget.close()

    def test_open_checkin_sets_is_checked_out_false(self, clocking_env, qt_app):
        write_clocking_csv(clocking_env, [f"{TODAY},TASK-1,09:00,,\n"])
        # TASK-1 must exist in tasks.csv so update_buttons() can look it up
        write_tasks_csv(clocking_env, ["TASK-1,Fix bugs,fixed\n"])
        from windows.clocking import Clocking
        widget = Clocking(make_tray_icon())
        widget.get_today_worked_hours()
        assert widget._is_checked_out is False
        widget.close()

    def test_all_completed_sets_is_checked_out_true(self, clocking_env, qt_app):
        write_clocking_csv(clocking_env, [f"{TODAY},TASK-1,09:00,10:00,\n"])
        from windows.clocking import Clocking
        widget = Clocking(make_tray_icon())
        widget.get_today_worked_hours()
        assert widget._is_checked_out is True
        widget.close()


# ---------------------------------------------------------------------------
# TestWarnIfOvertime
# ---------------------------------------------------------------------------

class TestWarnIfOvertime:
    def test_sets_red_style_at_8_hours(self, clocking_env, qt_app):
        from windows.clocking import Clocking
        widget = Clocking(make_tray_icon())
        widget.worked_hours = datetime.timedelta(hours=8)
        widget._overtime_message_showed = True  # prevent tray notification
        widget.warn_if_overtime()
        assert "red" in widget.timer_clocking_label.styleSheet()
        widget.close()

    def test_sets_red_style_over_8_hours(self, clocking_env, qt_app):
        from windows.clocking import Clocking
        widget = Clocking(make_tray_icon())
        widget.worked_hours = datetime.timedelta(hours=9)
        widget._overtime_message_showed = True
        widget.warn_if_overtime()
        assert "red" in widget.timer_clocking_label.styleSheet()
        widget.close()

    def test_sets_green_style_under_8_hours(self, clocking_env, qt_app):
        from windows.clocking import Clocking
        widget = Clocking(make_tray_icon())
        widget.worked_hours = datetime.timedelta(hours=7, minutes=59)
        widget.warn_if_overtime()
        assert "green" in widget.timer_clocking_label.styleSheet()
        widget.close()

    def test_overtime_message_shown_only_once(self, clocking_env, qt_app):
        from windows.clocking import Clocking
        widget = Clocking(make_tray_icon())
        widget.worked_hours = datetime.timedelta(hours=8)
        assert widget._overtime_message_showed is False
        widget.warn_if_overtime()
        assert widget._overtime_message_showed is True
        # Calling again should not trigger show again (tray icon called only once)
        call_count = widget.tray_icon.showMessage.call_count
        widget.warn_if_overtime()
        assert widget.tray_icon.showMessage.call_count == call_count
        widget.close()


# ---------------------------------------------------------------------------
# TestCollectCsvContent
# ---------------------------------------------------------------------------

class TestCollectCsvContent:
    def test_collect_includes_header(self, clocking_env, qt_app):
        from windows.clocking import Clocking
        widget = Clocking(make_tray_icon())
        content = widget._collect_csv_content()
        first_line = content.split("\n")[0]
        assert first_line == ",".join(CLOCKING_HEADER)
        widget.close()

    def test_collect_includes_table_rows(self, clocking_env, qt_app):
        write_clocking_csv(clocking_env, [f"{TODAY},TASK-1,09:00,10:00,msg\n"])
        from windows.clocking import Clocking
        widget = Clocking(make_tray_icon())
        content = widget._collect_csv_content()
        assert "TASK-1" in content
        widget.close()
