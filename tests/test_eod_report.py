"""Tests for the EodReport UI widget (windows/eod_report.py)."""
import datetime

import numpy as np
import pandas as pd
import pytest

from services.constants import CLOCKING_HEADER, TASK_HEADER
from windows.eod_report import EodReport


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_df(rows):
    """Build a DataFrame mimicking the output of Clocking.load_dataframe()."""
    df = pd.DataFrame(rows, columns=CLOCKING_HEADER)
    df["Date"] = pd.to_datetime(df["Date"], format="%Y-%m-%d", errors="coerce")
    date_part = df["Date"].dt.strftime("%Y-%m-%d")
    df["Check In"] = pd.to_datetime(
        date_part + " " + df["Check In"].astype("string"),
        format="%Y-%m-%d %H:%M",
        errors="coerce",
    )
    df["Check Out"] = pd.to_datetime(
        date_part + " " + df["Check Out"].astype("string"),
        format="%Y-%m-%d %H:%M",
        errors="coerce",
    )
    return df


TODAY = datetime.date.today().isoformat()
YESTERDAY = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()


# ---------------------------------------------------------------------------
# TestGetTaskMessages
# ---------------------------------------------------------------------------

class TestGetTaskMessages:
    def test_returns_none_for_empty_dataframe(self, qt_app):
        df = pd.DataFrame(columns=CLOCKING_HEADER)
        df["Date"] = pd.to_datetime(df["Date"])
        widget = EodReport(df)
        result = widget.get_task_messages(datetime.date.today())
        assert result is None
        widget.close()

    def test_returns_none_for_day_with_no_entries(self, qt_app):
        df = make_df([[YESTERDAY, "TASK-1", "09:00", "10:00", "done"]])
        widget = EodReport(df)
        result = widget.get_task_messages(datetime.date.today())
        assert result is None
        widget.close()

    def test_filters_to_requested_day(self, qt_app):
        df = make_df([
            [TODAY, "TASK-1", "09:00", "10:00", "today message"],
            [YESTERDAY, "TASK-2", "08:00", "09:00", "yesterday message"],
        ])
        widget = EodReport(df)
        result = widget.get_task_messages(datetime.date.today())
        assert "TASK-1" in result
        assert "TASK-2" not in result
        widget.close()

    def test_groups_messages_by_task(self, qt_app):
        df = make_df([
            [TODAY, "TASK-1", "09:00", "10:00", "msg1"],
            [TODAY, "TASK-1", "11:00", "12:00", "msg2"],
        ])
        widget = EodReport(df)
        result = widget.get_task_messages(datetime.date.today())
        assert "TASK-1" in result
        assert result["TASK-1"] == ["msg1", "msg2"]
        widget.close()

    def test_null_message_included_in_task_key_but_not_messages(self, qt_app):
        df = make_df([
            [TODAY, "TASK-1", "09:00", "10:00", np.nan],
        ])
        widget = EodReport(df)
        result = widget.get_task_messages(datetime.date.today())
        assert "TASK-1" in result
        assert result["TASK-1"] == []
        widget.close()

    def test_multiple_tasks_each_get_own_key(self, qt_app):
        df = make_df([
            [TODAY, "TASK-1", "09:00", "10:00", "alpha"],
            [TODAY, "TASK-2", "10:00", "11:00", "beta"],
        ])
        widget = EodReport(df)
        result = widget.get_task_messages(datetime.date.today())
        assert set(result.keys()) == {"TASK-1", "TASK-2"}
        widget.close()


# ---------------------------------------------------------------------------
# TestGetTaskDescriptions
# ---------------------------------------------------------------------------

class TestGetTaskDescriptions:
    def test_returns_empty_dict_when_no_tasks_file(self, qt_app, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        df = pd.DataFrame(columns=CLOCKING_HEADER)
        df["Date"] = pd.to_datetime(df["Date"])
        widget = EodReport(df)
        result = widget.get_task_descriptions()
        assert result == {}
        widget.close()

    def test_reads_descriptions_from_csv(self, qt_app, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        tasks_csv = tmp_path / "tasks.csv"
        tasks_csv.write_text("Task,Description,Task Type\nTASK-1,Fix bugs,fixed\nTASK-2,New feature,open\n")

        df = pd.DataFrame(columns=CLOCKING_HEADER)
        df["Date"] = pd.to_datetime(df["Date"])
        widget = EodReport(df)
        result = widget.get_task_descriptions()
        assert result == {"TASK-1": "Fix bugs", "TASK-2": "New feature"}
        widget.close()

    def test_empty_tasks_csv_returns_empty_dict(self, qt_app, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        tasks_csv = tmp_path / "tasks.csv"
        tasks_csv.write_text("Task,Description,Task Type\n")

        df = pd.DataFrame(columns=CLOCKING_HEADER)
        df["Date"] = pd.to_datetime(df["Date"])
        widget = EodReport(df)
        result = widget.get_task_descriptions()
        assert result == {}
        widget.close()


# ---------------------------------------------------------------------------
# TestDisplayTaskMessages
# ---------------------------------------------------------------------------

class TestDisplayTaskMessages:
    def _make_widget(self, qt_app, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        df = pd.DataFrame(columns=CLOCKING_HEADER)
        df["Date"] = pd.to_datetime(df["Date"])
        return EodReport(df)

    def test_formats_task_and_description_header(self, qt_app, tmp_path, monkeypatch):
        widget = self._make_widget(qt_app, tmp_path, monkeypatch)
        widget.display_task_massages({"TASK-1": ["a message"]})
        text = widget.report_text.toPlainText()
        assert "TASK-1:" in text
        widget.close()

    def test_formats_messages_as_bullets(self, qt_app, tmp_path, monkeypatch):
        widget = self._make_widget(qt_app, tmp_path, monkeypatch)
        widget.display_task_massages({"TASK-1": ["did something"]})
        text = widget.report_text.toPlainText()
        assert "- did something" in text
        widget.close()

    def test_splits_message_on_literal_backslash_n(self, qt_app, tmp_path, monkeypatch):
        widget = self._make_widget(qt_app, tmp_path, monkeypatch)
        widget.display_task_massages({"TASK-1": ["line1\\nline2"]})
        text = widget.report_text.toPlainText()
        assert "- line1" in text
        assert "- line2" in text
        widget.close()

    def test_uses_description_from_tasks_csv(self, qt_app, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        tasks_csv = tmp_path / "tasks.csv"
        tasks_csv.write_text("Task,Description,Task Type\nTASK-1,My Description,fixed\n")

        df = pd.DataFrame(columns=CLOCKING_HEADER)
        df["Date"] = pd.to_datetime(df["Date"])
        widget = EodReport(df)
        widget.display_task_massages({"TASK-1": []})
        text = widget.report_text.toPlainText()
        assert "My Description" in text
        widget.close()

    def test_empty_messages_list_shows_task_header_only(self, qt_app, tmp_path, monkeypatch):
        widget = self._make_widget(qt_app, tmp_path, monkeypatch)
        widget.display_task_massages({"TASK-1": []})
        text = widget.report_text.toPlainText()
        assert "TASK-1:" in text
        assert "- " not in text
        widget.close()


# ---------------------------------------------------------------------------
# TestEodReportWidget
# ---------------------------------------------------------------------------

class TestEodReportWidget:
    def test_initializes_without_error(self, qt_app, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        df = make_df([[TODAY, "TASK-1", "09:00", "10:00", "test"]])
        widget = EodReport(df)
        assert widget is not None
        widget.close()

    def test_report_text_is_read_only(self, qt_app, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        df = pd.DataFrame(columns=CLOCKING_HEADER)
        df["Date"] = pd.to_datetime(df["Date"])
        widget = EodReport(df)
        assert widget.report_text.isReadOnly()
        widget.close()

    def test_empty_dataframe_leaves_report_empty(self, qt_app, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        df = pd.DataFrame(columns=CLOCKING_HEADER)
        df["Date"] = pd.to_datetime(df["Date"])
        widget = EodReport(df)
        assert widget.report_text.toPlainText() == ""
        widget.close()
