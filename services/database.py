"""SQLite database access layer for ClockingApp."""
import datetime
import sqlite3
from dataclasses import dataclass
from typing import Optional

DB_FILE = 'clocking.db'


# ---------------------------------------------------------------------------
# Data objects
# ---------------------------------------------------------------------------

@dataclass
class ClockingRecord:
    date: str                   # YYYY-MM-DD
    task: str
    check_in: str               # YYYY-MM-DD HH:MM  (full datetime)
    check_out: Optional[str]    # YYYY-MM-DD HH:MM or None
    message: Optional[str]
    id: Optional[int] = None

    @property
    def check_in_time(self) -> str:
        """Return the HH:MM portion of check_in (for UI display)."""
        return self.check_in[11:] if self.check_in and len(self.check_in) >= 16 else self.check_in or ""

    @property
    def check_out_time(self) -> Optional[str]:
        """Return the HH:MM portion of check_out (for UI display), or None."""
        if self.check_out and len(self.check_out) >= 16:
            return self.check_out[11:]
        return self.check_out


@dataclass
class TaskRecord:
    task: str
    description: str
    task_type: str   # 'fixed' | 'open' | 'closed'


@dataclass
class TaskDuration:
    task: str
    total_seconds: int   # computed in SQL via julianday()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def get_db_path() -> str:
    return DB_FILE


def _get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _clocking_from_row(row: sqlite3.Row) -> ClockingRecord:
    return ClockingRecord(
        id=row['id'],
        date=row['date'],
        task=row['task'],
        check_in=row['check_in'],
        check_out=row['check_out'],
        message=row['message'],
    )


def _task_from_row(row: sqlite3.Row) -> TaskRecord:
    return TaskRecord(
        task=row['task'],
        description=row['description'],
        task_type=row['task_type'],
    )


def _task_duration_from_row(row: sqlite3.Row) -> TaskDuration:
    return TaskDuration(
        task=row['task'],
        total_seconds=row['total_seconds'] or 0,
    )


# ---------------------------------------------------------------------------
# Schema initialisation
# ---------------------------------------------------------------------------

def init_db() -> None:
    """Create tables if they do not yet exist."""
    with _get_connection() as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS clockings (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                date      TEXT NOT NULL,
                task      TEXT NOT NULL,
                check_in  TEXT NOT NULL,
                check_out TEXT,
                message   TEXT
            );
            CREATE TABLE IF NOT EXISTS tasks (
                task        TEXT PRIMARY KEY,
                description TEXT NOT NULL,
                task_type   TEXT NOT NULL
                    CHECK(task_type IN ('fixed', 'open', 'closed'))
            );
        """)


# ---------------------------------------------------------------------------
# Clocking queries
# ---------------------------------------------------------------------------

def get_all_clockings() -> list[ClockingRecord]:
    """Return all clocking rows ordered by check_in."""
    with _get_connection() as conn:
        rows = conn.execute(
            "SELECT id, date, task, check_in, check_out, message "
            "FROM clockings ORDER BY check_in"
        ).fetchall()
    return [_clocking_from_row(r) for r in rows]


def get_clockings_for_date(date: str) -> list[ClockingRecord]:
    """Return completed clocking rows for a given date (YYYY-MM-DD)."""
    with _get_connection() as conn:
        rows = conn.execute(
            "SELECT id, date, task, check_in, check_out, message "
            "FROM clockings WHERE date = ? AND check_out IS NOT NULL "
            "ORDER BY check_in",
            (date,),
        ).fetchall()
    return [_clocking_from_row(r) for r in rows]


def get_open_clocking() -> Optional[ClockingRecord]:
    """Return the clocking row with no check_out (the active session), or None."""
    with _get_connection() as conn:
        row = conn.execute(
            "SELECT id, date, task, check_in, check_out, message "
            "FROM clockings WHERE check_out IS NULL ORDER BY id DESC LIMIT 1"
        ).fetchone()
    return _clocking_from_row(row) if row else None


def get_today_completed_seconds(date: str) -> int:
    """Return sum of completed session durations for date, in seconds."""
    with _get_connection() as conn:
        row = conn.execute(
            "SELECT COALESCE("
            "  CAST(ROUND(SUM((julianday(check_out) - julianday(check_in)) * 86400)) AS INTEGER),"
            "  0"
            ") AS secs "
            "FROM clockings WHERE date = ? AND check_out IS NOT NULL",
            (date,),
        ).fetchone()
    return row['secs'] if row else 0


def get_task_durations_for_date(date: str) -> list[TaskDuration]:
    """Return per-task summed durations for date, computed in SQL."""
    with _get_connection() as conn:
        rows = conn.execute(
            "SELECT task, "
            "  CAST(ROUND(SUM((julianday(check_out) - julianday(check_in)) * 86400)) AS INTEGER)"
            "  AS total_seconds "
            "FROM clockings "
            "WHERE date = ? AND check_out IS NOT NULL "
            "GROUP BY task ORDER BY task",
            (date,),
        ).fetchall()
    return [_task_duration_from_row(r) for r in rows]


def insert_clocking(date: str, task: str, check_in: str, check_out: Optional[str] = None) -> None:
    """Insert a new clocking row."""
    with _get_connection() as conn:
        conn.execute(
            "INSERT INTO clockings (date, task, check_in, check_out) VALUES (?, ?, ?, ?)",
            (date, task, check_in, check_out),
        )


def update_check_out(row_id: int, check_out: str) -> None:
    """Set check_out on an existing clocking row."""
    with _get_connection() as conn:
        conn.execute(
            "UPDATE clockings SET check_out = ? WHERE id = ?",
            (check_out, row_id),
        )


def upsert_clocking(record: ClockingRecord) -> int:
    """Insert or update a single clocking row. Returns the row id."""
    with _get_connection() as conn:
        if record.id:
            conn.execute(
                "UPDATE clockings SET date=?, task=?, check_in=?, check_out=?, message=? WHERE id=?",
                (record.date, record.task, record.check_in, record.check_out, record.message, record.id),
            )
            return record.id
        else:
            cursor = conn.execute(
                "INSERT INTO clockings (date, task, check_in, check_out, message) VALUES (?, ?, ?, ?, ?)",
                (record.date, record.task, record.check_in, record.check_out, record.message),
            )
            return cursor.lastrowid


def delete_clocking(row_id: int) -> None:
    """Delete a single clocking row by id."""
    with _get_connection() as conn:
        conn.execute("DELETE FROM clockings WHERE id = ?", (row_id,))


def save_clockings(records: list[ClockingRecord]) -> None:
    """Replace the entire clockings table with the supplied records."""
    with _get_connection() as conn:
        conn.execute("DELETE FROM clockings")
        conn.executemany(
            "INSERT INTO clockings (id, date, task, check_in, check_out, message) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [
                (r.id, r.date, r.task, r.check_in, r.check_out, r.message)
                for r in records
            ],
        )


# ---------------------------------------------------------------------------
# Task queries
# ---------------------------------------------------------------------------

def get_all_tasks() -> list[TaskRecord]:
    """Return all task rows ordered by task key."""
    with _get_connection() as conn:
        rows = conn.execute(
            "SELECT task, description, task_type FROM tasks ORDER BY task"
        ).fetchall()
    return [_task_from_row(r) for r in rows]


def get_task_descriptions() -> dict[str, str]:
    """Return a {task: description} mapping for all tasks."""
    with _get_connection() as conn:
        rows = conn.execute("SELECT task, description FROM tasks").fetchall()
    return {row['task']: row['description'] for row in rows}


def save_tasks(records: list[TaskRecord]) -> None:
    """Replace the entire tasks table with the supplied records."""
    with _get_connection() as conn:
        conn.execute("DELETE FROM tasks")
        conn.executemany(
            "INSERT INTO tasks (task, description, task_type) VALUES (?, ?, ?)",
            [(r.task, r.description, r.task_type) for r in records],
        )


def upsert_tasks(issues: list[dict]) -> None:
    """Insert or update task rows from a list of {task, description} dicts."""
    with _get_connection() as conn:
        for issue in issues:
            conn.execute(
                "INSERT INTO tasks (task, description, task_type) VALUES (?, ?, 'open') "
                "ON CONFLICT(task) DO UPDATE SET description=excluded.description, task_type='open'",
                (issue['task'], issue['description']),
            )


def mark_stale_open_tasks_closed(active_task_ids: set[str]) -> None:
    """Set task_type='closed' for any 'open' task not in active_task_ids."""
    with _get_connection() as conn:
        rows = conn.execute(
            "SELECT task FROM tasks WHERE task_type = 'open'"
        ).fetchall()
        stale = [r['task'] for r in rows if r['task'] not in active_task_ids]
        if stale:
            conn.executemany(
                "UPDATE tasks SET task_type = 'closed' WHERE task = ?",
                [(t,) for t in stale],
            )
