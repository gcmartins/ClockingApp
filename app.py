import csv
import os
import os.path
import sys

from PySide6.QtWidgets import QApplication

from windows.clocking import MainClocking
from services.constants import (
    TASKS_CSV, FIXED_TASK_CSV, OPEN_TASK_CSV, CLOCKING_CSV,
)
from services.database import (
    init_db, get_all_tasks, save_tasks, save_clockings,
    ClockingRecord, TaskRecord,
)


def _migrate_to_sqlite():
    """One-time migration from legacy CSV files into clocking.db.

    Idempotent: if the tasks table already contains rows the function
    returns immediately, leaving the DB untouched.
    """
    init_db()

    # Skip if already migrated
    if get_all_tasks():
        return

    # --- Tasks ---
    task_rows: list[TaskRecord] = []

    if os.path.isfile(TASKS_CSV):
        with open(TASKS_CSV, newline='') as f:
            reader = csv.reader(f)
            next(reader, None)  # skip header
            for row in reader:
                if len(row) >= 3 and row[0].strip():
                    task_rows.append(TaskRecord(
                        task=row[0].strip(),
                        description=row[1].strip(),
                        task_type=row[2].strip() if row[2].strip() in ('fixed', 'open', 'closed') else 'fixed',
                    ))
    else:
        for path, task_type in ((FIXED_TASK_CSV, 'fixed'), (OPEN_TASK_CSV, 'open')):
            if not os.path.isfile(path):
                continue
            with open(path, newline='') as f:
                reader = csv.reader(f)
                next(reader, None)
                for row in reader:
                    if len(row) >= 2 and row[0].strip():
                        task_rows.append(TaskRecord(
                            task=row[0].strip(),
                            description=row[1].strip(),
                            task_type=task_type,
                        ))

    if not task_rows:
        task_rows.append(TaskRecord(
            task='TASK-KEY',
            description=(
                'Task description (you can manage tasks via Menu → Manage Tasks)'
            ),
            task_type='fixed',
        ))

    save_tasks(task_rows)

    # --- Clockings ---
    if not os.path.isfile(CLOCKING_CSV):
        return

    clocking_rows: list[ClockingRecord] = []
    with open(CLOCKING_CSV, newline='') as f:
        reader = csv.reader(f)
        next(reader, None)  # skip header
        for row in reader:
            if len(row) < 3 or not row[0].strip():
                continue
            date = row[0].strip()
            task = row[1].strip()
            check_in_time = row[2].strip()
            check_out_time = row[3].strip() if len(row) > 3 else ''
            message = row[4].strip() if len(row) > 4 else ''

            check_in = f"{date} {check_in_time}" if check_in_time else None
            check_out = f"{date} {check_out_time}" if check_out_time else None

            if not check_in:
                continue

            clocking_rows.append(ClockingRecord(
                id=None,  # AUTOINCREMENT — will be reassigned by DB
                date=date,
                task=task,
                check_in=check_in,
                check_out=check_out,
                message=message or None,
            ))

    if clocking_rows:
        save_clockings(clocking_rows)


if __name__ == '__main__':
    _migrate_to_sqlite()

    app = QApplication(sys.argv)
    widget = MainClocking()
    widget.show()
    exitCode = app.exec()

    if exitCode == MainClocking.EXIT_CODE_REBOOT:
        os.execv(sys.executable, [sys.executable] + sys.argv)
    else:
        sys.exit(exitCode)
