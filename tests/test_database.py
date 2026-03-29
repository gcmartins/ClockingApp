import os
import sqlite3
import textwrap
from unittest.mock import patch

import pandas as pd
import pytest

import services.database as db_module
from services.database import (
    _create_tables,
    _migrate_work_hours,
    _migrate_tasks,
    get_work_hours_df,
    get_work_hours_rows,
    append_check_in,
    get_active_session,
    update_check_out,
    insert_work_hours_row,
    update_work_hours_row,
    delete_work_hours_row,
    get_tasks_df,
    replace_tasks,
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
        assert {"work_hours", "fixed_tasks", "open_tasks"}.issubset(tables)

    def test_create_tables_idempotent(self, isolated_db):
        # calling again must not raise
        _create_tables(isolated_db)
        _create_tables(isolated_db)

    def test_work_hours_schema(self, isolated_db):
        cur = isolated_db.execute("PRAGMA table_info(work_hours)")
        cols = {r[1] for r in cur.fetchall()}
        assert {"id", "date", "task", "check_in", "check_out", "message"} == cols

    def test_task_table_schema(self, isolated_db):
        for table in ("fixed_tasks", "open_tasks"):
            cur = isolated_db.execute(f"PRAGMA table_info({table})")
            cols = {r[1] for r in cur.fetchall()}
            assert {"task", "description"} == cols


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
        assert rows[1][3] is None  # active session → NULL

    def test_migrate_creates_bak_file(self, isolated_db, tmp_path, monkeypatch):
        csv = tmp_path / "work_hours.csv"
        self._write(csv, "Date,Task,Check In,Check Out,Message\n")
        monkeypatch.chdir(tmp_path)
        _migrate_work_hours(isolated_db)
        assert not csv.exists()
        assert (tmp_path / "work_hours.csv.bak").exists()

    def test_migrate_tasks(self, isolated_db, tmp_path, monkeypatch):
        csv = tmp_path / "fixed_tasks.csv"
        self._write(csv, "Task,Description\nTASK-1,Do something\n")
        monkeypatch.chdir(tmp_path)
        _migrate_tasks(isolated_db, str(csv), "fixed_tasks")

        cur = isolated_db.execute("SELECT task, description FROM fixed_tasks")
        assert cur.fetchone() == ("TASK-1", "Do something")
        assert not csv.exists()

    def test_migrate_missing_csv_is_silent(self, isolated_db, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        # Should not raise
        _migrate_work_hours(isolated_db)
        _migrate_tasks(isolated_db, "nonexistent.csv", "fixed_tasks")


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
    @pytest.mark.parametrize("table", ["fixed_tasks", "open_tasks"])
    def test_replace_and_get(self, isolated_db, table):
        replace_tasks(table, [("T-1", "Desc 1"), ("T-2", "Desc 2")])
        df = get_tasks_df(table)
        assert list(df["Task"]) == ["T-1", "T-2"]
        assert list(df["Description"]) == ["Desc 1", "Desc 2"]

    @pytest.mark.parametrize("table", ["fixed_tasks", "open_tasks"])
    def test_replace_is_atomic(self, isolated_db, table):
        replace_tasks(table, [("T-OLD", "old")])
        replace_tasks(table, [("T-NEW", "new")])
        df = get_tasks_df(table)
        assert len(df) == 1
        assert df["Task"].iloc[0] == "T-NEW"

    def test_get_tasks_df_empty_table(self, isolated_db):
        df = get_tasks_df("fixed_tasks")
        assert len(df) == 0
        assert list(df.columns) == ["Task", "Description"]


# ---------------------------------------------------------------------------
# TestActiveSession (multi-day checkout)
# ---------------------------------------------------------------------------

class TestActiveSession:
    def test_multiday_checkout_creates_two_rows(self, isolated_db):
        # Simulate a check-in on a previous date
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
