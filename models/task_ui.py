from PyQt5.QtWidgets import QPushButton, QLabel


class TaskUI:
    def __init__(self, id: str, description: str, button: QPushButton):
        self.id = id
        self.description = description
        self.button = button
        self.label = QLabel(self.description)
