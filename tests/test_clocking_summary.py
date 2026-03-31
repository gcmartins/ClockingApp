"""Tests for the ClockingSummary UI widget (windows/clocking_summary.py)."""
import datetime
from unittest.mock import MagicMock

import pytest

from services.database import ClockingRecord, TaskDuration
from windows.clocking_summary import ClockingSummary


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TODAY = datetime.date.today()
TODAY_STR = TODAY.isoformat()
YESTERDAY_STR = (TODAY - datetime.timedelta(days=1)).isoformat()


def make_record(date, task, check_in, check_out=None, id=0):
    return ClockingRecord(
        id=id,
        date=date,
        task=task,
        check_in=f"{date} {check_in}",
        check_out=f"{date} {check_out}" if check_out else None,
        message=None,
    )


def _durations_for(records):
    """Compute TaskDuration list from ClockingRecord list (mirrors SQL logic)."""
    totals: dict[str, int] = {}
    for r in records:
        if not r.check_out:
            continue
        fmt = "%Y-%m-%d %H:%M"
        secs = int((datetime.datetime.strptime(r.check_out, fmt) -
                    datetime.datetime.strptime(r.check_in, fmt)).total_seconds())
        totals[r.task] = totals.get(r.task, 0) + secs
    return [TaskDuration(task=t, total_seconds=s) for t, s in sorted(totals.items())]


# ---------------------------------------------------------------------------
# TestComputeTaskDuration
# ---------------------------------------------------------------------------

class TestComputeTaskDuration:
    def _widget(self, qt_app, records=None):
        return ClockingSummary(records or [])

    def test_returns_none_for_day_with_no_data(self, qt_app, monkeypatch):
        import windows.clocking_summary as cs
        monkeypatch.setattr(cs, 'get_task_durations_for_date', lambda d: [])
        widget = self._widget(qt_app)
        assert widget.compute_task_duration(TODAY) is None
        widget.close()

    def test_returns_dict_with_required_keys(self, qt_app, monkeypatch):
        import windows.clocking_summary as cs
        durations = _durations_for([make_record(TODAY_STR, 'TASK-1', '09:00', '10:00')])
        monkeypatch.setattr(cs, 'get_task_durations_for_date', lambda d: durations)
        widget = self._widget(qt_app)
        result = widget.compute_task_duration(TODAY)
        assert result is not None
        assert 'date' in result and 'clockings' in result and 'total' in result
        widget.close()

    def test_date_field_matches_requested_day(self, qt_app, monkeypatch):
        import windows.clocking_summary as cs
        durations = _durations_for([make_record(TODAY_STR, 'TASK-1', '09:00', '10:00')])
        monkeypatch.setattr(cs, 'get_task_durations_for_date', lambda d: durations)
        widget = self._widget(qt_app)
        result = widget.compute_task_duration(TODAY)
        assert result['date'] == TODAY_STR
        widget.close()

    def test_excludes_rows_without_checkout(self, qt_app, monkeypatch):
        import windows.clocking_summary as cs
        monkeypatch.setattr(cs, 'get_task_durations_for_date', lambda d: [])
        widget = self._widget(qt_app)
        assert widget.compute_task_duration(TODAY) is None
        widget.close()

    def test_sums_duration_per_task(self, qt_app, monkeypatch):
        import windows.clocking_summary as cs
        records = [
            make_record(TODAY_STR, 'TASK-1', '09:00', '10:00'),
            make_record(TODAY_STR, 'TASK-1', '11:00', '12:00'),
        ]
        monkeypatch.setattr(cs, 'get_task_durations_for_date', lambda d: _durations_for(records))
        widget = self._widget(qt_app)
        result = widget.compute_task_duration(TODAY)
        assert 'TASK-1' in result['clockings']
        assert '02h' in result['clockings']
        widget.close()

    def test_total_contains_combined_duration(self, qt_app, monkeypatch):
        import windows.clocking_summary as cs
        records = [
            make_record(TODAY_STR, 'TASK-1', '09:00', '10:00'),
            make_record(TODAY_STR, 'TASK-2', '10:00', '11:30'),
        ]
        monkeypatch.setattr(cs, 'get_task_durations_for_date', lambda d: _durations_for(records))
        widget = self._widget(qt_app)
        result = widget.compute_task_duration(TODAY)
        assert 'Total' in result['total']
        assert '02:30:00' in result['total']
        widget.close()

    def test_multiple_tasks_appear_in_clockings(self, qt_app, monkeypatch):
        import windows.clocking_summary as cs
        records = [
            make_record(TODAY_STR, 'TASK-1', '09:00', '10:00'),
            make_record(TODAY_STR, 'TASK-2', '10:00', '11:00'),
        ]
        monkeypatch.setattr(cs, 'get_task_durations_for_date', lambda d: _durations_for(records))
        widget = self._widget(qt_app)
        result = widget.compute_task_duration(TODAY)
        assert 'TASK-1' in result['clockings']
        assert 'TASK-2' in result['clockings']
        widget.close()


# ---------------------------------------------------------------------------
# TestComputeWeekTaskDuration
# ---------------------------------------------------------------------------

class TestComputeWeekTaskDuration:
    def test_returns_empty_list_for_empty_db(self, qt_app, monkeypatch):
        import windows.clocking_summary as cs
        monkeypatch.setattr(cs, 'get_task_durations_for_date', lambda d: [])
        widget = ClockingSummary([])
        assert widget.compute_week_task_duration(TODAY) == []
        widget.close()

    def test_returns_only_days_with_data(self, qt_app, monkeypatch):
        import windows.clocking_summary as cs
        today_durations = _durations_for([make_record(TODAY_STR, 'TASK-1', '09:00', '10:00')])

        def fake_durations(date_str):
            return today_durations if date_str == TODAY_STR else []

        monkeypatch.setattr(cs, 'get_task_durations_for_date', fake_durations)
        widget = ClockingSummary([])
        result = widget.compute_week_task_duration(TODAY)
        assert len(result) == 1
        assert result[0]['date'] == TODAY_STR
        widget.close()

    def test_includes_multiple_days(self, qt_app, monkeypatch):
        import windows.clocking_summary as cs
        today_d = _durations_for([make_record(TODAY_STR, 'TASK-1', '09:00', '10:00')])
        yest_d = _durations_for([make_record(YESTERDAY_STR, 'TASK-1', '09:00', '11:00')])

        def fake_durations(date_str):
            if date_str == TODAY_STR:
                return today_d
            if date_str == YESTERDAY_STR:
                return yest_d
            return []

        monkeypatch.setattr(cs, 'get_task_durations_for_date', fake_durations)
        widget = ClockingSummary([])
        result = widget.compute_week_task_duration(TODAY)
        dates = [r['date'] for r in result]
        assert TODAY_STR in dates
        assert YESTERDAY_STR in dates
        widget.close()

    def test_does_not_include_data_older_than_7_days(self, qt_app, monkeypatch):
        import windows.clocking_summary as cs
        eight_days_ago = (TODAY - datetime.timedelta(days=8)).isoformat()
        old_d = _durations_for([make_record(eight_days_ago, 'TASK-1', '09:00', '10:00')])

        def fake_durations(date_str):
            return old_d if date_str == eight_days_ago else []

        monkeypatch.setattr(cs, 'get_task_durations_for_date', fake_durations)
        widget = ClockingSummary([])
        assert widget.compute_week_task_duration(TODAY) == []
        widget.close()

    def test_includes_data_exactly_7_days_ago(self, qt_app, monkeypatch):
        import windows.clocking_summary as cs
        seven_ago = (TODAY - datetime.timedelta(days=7)).isoformat()
        old_d = _durations_for([make_record(seven_ago, 'TASK-1', '09:00', '10:00')])

        def fake_durations(date_str):
            return old_d if date_str == seven_ago else []

        monkeypatch.setattr(cs, 'get_task_durations_for_date', fake_durations)
        widget = ClockingSummary([])
        result = widget.compute_week_task_duration(TODAY)
        assert len(result) == 1
        assert result[0]['date'] == seven_ago
        widget.close()


# ---------------------------------------------------------------------------
# TestPushToJira
# ---------------------------------------------------------------------------

class TestPushToJira:
    def test_logs_not_configured_when_jira_missing(self, qt_app, monkeypatch):
        mock_config = MagicMock()
        mock_config.is_jira_configured.return_value = (False, ['ATLASSIAN_EMAIL'])
        import windows.clocking_summary as cs
        monkeypatch.setattr(cs, 'get_config_manager', lambda: mock_config)
        monkeypatch.setattr(cs, 'get_clockings_for_date', lambda d: [])
        monkeypatch.setattr(cs, 'get_task_durations_for_date', lambda d: [])

        widget = ClockingSummary([])
        widget.push_to_jira(TODAY_STR)
        assert 'not configured' in widget.log_text.toPlainText().lower() or \
               'Jira' in widget.log_text.toPlainText()
        widget.close()

    def test_calls_push_api_for_each_completed_row(self, qt_app, monkeypatch):
        mock_config = MagicMock()
        mock_config.is_jira_configured.return_value = (True, [])
        import windows.clocking_summary as cs
        monkeypatch.setattr(cs, 'get_config_manager', lambda: mock_config)
        monkeypatch.setattr(cs, 'get_task_durations_for_date', lambda d: [])

        records = [
            make_record(TODAY_STR, 'TASK-1', '09:00', '10:00'),
            make_record(TODAY_STR, 'TASK-2', '11:00', '12:00'),
        ]
        monkeypatch.setattr(cs, 'get_clockings_for_date', lambda d: records)

        push_calls = []
        monkeypatch.setattr(cs, 'push_worklog_to_jira',
                            lambda task, start, duration: push_calls.append(task) or True)

        widget = ClockingSummary([])
        widget.push_to_jira(TODAY_STR)
        assert len(push_calls) == 2
        assert 'TASK-1' in push_calls
        assert 'TASK-2' in push_calls
        widget.close()

    def test_skips_rows_without_checkout(self, qt_app, monkeypatch):
        mock_config = MagicMock()
        mock_config.is_jira_configured.return_value = (True, [])
        import windows.clocking_summary as cs
        monkeypatch.setattr(cs, 'get_config_manager', lambda: mock_config)
        monkeypatch.setattr(cs, 'get_task_durations_for_date', lambda d: [])
        monkeypatch.setattr(cs, 'get_clockings_for_date', lambda d: [])

        push_calls = []
        monkeypatch.setattr(cs, 'push_worklog_to_jira',
                            lambda task, start, duration: push_calls.append(task) or True)

        widget = ClockingSummary([])
        widget.push_to_jira(TODAY_STR)
        assert push_calls == []
        widget.close()

    def test_logs_success_and_failure(self, qt_app, monkeypatch):
        mock_config = MagicMock()
        mock_config.is_jira_configured.return_value = (True, [])
        import windows.clocking_summary as cs
        monkeypatch.setattr(cs, 'get_config_manager', lambda: mock_config)
        monkeypatch.setattr(cs, 'get_task_durations_for_date', lambda d: [])

        records = [
            make_record(TODAY_STR, 'TASK-1', '09:00', '10:00'),
            make_record(TODAY_STR, 'TASK-2', '11:00', '12:00'),
        ]
        monkeypatch.setattr(cs, 'get_clockings_for_date', lambda d: records)

        results = iter([True, False])
        monkeypatch.setattr(cs, 'push_worklog_to_jira',
                            lambda task, start, duration: next(results))

        widget = ClockingSummary([])
        widget.push_to_jira(TODAY_STR)
        log = widget.log_text.toHtml()
        assert 'Success' in log
        assert 'Fail' in log
        widget.close()


# ---------------------------------------------------------------------------
# TestPushToClockify
# ---------------------------------------------------------------------------

class TestPushToClockify:
    def test_logs_not_configured_when_clockify_missing(self, qt_app, monkeypatch):
        mock_config = MagicMock()
        mock_config.is_clockify_configured.return_value = (False, ['CLOCKIFY_API_KEY'])
        import windows.clocking_summary as cs
        monkeypatch.setattr(cs, 'get_config_manager', lambda: mock_config)
        monkeypatch.setattr(cs, 'get_clockings_for_date', lambda d: [])
        monkeypatch.setattr(cs, 'get_task_durations_for_date', lambda d: [])

        widget = ClockingSummary([])
        widget.push_to_clockify(TODAY_STR)
        log = widget.log_text.toPlainText()
        assert 'not configured' in log.lower() or 'Clockify' in log
        widget.close()

    def test_calls_push_api_for_each_completed_row(self, qt_app, monkeypatch):
        mock_config = MagicMock()
        mock_config.is_clockify_configured.return_value = (True, [])
        import windows.clocking_summary as cs
        monkeypatch.setattr(cs, 'get_config_manager', lambda: mock_config)
        monkeypatch.setattr(cs, 'get_task_durations_for_date', lambda d: [])

        records = [
            make_record(TODAY_STR, 'TASK-1', '09:00', '10:00'),
            make_record(TODAY_STR, 'TASK-2', '11:00', '12:00'),
        ]
        monkeypatch.setattr(cs, 'get_clockings_for_date', lambda d: records)

        push_calls = []
        monkeypatch.setattr(cs, 'push_worklog_to_clockify',
                            lambda task, start, end: push_calls.append(task) or True)

        widget = ClockingSummary([])
        widget.push_to_clockify(TODAY_STR)
        assert len(push_calls) == 2
        widget.close()

    def test_skips_rows_without_checkout(self, qt_app, monkeypatch):
        mock_config = MagicMock()
        mock_config.is_clockify_configured.return_value = (True, [])
        import windows.clocking_summary as cs
        monkeypatch.setattr(cs, 'get_config_manager', lambda: mock_config)
        monkeypatch.setattr(cs, 'get_task_durations_for_date', lambda d: [])
        monkeypatch.setattr(cs, 'get_clockings_for_date', lambda d: [])

        push_calls = []
        monkeypatch.setattr(cs, 'push_worklog_to_clockify',
                            lambda task, start, end: push_calls.append(task) or True)

        widget = ClockingSummary([])
        widget.push_to_clockify(TODAY_STR)
        assert push_calls == []
        widget.close()
