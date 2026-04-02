import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="session")
def qt_app():
    """Session-scoped QApplication required by all Qt widget tests."""
    app = QApplication.instance() or QApplication([])
    yield app
