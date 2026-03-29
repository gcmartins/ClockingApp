import os
import sqlite3
import sys
from typing import Optional

import pandas as pd

from services.constants import (
    DB_PATH, CLOCKING_CSV, FIXED_TASK_CSV, OPEN_TASK_CSV,
    CLOCKING_HEADER, TASK_HEADER,
)

_conn: Optional[sqlite3.Connection] = None


def get_connection() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(DB_PATH)
        _conn.execute("PRAGMA journal_mode=WAL")
    return _conn


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_CREATE_WORK_HOURS = """
CREATE TABLE IF NOT EXISTS work_hours (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    date      TEXT NOT NULL,
    task      TEXT NOT NULL,
    check_in  TEXT NOT NULL,
    check_out TEXT,
    message   TEXT DEFAULT ''
)
"""

_CREATE_FIXED_TASKS = """
CREATE TABLE IF NOT EXISTS fixed_tasks (
    task        TEXT PRIMARY KEY,
    description TEXT DEFAULT ''
)
"""

_CREATE_OPEN_TASKS = """
CREATE TABLE IF NOT EXISTS open_tasks (
    task        TEXT PRIMARY KEY,
    description TEXT DEFAULT ''
)
"""


def _create_tables(conn: sqlite3.Connection) -> None:
    conn.execute(_CREATE_WORK_HOURS)
    conn.execute(_CREATE_FIXED_TASKS)
    conn.execute(_CREATE_OPEN_TASKS)
    conn.commit()


# ---------------------------------------------------------------------------
# Initialisation & migration
# ---------------------------------------------------------------------------

def init_db() -> None:
    """Create the database and tables. On first run, migrate existing CSV files."""
    is_new = not os.path.exists(DB_PATH)
    conn = get_connection()
    _create_tables(conn)
    if is_new:
        migrate_from_csv(conn)


def migrate_from_csv(conn: sqlite3.Connection) -> None:
    """One-time import of legacy CSV data into the database."""
    _migrate_work_hours(conn)
    _migrate_tasks(conn, FIXED_TASK_CSV, 'fixed_tasks')
    _migrate_tasks(conn, OPEN_TASK_CSV, 'open_tasks')


def _migrate_work_hours(conn: sqlite3.Connection) -> None:
    if not os.path.exists(CLOCKING_CSV):
        return
    try:
        df = pd.read_csv(CLOCKING_CSV, names=CLOCKING_HEADER, header=0)
        with conn:
            for _, row in df.iterrows():
                check_out = row['Check Out']
                if pd.isna(check_out) or str(check_out).strip() == '':
                    check_out = None
                else:
                    check_out = str(check_out).strip()
                message = row['Message'] if not pd.isna(row['Message']) else ''
                conn.execute(
                    "INSERT INTO work_hours (date, task, check_in, check_out, message) VALUES (?, ?, ?, ?, ?)",
                    (str(row['Date']).strip(), str(row['Task']).strip(),
                     str(row['Check In']).strip(), check_out, str(message)),
                )
        os.rename(CLOCKING_CSV, CLOCKING_CSV + '.bak')
    except Exception as e:
        print(f"Warning: could not migrate {CLOCKING_CSV}: {e}", file=sys.stderr)


def _migrate_tasks(conn: sqlite3.Connection, csv_path: str, table: str) -> None:
    if not os.path.exists(csv_path):
        return
    try:
        df = pd.read_csv(csv_path, names=TASK_HEADER, header=0)
        with conn:
            for _, row in df.iterrows():
                desc = row['Description'] if not pd.isna(row['Description']) else ''
                conn.execute(
                    f"INSERT OR REPLACE INTO {table} (task, description) VALUES (?, ?)",
                    (str(row['Task']).strip(), str(desc)),
                )
        os.rename(csv_path, csv_path + '.bak')
    except Exception as e:
        print(f"Warning: could not migrate {csv_path}: {e}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Work hours — read
# ---------------------------------------------------------------------------

def get_work_hours_df() -> pd.DataFrame:
    """Return a typed DataFrame matching the shape previously produced by load_dataframe()."""
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT date, task, check_in, check_out, message FROM work_hours ORDER BY id",
        conn,
    )
    df.columns = ["Date", "Task", "Check In", "Check Out", "Message"]
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


def get_work_hours_rows() -> list[tuple]:
    """Return raw rows as (id, date, task, check_in, check_out, message) for table display."""
    conn = get_connection()
    cur = conn.execute(
        "SELECT id, date, task, check_in, check_out, message FROM work_hours ORDER BY id"
    )
    return cur.fetchall()


# ---------------------------------------------------------------------------
# Work hours — write (clocking operations)
# ---------------------------------------------------------------------------

def append_check_in(date: str, task: str, check_in: str) -> None:
    conn = get_connection()
    with conn:
        conn.execute(
            "INSERT INTO work_hours (date, task, check_in, check_out, message) VALUES (?, ?, ?, NULL, '')",
            (date, task, check_in),
        )


def get_active_session() -> Optional[tuple]:
    """Return (id, date, task, check_in) for the active (unchecked-out) row, or None."""
    conn = get_connection()
    cur = conn.execute(
        "SELECT id, date, task, check_in FROM work_hours WHERE check_out IS NULL LIMIT 1"
    )
    return cur.fetchone()


def update_check_out(row_id: int, check_out: str) -> None:
    conn = get_connection()
    with conn:
        conn.execute(
            "UPDATE work_hours SET check_out = ? WHERE id = ?",
            (check_out, row_id),
        )


# ---------------------------------------------------------------------------
# Work hours — write (manual record editor)
# ---------------------------------------------------------------------------

def insert_work_hours_row(date: str, task: str, check_in: str,
                          check_out: Optional[str], message: str) -> int:
    """Insert a manually entered row and return its new id."""
    conn = get_connection()
    co = check_out if check_out and check_out.strip() else None
    with conn:
        cur = conn.execute(
            "INSERT INTO work_hours (date, task, check_in, check_out, message) VALUES (?, ?, ?, ?, ?)",
            (date, task, check_in, co, message or ''),
        )
    return cur.lastrowid


def update_work_hours_row(row_id: int, date: str, task: str, check_in: str,
                          check_out: Optional[str], message: str) -> None:
    co = check_out if check_out and check_out.strip() else None
    conn = get_connection()
    with conn:
        conn.execute(
            "UPDATE work_hours SET date=?, task=?, check_in=?, check_out=?, message=? WHERE id=?",
            (date, task, check_in, co, message or '', row_id),
        )


def delete_work_hours_row(row_id: int) -> None:
    conn = get_connection()
    with conn:
        conn.execute("DELETE FROM work_hours WHERE id = ?", (row_id,))


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

def get_tasks_df(table: str) -> pd.DataFrame:
    """Return a DataFrame with columns Task, Description for fixed_tasks or open_tasks."""
    conn = get_connection()
    df = pd.read_sql_query(f"SELECT task, description FROM {table}", conn)
    df.columns = ["Task", "Description"]
    return df


def replace_tasks(table: str, rows: list[tuple[str, str]]) -> None:
    """Atomically replace all rows in the given task table."""
    conn = get_connection()
    with conn:
        conn.execute(f"DELETE FROM {table}")
        conn.executemany(
            f"INSERT INTO {table} (task, description) VALUES (?, ?)", rows
        )
