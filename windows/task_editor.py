from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
)

from services import database as db

_COL_TASK = 0
_COL_DESC = 1
_COL_SRC = 2
_COLUMNS = ["Task", "Description", "Source"]


class TaskEditor(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manage Tasks")
        self.setMinimumSize(600, 400)
        self._setup_ui()
        self.refresh()

    def _setup_ui(self):
        layout = QVBoxLayout()

        self.table = QTableWidget()
        self.table.setColumnCount(len(_COLUMNS))
        self.table.setHorizontalHeaderLabels(_COLUMNS)
        self.table.horizontalHeader().setSectionResizeMode(
            _COL_DESC, QHeaderView.ResizeMode.Stretch
        )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.DoubleClicked)
        layout.addWidget(self.table)

        btn_row = QHBoxLayout()
        self.btn_add = QPushButton("Add Task")
        self.btn_save = QPushButton("Save Changes")
        self.btn_delete = QPushButton("Delete Task")
        self.btn_refresh = QPushButton("Refresh")
        self.btn_add.clicked.connect(self._add_row)
        self.btn_save.clicked.connect(self._save_changes)
        self.btn_delete.clicked.connect(self._delete_row)
        self.btn_refresh.clicked.connect(self.refresh)
        btn_row.addWidget(self.btn_add)
        btn_row.addWidget(self.btn_save)
        btn_row.addWidget(self.btn_delete)
        btn_row.addWidget(self.btn_refresh)
        layout.addLayout(btn_row)

        self.setLayout(layout)

    def refresh(self):
        rows = db.get_task_rows()
        self.table.setRowCount(len(rows))
        for r, (task, description, source) in enumerate(rows):
            self._set_row(r, task, description, source, is_new=False)

    def _set_row(self, r: int, task: str, description: str, source: str, is_new: bool):
        task_item = QTableWidgetItem(task)
        if not is_new:
            task_item.setFlags(task_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.table.setItem(r, _COL_TASK, task_item)

        self.table.setItem(r, _COL_DESC, QTableWidgetItem(description))

        src_item = QTableWidgetItem(source)
        src_item.setFlags(src_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.table.setItem(r, _COL_SRC, src_item)

    def _add_row(self):
        r = self.table.rowCount()
        self.table.insertRow(r)
        self._set_row(r, '', '', 'fixed', is_new=True)
        self.table.scrollToBottom()
        self.table.editItem(self.table.item(r, _COL_TASK))

    def _save_changes(self):
        for r in range(self.table.rowCount()):
            task_item = self.table.item(r, _COL_TASK)
            if task_item is None:
                continue
            task = task_item.text().strip()
            description = (self.table.item(r, _COL_DESC).text() or '').strip()
            source = (self.table.item(r, _COL_SRC).text() or 'fixed').strip()

            if not task:
                continue

            # Determine if this is a new row (task key is editable) or existing
            is_editable = bool(task_item.flags() & Qt.ItemFlag.ItemIsEditable)
            if is_editable:
                db.insert_task(task, description, source)
                # Lock task key now that it's persisted
                task_item.setFlags(task_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            else:
                db.update_task(task, description)

    def _delete_row(self):
        r = self.table.currentRow()
        if r < 0:
            return
        task_item = self.table.item(r, _COL_TASK)
        task = task_item.text().strip() if task_item else ''

        is_new = bool(task_item.flags() & Qt.ItemFlag.ItemIsEditable) if task_item else True
        if not is_new and task:
            db.delete_task(task)
        self.table.removeRow(r)
