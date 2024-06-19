import os.path

from PyQt5.QtWidgets import QApplication

from windows.clocking import MainClocking
from services.constants import FIXED_TASK_CSV, OPEN_TASK_CSV, CLOCKING_CSV, CLOCKING_HEADER, TASK_HEADER

APP_FILE_HEADERS = {
    CLOCKING_CSV: CLOCKING_HEADER,
    FIXED_TASK_CSV: TASK_HEADER,
    OPEN_TASK_CSV: TASK_HEADER,
}

if __name__ == '__main__':
    for filename, header in APP_FILE_HEADERS.items():
        if not os.path.isfile(filename):
            with open(filename, "w") as f:
                f.write(','.join(header) + '\n')
                if filename == FIXED_TASK_CSV:
                    f.write(f'TASK-KEY,Task description (you can change it by editing "{os.path.abspath(f.name)}" file)\n')

    currentExitCode = MainClocking.EXIT_CODE_REBOOT
    while currentExitCode == MainClocking.EXIT_CODE_REBOOT:
        app = QApplication([])
        widget = MainClocking()
        widget.show()
        currentExitCode = app.exec_()
        app = None  # delete the QApplication object
