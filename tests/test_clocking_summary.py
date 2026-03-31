"""Tests for the ClockingSummary UI widget (windows/clocking_summary.py)."""
import datetime
from unittest.mock import MagicMock

import pandas as pd
import pytest

from services.constants import CLOCKING_HEADER
from windows.clocking_summary import ClockingSummary


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_df(rows):
    """Build a DataFrame mimicking Clocking.load_dataframe() output."""
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


def empty_df():
    df = pd.DataFrame(columns=CLOCKING_HEADER)
    df["Date"] = pd.to_datetime(df["Date"])
    df["Check In"] = pd.to_datetime(df["Check In"])
    df["Check Out"] = pd.to_datetime(df["Check Out"])
    return df


TODAY = datetime.date.today()
TODAY_STR = TODAY.isoformat()
YESTERDAY_STR = (TODAY - datetime.timedelta(days=1)).isoformat()


# ---------------------------------------------------------------------------
# TestComputeTaskDuration
# ---------------------------------------------------------------------------

class TestComputeTaskDuration:
    def _widget(self, qt_app, df):
        return ClockingSummary(df)

    def test_returns_none_for_day_with_no_data(self, qt_app):
        widget = self._widget(qt_app, empty_df())
        result = widget.compute_task_duration(TODAY)
        assert result is None
        widget.close()

    def test_returns_dict_with_required_keys(self, qt_app):
        df = make_df([[TODAY_STR, "TASK-1", "09:00", "10:00", ""]])
        widget = self._widget(qt_app, df)
        result = widget.compute_task_duration(TODAY)
        assert result is not None
        assert "date" in result
        assert "clockings" in result
        assert "total" in result
        widget.close()

    def test_date_field_matches_requested_day(self, qt_app):
        df = make_df([[TODAY_STR, "TASK-1", "09:00", "10:00", ""]])
        widget = self._widget(qt_app, df)
        result = widget.compute_task_duration(TODAY)
        assert result["date"] == TODAY_STR
        widget.close()

    def test_excludes_rows_without_checkout(self, qt_app):
        df = make_df([[TODAY_STR, "TASK-1", "09:00", "", ""]])
        widget = self._widget(qt_app, df)
        result = widget.compute_task_duration(TODAY)
        assert result is None
        widget.close()

    def test_sums_duration_per_task(self, qt_app):
        df = make_df([
            [TODAY_STR, "TASK-1", "09:00", "10:00", ""],
            [TODAY_STR, "TASK-1", "11:00", "12:00", ""],
        ])
        widget = self._widget(qt_app, df)
        result = widget.compute_task_duration(TODAY)
        assert "TASK-1" in result["clockings"]
        assert "02h" in result["clockings"]
        widget.close()

    def test_total_contains_combined_duration(self, qt_app):
        df = make_df([
            [TODAY_STR, "TASK-1", "09:00", "10:00", ""],
            [TODAY_STR, "TASK-2", "10:00", "11:30", ""],
        ])
        widget = self._widget(qt_app, df)
        result = widget.compute_task_duration(TODAY)
        assert "Total" in result["total"]
        assert "02:30:00" in result["total"]
        widget.close()

    def test_multiple_tasks_appear_in_clockings(self, qt_app):
        df = make_df([
            [TODAY_STR, "TASK-1", "09:00", "10:00", ""],
            [TODAY_STR, "TASK-2", "10:00", "11:00", ""],
        ])
        widget = self._widget(qt_app, df)
        result = widget.compute_task_duration(TODAY)
        assert "TASK-1" in result["clockings"]
        assert "TASK-2" in result["clockings"]
        widget.close()


# ---------------------------------------------------------------------------
# TestComputeWeekTaskDuration
# ---------------------------------------------------------------------------

class TestComputeWeekTaskDuration:
    def test_returns_empty_list_for_empty_dataframe(self, qt_app):
        widget = ClockingSummary(empty_df())
        result = widget.compute_week_task_duration(TODAY)
        assert result == []
        widget.close()

    def test_returns_only_days_with_data(self, qt_app):
        df = make_df([[TODAY_STR, "TASK-1", "09:00", "10:00", ""]])
        widget = ClockingSummary(df)
        result = widget.compute_week_task_duration(TODAY)
        assert len(result) == 1
        assert result[0]["date"] == TODAY_STR
        widget.close()

    def test_includes_multiple_days(self, qt_app):
        df = make_df([
            [TODAY_STR, "TASK-1", "09:00", "10:00", ""],
            [YESTERDAY_STR, "TASK-1", "09:00", "11:00", ""],
        ])
        widget = ClockingSummary(df)
        result = widget.compute_week_task_duration(TODAY)
        dates = [r["date"] for r in result]
        assert TODAY_STR in dates
        assert YESTERDAY_STR in dates
        widget.close()

    def test_does_not_include_data_older_than_7_days(self, qt_app):
        eight_days_ago = (TODAY - datetime.timedelta(days=8)).isoformat()
        df = make_df([[eight_days_ago, "TASK-1", "09:00", "10:00", ""]])
        widget = ClockingSummary(df)
        result = widget.compute_week_task_duration(TODAY)
        assert result == []
        widget.close()

    def test_includes_data_exactly_7_days_ago(self, qt_app):
        seven_days_ago = (TODAY - datetime.timedelta(days=7)).isoformat()
        df = make_df([[seven_days_ago, "TASK-1", "09:00", "10:00", ""]])
        widget = ClockingSummary(df)
        result = widget.compute_week_task_duration(TODAY)
        assert len(result) == 1
        assert result[0]["date"] == seven_days_ago
        widget.close()


# ---------------------------------------------------------------------------
# TestPushToJira
# ---------------------------------------------------------------------------

class TestPushToJira:
    def test_logs_not_configured_when_jira_missing(self, qt_app, monkeypatch):
        mock_config = MagicMock()
        mock_config.is_jira_configured.return_value = (False, ["ATLASSIAN_EMAIL"])
        import windows.clocking_summary as cs_module
        monkeypatch.setattr(cs_module, "get_config_manager", lambda: mock_config)

        widget = ClockingSummary(empty_df())
        widget.push_to_jira(TODAY_STR)
        log_content = widget.log_text.toPlainText()
        assert "not configured" in log_content.lower() or "Jira" in log_content
        widget.close()

    def test_calls_push_api_for_each_completed_row(self, qt_app, monkeypatch):
        mock_config = MagicMock()
        mock_config.is_jira_configured.return_value = (True, [])
        import windows.clocking_summary as cs_module
        monkeypatch.setattr(cs_module, "get_config_manager", lambda: mock_config)

        push_calls = []
        monkeypatch.setattr(cs_module, "push_worklog_to_jira",
                            lambda task, start, duration: push_calls.append(task) or True)

        df = make_df([
            [TODAY_STR, "TASK-1", "09:00", "10:00", ""],
            [TODAY_STR, "TASK-2", "11:00", "12:00", ""],
        ])
        widget = ClockingSummary(df)
        widget.push_to_jira(TODAY_STR)
        assert len(push_calls) == 2
        assert "TASK-1" in push_calls
        assert "TASK-2" in push_calls
        widget.close()

    def test_skips_rows_without_checkout(self, qt_app, monkeypatch):
        mock_config = MagicMock()
        mock_config.is_jira_configured.return_value = (True, [])
        import windows.clocking_summary as cs_module
        monkeypatch.setattr(cs_module, "get_config_manager", lambda: mock_config)

        push_calls = []
        monkeypatch.setattr(cs_module, "push_worklog_to_jira",
                            lambda task, start, duration: push_calls.append(task) or True)

        df = make_df([[TODAY_STR, "TASK-1", "09:00", "", ""]])
        widget = ClockingSummary(df)
        widget.push_to_jira(TODAY_STR)
        assert push_calls == []
        widget.close()

    def test_logs_success_and_failure(self, qt_app, monkeypatch):
        mock_config = MagicMock()
        mock_config.is_jira_configured.return_value = (True, [])
        import windows.clocking_summary as cs_module
        monkeypatch.setattr(cs_module, "get_config_manager", lambda: mock_config)

        results = iter([True, False])
        monkeypatch.setattr(cs_module, "push_worklog_to_jira",
                            lambda task, start, duration: next(results))

        df = make_df([
            [TODAY_STR, "TASK-1", "09:00", "10:00", ""],
            [TODAY_STR, "TASK-2", "11:00", "12:00", ""],
        ])
        widget = ClockingSummary(df)
        widget.push_to_jira(TODAY_STR)
        log = widget.log_text.toHtml()
        assert "Success" in log
        assert "Fail" in log
        widget.close()


# ---------------------------------------------------------------------------
# TestPushToClockify
# ---------------------------------------------------------------------------

class TestPushToClockify:
    def test_logs_not_configured_when_clockify_missing(self, qt_app, monkeypatch):
        mock_config = MagicMock()
        mock_config.is_clockify_configured.return_value = (False, ["CLOCKIFY_API_KEY"])
        import windows.clocking_summary as cs_module
        monkeypatch.setattr(cs_module, "get_config_manager", lambda: mock_config)

        widget = ClockingSummary(empty_df())
        widget.push_to_clockify(TODAY_STR)
        log_content = widget.log_text.toPlainText()
        assert "not configured" in log_content.lower() or "Clockify" in log_content
        widget.close()

    def test_calls_push_api_for_each_completed_row(self, qt_app, monkeypatch):
        mock_config = MagicMock()
        mock_config.is_clockify_configured.return_value = (True, [])
        import windows.clocking_summary as cs_module
        monkeypatch.setattr(cs_module, "get_config_manager", lambda: mock_config)

        push_calls = []
        monkeypatch.setattr(cs_module, "push_worklog_to_clockify",
                            lambda task, start, end: push_calls.append(task) or True)

        df = make_df([
            [TODAY_STR, "TASK-1", "09:00", "10:00", ""],
            [TODAY_STR, "TASK-2", "11:00", "12:00", ""],
        ])
        widget = ClockingSummary(df)
        widget.push_to_clockify(TODAY_STR)
        assert len(push_calls) == 2
        widget.close()

    def test_skips_rows_without_checkout(self, qt_app, monkeypatch):
        mock_config = MagicMock()
        mock_config.is_clockify_configured.return_value = (True, [])
        import windows.clocking_summary as cs_module
        monkeypatch.setattr(cs_module, "get_config_manager", lambda: mock_config)

        push_calls = []
        monkeypatch.setattr(cs_module, "push_worklog_to_clockify",
                            lambda task, start, end: push_calls.append(task) or True)

        df = make_df([[TODAY_STR, "TASK-1", "09:00", "", ""]])
        widget = ClockingSummary(df)
        widget.push_to_clockify(TODAY_STR)
        assert push_calls == []
        widget.close()
