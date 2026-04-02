"""Tests for the EodReport UI widget (windows/eod_report.py)."""
import datetime

import pytest

from services.database import ClockingRecord, TaskRecord, init_db, save_tasks
from windows.eod_report import EodReport

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TODAY = datetime.date.today().isoformat()
YESTERDAY = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()


def make_record(date, task, check_in='09:00', check_out='10:00', message=None, id=0):
    return ClockingRecord(
        id=id,
        date=date,
        task=task,
        check_in=f"{date} {check_in}",
        check_out=f"{date} {check_out}" if check_out else None,
        message=message,
    )


@pytest.fixture
def db_env(tmp_path, monkeypatch):
    import services.database as db_module
    db_path = str(tmp_path / 'clocking.db')
    monkeypatch.setattr(db_module, 'DB_FILE', db_path)
    init_db()
    return tmp_path


# ---------------------------------------------------------------------------
# TestGetTaskMessages
# ---------------------------------------------------------------------------

class TestGetTaskMessages:
    def test_returns_none_for_empty_data(self, qt_app):
        widget = EodReport([])
        assert widget.get_task_messages(datetime.date.today()) is None
        widget.close()

    def test_returns_none_for_day_with_no_entries(self, qt_app, db_env):
        widget = EodReport([make_record(YESTERDAY, 'TASK-1', message='done')])
        assert widget.get_task_messages(datetime.date.today()) is None
        widget.close()

    def test_filters_to_requested_day(self, qt_app, db_env):
        data = [
            make_record(TODAY, 'TASK-1', message='today message'),
            make_record(YESTERDAY, 'TASK-2', message='yesterday message'),
        ]
        widget = EodReport(data)
        result = widget.get_task_messages(datetime.date.today())
        assert result is not None
        assert 'TASK-1' in result
        assert 'TASK-2' not in result
        widget.close()

    def test_groups_messages_by_task(self, qt_app, db_env):
        data = [
            make_record(TODAY, 'TASK-1', check_in='09:00', check_out='10:00', message='msg1'),
            make_record(TODAY, 'TASK-1', check_in='11:00', check_out='12:00', message='msg2'),
        ]
        widget = EodReport(data)
        result = widget.get_task_messages(datetime.date.today())
        assert result is not None
        assert result['TASK-1'] == ['msg1', 'msg2']
        widget.close()

    def test_null_message_included_in_task_key_but_not_messages(self, qt_app, db_env):
        widget = EodReport([make_record(TODAY, 'TASK-1', message=None)])
        result = widget.get_task_messages(datetime.date.today())
        assert result is not None
        assert 'TASK-1' in result
        assert result['TASK-1'] == []
        widget.close()

    def test_multiple_tasks_each_get_own_key(self, qt_app, db_env):
        data = [
            make_record(TODAY, 'TASK-1', message='alpha'),
            make_record(TODAY, 'TASK-2', message='beta'),
        ]
        widget = EodReport(data)
        result = widget.get_task_messages(datetime.date.today())
        assert result is not None
        assert set(result.keys()) == {'TASK-1', 'TASK-2'}
        widget.close()


# ---------------------------------------------------------------------------
# TestGetTaskDescriptions
# ---------------------------------------------------------------------------

class TestGetTaskDescriptions:
    """Test the database.get_task_descriptions() helper used by EodReport."""

    def test_returns_empty_dict_when_no_tasks(self, db_env):
        from services.database import get_task_descriptions
        assert get_task_descriptions() == {}

    def test_reads_descriptions_from_db(self, db_env):
        from services.database import get_task_descriptions
        save_tasks([
            TaskRecord('TASK-1', 'Fix bugs', 'fixed'),
            TaskRecord('TASK-2', 'New feature', 'open'),
        ])
        assert get_task_descriptions() == {'TASK-1': 'Fix bugs', 'TASK-2': 'New feature'}

    def test_empty_tasks_table_returns_empty_dict(self, db_env):
        from services.database import get_task_descriptions
        assert get_task_descriptions() == {}


# ---------------------------------------------------------------------------
# TestDisplayTaskMessages
# ---------------------------------------------------------------------------

class TestDisplayTaskMessages:
    def test_formats_task_and_description_header(self, qt_app, db_env):
        widget = EodReport([])
        widget.display_task_messages({'TASK-1': ['a message']})
        assert 'TASK-1:' in widget.report_text.toPlainText()
        widget.close()

    def test_formats_messages_as_bullets(self, qt_app, db_env):
        widget = EodReport([])
        widget.display_task_messages({'TASK-1': ['did something']})
        assert '- did something' in widget.report_text.toPlainText()
        widget.close()

    def test_splits_message_on_literal_backslash_n(self, qt_app, db_env):
        widget = EodReport([])
        widget.display_task_messages({'TASK-1': ['line1\\nline2']})
        text = widget.report_text.toPlainText()
        assert '- line1' in text
        assert '- line2' in text
        widget.close()

    def test_uses_description_from_db(self, qt_app, db_env):
        save_tasks([TaskRecord('TASK-1', 'My Description', 'fixed')])
        widget = EodReport([])
        widget.display_task_messages({'TASK-1': []})
        assert 'My Description' in widget.report_text.toPlainText()
        widget.close()

    def test_empty_messages_list_shows_task_header_only(self, qt_app, db_env):
        widget = EodReport([])
        widget.display_task_messages({'TASK-1': []})
        text = widget.report_text.toPlainText()
        assert 'TASK-1:' in text
        assert '- ' not in text
        widget.close()


# ---------------------------------------------------------------------------
# TestEodReportWidget
# ---------------------------------------------------------------------------

class TestEodReportWidget:
    def test_initializes_without_error(self, qt_app, db_env):
        widget = EodReport([make_record(TODAY, 'TASK-1', message='test')])
        assert widget is not None
        widget.close()

    def test_report_text_is_read_only(self, qt_app):
        widget = EodReport([])
        assert widget.report_text.isReadOnly()
        widget.close()

    def test_empty_data_leaves_report_empty(self, qt_app):
        widget = EodReport([])
        assert widget.report_text.toPlainText() == ''
        widget.close()
