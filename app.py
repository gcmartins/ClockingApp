import csv
import os
import os.path
import sys

from PySide6.QtWidgets import QApplication

from windows.clocking import MainClocking
from services.constants import (
    TASKS_CSV, FIXED_TASK_CSV, OPEN_TASK_CSV,
    CLOCKING_CSV, CLOCKING_HEADER, TASK_HEADER,
)

APP_FILE_HEADERS = {
    CLOCKING_CSV: CLOCKING_HEADER,
    TASKS_CSV: TASK_HEADER,
}


def _migrate_tasks_csv():
    """Create tasks.csv, migrating from old split CSVs if they exist."""
    if os.path.isfile(TASKS_CSV):
        return

    rows = []

    for path, task_type in ((FIXED_TASK_CSV, 'fixed'), (OPEN_TASK_CSV, 'open')):
        if not os.path.isfile(path):
            continue
        with open(path, newline='') as f:
            reader = csv.reader(f)
            next(reader, None)  # skip old header
            for row in reader:
                if len(row) >= 2 and row[0].strip():
                    rows.append([row[0], row[1], task_type])

    if not rows:
        rows.append([
            'TASK-KEY',
            f'Task description (you can manage tasks via Menu → Manage Tasks or edit "{os.path.abspath(TASKS_CSV)}")',
            'fixed',
        ])

    with open(TASKS_CSV, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(TASK_HEADER)
        writer.writerows(rows)


if __name__ == '__main__':
    _migrate_tasks_csv()

    # Initialize remaining CSV files (clocking) if they don't exist
    for filename, header in APP_FILE_HEADERS.items():
        if not os.path.isfile(filename):
            with open(filename, 'w') as f:
                f.write(','.join(header) + '\n')

    app = QApplication(sys.argv)
    widget = MainClocking()
    widget.show()
    exitCode = app.exec()

    if exitCode == MainClocking.EXIT_CODE_REBOOT:
        os.execv(sys.executable, [sys.executable] + sys.argv)
    else:
        sys.exit(exitCode)
