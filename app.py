import os
import os.path
import sys

from PySide6.QtWidgets import QApplication

from windows.clocking import MainClocking
from services.constants import FIXED_TASK_CSV, OPEN_TASK_CSV, CLOCKING_CSV, CLOCKING_HEADER, TASK_HEADER

APP_FILE_HEADERS = {
    CLOCKING_CSV: CLOCKING_HEADER,
    FIXED_TASK_CSV: TASK_HEADER,
    OPEN_TASK_CSV: TASK_HEADER,
}

if __name__ == '__main__':
    # Initialize CSV files if they don't exist
    for filename, header in APP_FILE_HEADERS.items():
        if not os.path.isfile(filename):
            with open(filename, "w") as f:
                f.write(','.join(header) + '\n')
                if filename == FIXED_TASK_CSV:
                    f.write(f'TASK-KEY,Task description (you can change it by editing "{os.path.abspath(f.name)}" file)\n')

    app = QApplication(sys.argv)
    widget = MainClocking()
    widget.show()
    exitCode = app.exec()

    if exitCode == MainClocking.EXIT_CODE_REBOOT:
        os.execv(sys.executable, [sys.executable] + sys.argv)
    else:
        sys.exit(exitCode)
