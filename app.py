import os
import os.path
import sys

from PySide6.QtWidgets import QApplication

from windows.clocking import MainClocking

from services.database import init_db


if __name__ == '__main__':
    init_db()

    app = QApplication(sys.argv)
    widget = MainClocking()
    widget.show()
    exitCode = app.exec()

    if exitCode == MainClocking.EXIT_CODE_REBOOT:
        os.execv(sys.executable, [sys.executable] + sys.argv)
    else:
        sys.exit(exitCode)
