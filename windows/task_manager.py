from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QMessageBox,
    QPushButton,
    QStyledItemDelegate,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from services.constants import TASK_HEADER, TASK_TYPES
from services.database import TaskRecord, get_all_tasks, save_tasks


class _TaskTypeDelegate(QStyledItemDelegate):
    """Delegate that renders a QComboBox for the Task Type column."""

    def createEditor(self, parent, option, index):
        combo = QComboBox(parent)
        combo.addItems(TASK_TYPES)
        return combo

    def setEditorData(self, editor, index):
        value = index.data(Qt.ItemDataRole.EditRole) or TASK_TYPES[0]
        i = editor.findText(value)
        editor.setCurrentIndex(i if i >= 0 else 0)

    def setModelData(self, editor, model, index):
        model.setData(index, editor.currentText(), Qt.ItemDataRole.EditRole)

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)


class TaskManagerDialog(QDialog):
    """Dialog for creating, editing, and deleting tasks."""

    _COL_TASK = 0
    _COL_DESC = 1
    _COL_TYPE = 2

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manage Tasks")
        self.setMinimumSize(640, 400)

        self._table = QTableWidget()
        self._table.setColumnCount(len(TASK_HEADER))
        self._table.setHorizontalHeaderLabels(TASK_HEADER)
        self._table.setItemDelegateForColumn(self._COL_TYPE, _TaskTypeDelegate(self))
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked |
            QAbstractItemView.EditTrigger.SelectedClicked |
            QAbstractItemView.EditTrigger.EditKeyPressed
        )
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(self._COL_TASK, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self._COL_TYPE, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self._COL_DESC, QHeaderView.ResizeMode.Stretch)

        self._load_tasks()

        add_btn = QPushButton("Add Task")
        add_btn.clicked.connect(self._add_row)
        delete_btn = QPushButton("Delete Selected")
        delete_btn.clicked.connect(self._delete_selected)

        row_btns = QHBoxLayout()
        row_btns.addWidget(add_btn)
        row_btns.addWidget(delete_btn)
        row_btns.addStretch()

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._save)
        button_box.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addWidget(self._table)
        layout.addLayout(row_btns)
        layout.addWidget(button_box)
        self.setLayout(layout)

    def _load_tasks(self):
        tasks = get_all_tasks()
        self._table.blockSignals(True)
        self._table.setRowCount(0)
        for t in tasks:
            self._insert_row(t.task, t.description, t.task_type)
        self._table.blockSignals(False)

    def _insert_row(self, task: str = '', description: str = '', task_type: str = 'fixed'):
        row_idx = self._table.rowCount()
        self._table.insertRow(row_idx)
        self._table.setItem(row_idx, self._COL_TASK, QTableWidgetItem(task))
        self._table.setItem(row_idx, self._COL_DESC, QTableWidgetItem(description))
        type_item = QTableWidgetItem(task_type if task_type in TASK_TYPES else 'fixed')
        self._table.setItem(row_idx, self._COL_TYPE, type_item)

    def _add_row(self):
        self._insert_row()
        self._table.scrollToBottom()
        self._table.setCurrentCell(self._table.rowCount() - 1, self._COL_TASK)

    def _delete_selected(self):
        selected_rows = sorted(
            {idx.row() for idx in self._table.selectedIndexes()},
            reverse=True,
        )
        if not selected_rows:
            QMessageBox.information(self, "No Selection", "Please select a row to delete.")
            return
        confirm = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Delete {len(selected_rows)} row(s)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        for row_idx in selected_rows:
            self._table.removeRow(row_idx)

    def _collect_rows(self) -> list[tuple]:
        rows = []
        for row_idx in range(self._table.rowCount()):
            task = (self._table.item(row_idx, self._COL_TASK) or QTableWidgetItem()).text().strip()
            desc = (self._table.item(row_idx, self._COL_DESC) or QTableWidgetItem()).text().strip()
            task_type = (self._table.item(row_idx, self._COL_TYPE) or QTableWidgetItem()).text().strip()
            rows.append((task, desc, task_type))
        return rows

    def _save(self):
        rows = self._collect_rows()
        errors = []
        for i, (task, _, task_type) in enumerate(rows, start=1):
            if not task:
                errors.append(f"Row {i}: Task field is empty.")
            if task_type not in TASK_TYPES:
                errors.append(f"Row {i}: Invalid task type '{task_type}'.")

        if errors:
            QMessageBox.critical(
                self,
                "Validation Error",
                "Cannot save due to the following errors:\n\n" + "\n".join(errors),
            )
            return

        records = [
            TaskRecord(task=task, description=desc, task_type=task_type)
            for task, desc, task_type in rows
        ]
        save_tasks(records)
        self.accept()
