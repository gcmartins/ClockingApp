import os
import sqlite3
import textwrap

import pandas as pd
import pytest

import services.database as db_module
from services.database import (
    _create_tables,
    _migrate_schema,
    _migrate_work_hours,
    _migrate_tasks_csv,
    get_work_hours_df,
    get_work_hours_rows,
    append_check_in,
    get_active_session,
    update_check_out,
    insert_work_hours_row,
    update_work_hours_row,
    delete_work_hours_row,
    get_tasks_df,
    get_task_rows,
    insert_task,
    update_task,
    delete_task,
    replace_jira_tasks,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Each test gets its own in-memory connection; resets module singleton."""
    conn = sqlite3.connect(":memory:")
    monkeypatch.setattr(db_module, "_conn", conn)
    _create_tables(conn)
    yield conn
    conn.close()
    monkeypatch.setattr(db_module, "_conn", None)


# ---------------------------------------------------------------------------
# TestDBInit
# ---------------------------------------------------------------------------

class TestDBInit:
    def test_tables_exist(self, isolated_db):
        cur = isolated_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = {r[0] for r in cur.fetchall()}
        assert {"work_hours", "tasks"}.issubset(tables)

    def test_old_tables_not_present(self, isolated_db):
        cur = isolated_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('fixed_tasks','open_tasks')"
        )
        assert cur.fetchall() == []

    def test_create_tables_idempotent(self, isolated_db):
        _create_tables(isolated_db)
        _create_tables(isolated_db)

    def test_work_hours_schema(self, isolated_db):
        cur = isolated_db.execute("PRAGMA table_info(work_hours)")
        cols = {r[1] for r in cur.fetchall()}
        assert {"id", "date", "task", "check_in", "check_out", "message"} == cols

    def test_tasks_schema(self, isolated_db):
        cur = isolated_db.execute("PRAGMA table_info(tasks)")
        cols = {r[1] for r in cur.fetchall()}
        assert {"task", "description", "source"} == cols


# ---------------------------------------------------------------------------
# TestSchemaMigration (legacy fixed_tasks / open_tasks → tasks)
# ---------------------------------------------------------------------------

class TestSchemaMigration:
    def _seed_old_tables(self, conn):
        conn.execute("CREATE TABLE IF NOT EXISTS fixed_tasks (task TEXT PRIMARY KEY, description TEXT DEFAULT '')")
        conn.execute("CREATE TABLE IF NOT EXISTS open_tasks  (task TEXT PRIMARY KEY, description TEXT DEFAULT '')")
        conn.execute("INSERT INTO fixed_tasks VALUES ('FIX-1', 'Fixed desc')")
        conn.execute("INSERT INTO open_tasks  VALUES ('JIRA-1', 'Jira desc')")
        conn.commit()

    def test_old_rows_merged_into_tasks(self, isolated_db):
        self._seed_old_tables(isolated_db)
        _migrate_schema(isolated_db)
        cur = isolated_db.execute("SELECT task, source FROM tasks ORDER BY task")
        rows = {r[0]: r[1] for r in cur.fetchall()}
        assert rows.get('FIX-1') == 'fixed'
        assert rows.get('JIRA-1') == 'jira'

    def test_old_tables_dropped_after_migration(self, isolated_db):
        self._seed_old_tables(isolated_db)
        _migrate_schema(isolated_db)
        cur = isolated_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('fixed_tasks','open_tasks')"
        )
        assert cur.fetchall() == []

    def test_migration_skipped_when_tasks_already_populated(self, isolated_db):
        self._seed_old_tables(isolated_db)
        insert_task('EXISTING', 'already here')
        _migrate_schema(isolated_db)
        cur = isolated_db.execute("SELECT task FROM tasks")
        tasks = {r[0] for r in cur.fetchall()}
        # Old rows NOT imported because tasks table was non-empty
        assert 'FIX-1' not in tasks
        assert 'EXISTING' in tasks


# ---------------------------------------------------------------------------
# TestCSVMigration
# ---------------------------------------------------------------------------

class TestCSVMigration:
    def _write(self, path, content):
        path.write_text(textwrap.dedent(content))

    def test_migrate_work_hours(self, isolated_db, tmp_path, monkeypatch):
        csv = tmp_path / "work_hours.csv"
        self._write(csv, """\
            Date,Task,Check In,Check Out,Message
            2024-01-10,TASK-1,09:00,17:00,did stuff
            2024-01-11,TASK-2,08:00,,
        """)
        monkeypatch.chdir(tmp_path)
        _migrate_work_hours(isolated_db)

        cur = isolated_db.execute("SELECT date, task, check_in, check_out, message FROM work_hours")
        rows = cur.fetchall()
        assert len(rows) == 2
        assert rows[0] == ("2024-01-10", "TASK-1", "09:00", "17:00", "did stuff")
        assert rows[1][3] is None

    def test_migrate_creates_bak_file(self, isolated_db, tmp_path, monkeypatch):
        csv = tmp_path / "work_hours.csv"
        self._write(csv, "Date,Task,Check In,Check Out,Message\n")
        monkeypatch.chdir(tmp_path)
        _migrate_work_hours(isolated_db)
        assert not csv.exists()
        assert (tmp_path / "work_hours.csv.bak").exists()

    def test_migrate_tasks_csv_fixed(self, isolated_db, tmp_path, monkeypatch):
        csv = tmp_path / "fixed_tasks.csv"
        self._write(csv, "Task,Description\nTASK-1,Do something\n")
        monkeypatch.chdir(tmp_path)
        _migrate_tasks_csv(isolated_db, str(csv), 'fixed')

        cur = isolated_db.execute("SELECT task, description, source FROM tasks")
        assert cur.fetchone() == ("TASK-1", "Do something", "fixed")
        assert not csv.exists()

    def test_migrate_tasks_csv_jira(self, isolated_db, tmp_path, monkeypatch):
        csv = tmp_path / "open_tasks.csv"
        self._write(csv, "Task,Description\nJIRA-1,Fix bug\n")
        monkeypatch.chdir(tmp_path)
        _migrate_tasks_csv(isolated_db, str(csv), 'jira')

        cur = isolated_db.execute("SELECT source FROM tasks WHERE task='JIRA-1'")
        assert cur.fetchone()[0] == 'jira'

    def test_migrate_missing_csv_is_silent(self, isolated_db, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _migrate_work_hours(isolated_db)
        _migrate_tasks_csv(isolated_db, "nonexistent.csv", 'fixed')


# ---------------------------------------------------------------------------
# TestWorkHoursCRUD
# ---------------------------------------------------------------------------

class TestWorkHoursCRUD:
    def test_append_check_in_creates_row(self, isolated_db):
        append_check_in("2024-03-01", "TASK-1", "09:00")
        cur = isolated_db.execute("SELECT date, task, check_in, check_out FROM work_hours")
        row = cur.fetchone()
        assert row == ("2024-03-01", "TASK-1", "09:00", None)

    def test_get_active_session_returns_open_row(self, isolated_db):
        append_check_in("2024-03-01", "TASK-1", "09:00")
        session = get_active_session()
        assert session is not None
        _, date, task, check_in = session
        assert date == "2024-03-01"
        assert task == "TASK-1"

    def test_get_active_session_none_when_all_closed(self, isolated_db):
        isolated_db.execute(
            "INSERT INTO work_hours (date, task, check_in, check_out) VALUES ('2024-03-01','T','09:00','17:00')"
        )
        isolated_db.commit()
        assert get_active_session() is None

    def test_update_check_out(self, isolated_db):
        append_check_in("2024-03-01", "TASK-1", "09:00")
        row_id = get_active_session()[0]
        update_check_out(row_id, "17:00")
        cur = isolated_db.execute("SELECT check_out FROM work_hours WHERE id=?", (row_id,))
        assert cur.fetchone()[0] == "17:00"
        assert get_active_session() is None

    def test_get_work_hours_df_types(self, isolated_db):
        isolated_db.execute(
            "INSERT INTO work_hours (date, task, check_in, check_out, message) "
            "VALUES ('2024-03-01','T','09:00','17:00','msg')"
        )
        isolated_db.commit()
        df = get_work_hours_df()
        assert list(df.columns) == ["Date", "Task", "Check In", "Check Out", "Message"]
        assert pd.api.types.is_datetime64_any_dtype(df["Date"])
        assert pd.api.types.is_datetime64_any_dtype(df["Check In"])

    def test_get_work_hours_df_null_checkout_is_nat(self, isolated_db):
        append_check_in("2024-03-01", "TASK-1", "09:00")
        df = get_work_hours_df()
        assert pd.isna(df["Check Out"].iloc[0])

    def test_insert_work_hours_row_returns_id(self, isolated_db):
        row_id = insert_work_hours_row("2024-03-01", "TASK-1", "09:00", "17:00", "note")
        assert isinstance(row_id, int)
        cur = isolated_db.execute("SELECT task FROM work_hours WHERE id=?", (row_id,))
        assert cur.fetchone()[0] == "TASK-1"

    def test_insert_work_hours_row_empty_checkout_stores_null(self, isolated_db):
        row_id = insert_work_hours_row("2024-03-01", "TASK-1", "09:00", "", "")
        cur = isolated_db.execute("SELECT check_out FROM work_hours WHERE id=?", (row_id,))
        assert cur.fetchone()[0] is None

    def test_update_work_hours_row(self, isolated_db):
        row_id = insert_work_hours_row("2024-03-01", "TASK-1", "09:00", "17:00", "")
        update_work_hours_row(row_id, "2024-03-02", "TASK-2", "08:00", "16:00", "updated")
        cur = isolated_db.execute(
            "SELECT date, task, check_in, check_out, message FROM work_hours WHERE id=?",
            (row_id,)
        )
        assert cur.fetchone() == ("2024-03-02", "TASK-2", "08:00", "16:00", "updated")

    def test_delete_work_hours_row(self, isolated_db):
        row_id = insert_work_hours_row("2024-03-01", "TASK-1", "09:00", "17:00", "")
        delete_work_hours_row(row_id)
        cur = isolated_db.execute("SELECT COUNT(*) FROM work_hours WHERE id=?", (row_id,))
        assert cur.fetchone()[0] == 0

    def test_get_work_hours_rows(self, isolated_db):
        insert_work_hours_row("2024-03-01", "TASK-1", "09:00", "17:00", "msg")
        rows = get_work_hours_rows()
        assert len(rows) == 1
        _, date, task, check_in, check_out, message = rows[0]
        assert (date, task, check_in, check_out, message) == ("2024-03-01", "TASK-1", "09:00", "17:00", "msg")


# ---------------------------------------------------------------------------
# TestTasksCRUD
# ---------------------------------------------------------------------------

class TestTasksCRUD:
    def test_insert_and_get_fixed(self, isolated_db):
        insert_task("T-1", "Desc 1")
        df = get_tasks_df()
        assert "T-1" in df["Task"].values

    def test_insert_and_get_jira(self, isolated_db):
        insert_task("JIRA-1", "Jira desc", source='jira')
        rows = get_task_rows()
        assert any(r[0] == 'JIRA-1' and r[2] == 'jira' for r in rows)

    def test_update_task_description(self, isolated_db):
        insert_task("T-1", "old")
        update_task("T-1", "new")
        cur = isolated_db.execute("SELECT description FROM tasks WHERE task='T-1'")
        assert cur.fetchone()[0] == "new"

    def test_delete_task(self, isolated_db):
        insert_task("T-1", "desc")
        delete_task("T-1")
        cur = isolated_db.execute("SELECT COUNT(*) FROM tasks WHERE task='T-1'")
        assert cur.fetchone()[0] == 0

    def test_replace_jira_tasks_only_replaces_jira(self, isolated_db):
        insert_task("FIX-1", "keep me", source='fixed')
        insert_task("OLD-JIRA", "old", source='jira')
        replace_jira_tasks([("NEW-JIRA", "new jira")])
        cur = isolated_db.execute("SELECT task, source FROM tasks ORDER BY task")
        rows = {r[0]: r[1] for r in cur.fetchall()}
        assert rows.get("FIX-1") == 'fixed'
        assert "OLD-JIRA" not in rows
        assert rows.get("NEW-JIRA") == 'jira'

    def test_get_tasks_df_columns(self, isolated_db):
        df = get_tasks_df()
        assert list(df.columns) == ["Task", "Description"]

    def test_get_task_rows_includes_source(self, isolated_db):
        insert_task("T-1", "desc", 'fixed')
        rows = get_task_rows()
        assert len(rows) == 1
        task, description, source = rows[0]
        assert (task, description, source) == ("T-1", "desc", "fixed")

    def test_get_tasks_df_empty(self, isolated_db):
        df = get_tasks_df()
        assert len(df) == 0
        assert list(df.columns) == ["Task", "Description"]


# ---------------------------------------------------------------------------
# TestActiveSession (multi-day checkout)
# ---------------------------------------------------------------------------

class TestActiveSession:
    def test_multiday_checkout_creates_two_rows(self, isolated_db):
        isolated_db.execute(
            "INSERT INTO work_hours (date, task, check_in, check_out) "
            "VALUES ('2024-03-01', 'TASK-1', '23:00', NULL)"
        )
        isolated_db.commit()

        session = get_active_session()
        assert session is not None
        row_id, started_date, task_key, _ = session

        end_date = "2024-03-02"
        end_time = "01:00"

        with isolated_db:
            isolated_db.execute(
                "UPDATE work_hours SET check_out = '23:59' WHERE id = ?", (row_id,)
            )
            isolated_db.execute(
                "INSERT INTO work_hours (date, task, check_in, check_out, message) "
                "VALUES (?, ?, '00:00', ?, '')",
                (end_date, task_key, end_time),
            )

        cur = isolated_db.execute("SELECT date, check_in, check_out FROM work_hours ORDER BY id")
        rows = cur.fetchall()
        assert len(rows) == 2
        assert rows[0] == ("2024-03-01", "23:00", "23:59")
        assert rows[1] == ("2024-03-02", "00:00", "01:00")
        assert get_active_session() is None
