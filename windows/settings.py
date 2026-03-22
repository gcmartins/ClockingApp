from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QLineEdit, QPushButton, QGroupBox, QMessageBox,
                             QFormLayout, QTabWidget, QWidget)
from PyQt5.QtCore import Qt
from services.config_manager import get_config_manager
from services.jira_api import clear_jira_cache
from services.clockify_api import clear_clockify_cache


class SettingsDialog(QDialog):
    """Dialog for configuring API settings"""
    
    def __init__(self, parent=None, check_on_close=True):
        """
        Initialize settings dialog
        
        Args:
            parent: Parent widget
            check_on_close: If True, validate settings when closing with OK
        """
        super().__init__(parent)
        self.check_on_close = check_on_close
        self.config_manager = get_config_manager()
        self.setWindowTitle("API Settings")
        self.setMinimumWidth(500)
        self.setup_ui()
        self.load_current_settings()
    
    def setup_ui(self):
        """Set up the user interface"""
        layout = QVBoxLayout()
        
        # Create tab widget
        tabs = QTabWidget()
        
        # Jira settings tab
        jira_tab = QWidget()
        jira_layout = QVBoxLayout()
        
        jira_group = self.create_jira_group()
        jira_layout.addWidget(jira_group)
        jira_layout.addStretch()
        
        jira_tab.setLayout(jira_layout)
        tabs.addTab(jira_tab, "Jira")
        
        # Clockify settings tab
        clockify_tab = QWidget()
        clockify_layout = QVBoxLayout()
        
        clockify_group = self.create_clockify_group()
        clockify_layout.addWidget(clockify_group)
        clockify_layout.addStretch()
        
        clockify_tab.setLayout(clockify_layout)
        tabs.addTab(clockify_tab, "Clockify")
        
        layout.addWidget(tabs)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        save_button = QPushButton("Save")
        save_button.clicked.connect(self.save_settings)
        button_layout.addWidget(save_button)
        
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def create_jira_group(self) -> QGroupBox:
        """Create Jira settings group"""
        group = QGroupBox("Jira Configuration")
        form_layout = QFormLayout()
        
        # Email
        self.jira_email_input = QLineEdit()
        self.jira_email_input.setPlaceholderText("your@email.com")
        form_layout.addRow("Email:", self.jira_email_input)
        
        # Token with show/hide button
        self.jira_token_input = QLineEdit()
        self.jira_token_input.setEchoMode(QLineEdit.Password)
        self.jira_token_input.setPlaceholderText("Your Jira API token")
        
        show_jira_token_btn = QPushButton("Show")
        show_jira_token_btn.setCheckable(True)
        show_jira_token_btn.toggled.connect(
            lambda checked: self.toggle_password_visibility(self.jira_token_input, show_jira_token_btn, checked)
        )
        token_layout = QHBoxLayout()
        token_layout.addWidget(self.jira_token_input)
        token_layout.addWidget(show_jira_token_btn)
        form_layout.addRow("API Token:", token_layout)
        
        # URL
        self.jira_url_input = QLineEdit()
        self.jira_url_input.setPlaceholderText("https://yourcompany.atlassian.net")
        form_layout.addRow("Atlassian URL:", self.jira_url_input)
        
        # Help text
        help_label = QLabel(
            '<small>To get your API token, visit: '
            '<a href="https://id.atlassian.com/manage-profile/security/api-tokens">'
            'Atlassian API Tokens</a></small>'
        )
        help_label.setOpenExternalLinks(True)
        help_label.setWordWrap(True)
        form_layout.addRow("", help_label)
        
        group.setLayout(form_layout)
        return group
    
    def create_clockify_group(self) -> QGroupBox:
        """Create Clockify settings group"""
        group = QGroupBox("Clockify Configuration")
        form_layout = QFormLayout()
        
        # Workspace
        self.clockify_workspace_input = QLineEdit()
        self.clockify_workspace_input.setPlaceholderText("Your workspace ID")
        form_layout.addRow("Workspace ID:", self.clockify_workspace_input)
        
        # API Key
        self.clockify_api_key_input = QLineEdit()
        self.clockify_api_key_input.setEchoMode(QLineEdit.Password)
        self.clockify_api_key_input.setPlaceholderText("Your Clockify API key")
        
        # Show/hide password button
        show_clockify_key_btn = QPushButton("Show")
        show_clockify_key_btn.setCheckable(True)
        show_clockify_key_btn.toggled.connect(
            lambda checked: self.toggle_password_visibility(self.clockify_api_key_input, show_clockify_key_btn, checked)
        )
        key_layout = QHBoxLayout()
        key_layout.addWidget(self.clockify_api_key_input)
        key_layout.addWidget(show_clockify_key_btn)
        form_layout.addRow("API Key:", key_layout)
        
        # Help text
        help_label = QLabel(
            '<small>To get your API key, visit: '
            '<a href="https://app.clockify.me/user/settings">'
            'Clockify Settings</a></small>'
        )
        help_label.setOpenExternalLinks(True)
        help_label.setWordWrap(True)
        form_layout.addRow("", help_label)
        
        group.setLayout(form_layout)
        return group
    
    def toggle_password_visibility(self, line_edit: QLineEdit, button: QPushButton, show: bool):
        """Toggle password visibility for a line edit"""
        if show:
            line_edit.setEchoMode(QLineEdit.Normal)
            button.setText("Hide")
        else:
            line_edit.setEchoMode(QLineEdit.Password)
            button.setText("Show")
    
    def load_current_settings(self):
        """Load current settings from config manager"""
        self.jira_email_input.setText(self.config_manager.get('ATLASSIAN_EMAIL'))
        self.jira_token_input.setText(self.config_manager.get('ATLASSIAN_TOKEN'))
        self.jira_url_input.setText(self.config_manager.get('ATLASSIAN_URL'))
        self.clockify_workspace_input.setText(self.config_manager.get('CLOCKIFY_WORKSPACE'))
        self.clockify_api_key_input.setText(self.config_manager.get('CLOCKIFY_API_KEY'))
    
    def save_settings(self):
        """Save settings to config manager and close dialog"""
        # Get values from inputs
        settings = {
            'ATLASSIAN_EMAIL': self.jira_email_input.text().strip(),
            'ATLASSIAN_TOKEN': self.jira_token_input.text().strip(),
            'ATLASSIAN_URL': self.jira_url_input.text().strip(),
            'CLOCKIFY_WORKSPACE': self.clockify_workspace_input.text().strip(),
            'CLOCKIFY_API_KEY': self.clockify_api_key_input.text().strip(),
        }
        
        # Update config manager
        self.config_manager.update_all(settings)
        
        # Save to file
        if self.config_manager.save():
            clear_jira_cache()
            clear_clockify_cache()
            QMessageBox.information(
                self,
                "Settings Saved",
                "Your API settings have been saved successfully."
            )
            self.accept()
        else:
            QMessageBox.critical(
                self,
                "Save Failed",
                "Failed to save settings. Please check file permissions."
            )
    
    @staticmethod
    def show_first_time_setup(parent=None) -> bool:
        """
        Show settings dialog for first-time setup
        
        Args:
            parent: Parent widget
            
        Returns:
            True if settings were configured, False otherwise
        """
        dialog = SettingsDialog(parent, check_on_close=False)
        dialog.setWindowTitle("Welcome - Optional API Settings")
        
        # Add welcome message
        welcome_label = QLabel(
            "<b>Welcome to Clocking App!</b><br><br>"
            "The app works without API configuration for basic time tracking.<br><br>"
            "To enable additional features, you can optionally configure:<br>"
            "• <b>Jira</b> - For tracking issues and logging work<br>"
            "• <b>Clockify</b> - For time tracking integration<br><br>"
            "You can configure these now or later via Menu → Settings."
        )
        welcome_label.setWordWrap(True)
        dialog.layout().insertWidget(0, welcome_label)
        
        return dialog.exec_() == QDialog.Accepted
