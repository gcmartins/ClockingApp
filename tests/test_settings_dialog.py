"""Tests for the SettingsDialog UI component (windows/settings.py)."""
import pytest
from PySide6.QtWidgets import QLineEdit, QMessageBox, QPushButton

from services.config_manager import ConfigManager
from windows.settings import SettingsDialog

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def env_path(tmp_path):
    """Return path to a temp .env file."""
    return str(tmp_path / ".env")


@pytest.fixture
def config(env_path):
    """Isolated ConfigManager backed by a temp .env file."""
    return ConfigManager(env_path=env_path)


@pytest.fixture
def dialog(qt_app, config, monkeypatch):
    """SettingsDialog with an isolated ConfigManager."""
    import services.config_manager as cm_module

    monkeypatch.setattr(cm_module, "_config_manager", config)
    monkeypatch.setattr(cm_module, "get_config_manager", lambda: config)
    # Also patch the import inside settings module
    import windows.settings as settings_module
    monkeypatch.setattr(settings_module, "get_config_manager", lambda: config)

    dlg = SettingsDialog(check_on_close=False)
    yield dlg
    dlg.close()


# ---------------------------------------------------------------------------
# TestSettingsDialogLoad
# ---------------------------------------------------------------------------

class TestSettingsDialogLoad:
    def test_empty_config_produces_empty_fields(self, dialog):
        assert dialog.jira_email_input.text() == ""
        assert dialog.jira_token_input.text() == ""
        assert dialog.jira_url_input.text() == ""
        assert dialog.clockify_workspace_input.text() == ""
        assert dialog.clockify_api_key_input.text() == ""

    def test_load_current_settings_populates_fields(self, qt_app, env_path, monkeypatch):
        cfg = ConfigManager(env_path=env_path)
        cfg.update_all({
            'ATLASSIAN_EMAIL': 'user@example.com',
            'ATLASSIAN_TOKEN': 'mytoken',
            'ATLASSIAN_URL': 'https://example.atlassian.net',
            'CLOCKIFY_WORKSPACE': 'ws123',
            'CLOCKIFY_API_KEY': 'ck-key',
        })

        import windows.settings as settings_module
        monkeypatch.setattr(settings_module, "get_config_manager", lambda: cfg)

        dlg = SettingsDialog(check_on_close=False)
        try:
            assert dlg.jira_email_input.text() == 'user@example.com'
            assert dlg.jira_token_input.text() == 'mytoken'
            assert dlg.jira_url_input.text() == 'https://example.atlassian.net'
            assert dlg.clockify_workspace_input.text() == 'ws123'
            assert dlg.clockify_api_key_input.text() == 'ck-key'
        finally:
            dlg.close()


# ---------------------------------------------------------------------------
# TestTogglePasswordVisibility
# ---------------------------------------------------------------------------

class TestTogglePasswordVisibility:
    def test_show_sets_normal_echo_mode(self, dialog):
        line_edit = QLineEdit()
        button = QPushButton("Show")
        dialog.toggle_password_visibility(line_edit, button, show=True)
        assert line_edit.echoMode() == QLineEdit.EchoMode.Normal
        assert button.text() == "Hide"

    def test_hide_sets_password_echo_mode(self, dialog):
        line_edit = QLineEdit()
        line_edit.setEchoMode(QLineEdit.EchoMode.Normal)
        button = QPushButton("Hide")
        dialog.toggle_password_visibility(line_edit, button, show=False)
        assert line_edit.echoMode() == QLineEdit.EchoMode.Password
        assert button.text() == "Show"

    def test_jira_token_starts_as_password(self, dialog):
        assert dialog.jira_token_input.echoMode() == QLineEdit.EchoMode.Password

    def test_clockify_key_starts_as_password(self, dialog):
        assert dialog.clockify_api_key_input.echoMode() == QLineEdit.EchoMode.Password


# ---------------------------------------------------------------------------
# TestSettingsDialogSave
# ---------------------------------------------------------------------------

class TestSettingsDialogSave:
    def test_save_updates_config_with_form_values(self, dialog, config, monkeypatch):
        dialog.jira_email_input.setText("test@example.com")
        dialog.jira_token_input.setText("secret")
        dialog.jira_url_input.setText("https://test.atlassian.net")
        dialog.clockify_workspace_input.setText("ws-abc")
        dialog.clockify_api_key_input.setText("clockify-key")

        saved_data = {}

        def fake_update_all(data):
            saved_data.update(data)

        monkeypatch.setattr(config, "update_all", fake_update_all)
        monkeypatch.setattr(config, "save", lambda: True)
        import windows.settings as settings_module
        monkeypatch.setattr(settings_module, "clear_jira_cache", lambda: None)
        monkeypatch.setattr(settings_module, "clear_clockify_cache", lambda: None)
        monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **kw: None))

        dialog.save_settings()

        assert saved_data['ATLASSIAN_EMAIL'] == 'test@example.com'
        assert saved_data['ATLASSIAN_TOKEN'] == 'secret'
        assert saved_data['ATLASSIAN_URL'] == 'https://test.atlassian.net'
        assert saved_data['CLOCKIFY_WORKSPACE'] == 'ws-abc'
        assert saved_data['CLOCKIFY_API_KEY'] == 'clockify-key'

    def test_save_strips_whitespace(self, dialog, config, monkeypatch):
        dialog.jira_email_input.setText("  user@test.com  ")
        dialog.jira_token_input.setText("")
        dialog.jira_url_input.setText("")
        dialog.clockify_workspace_input.setText("")
        dialog.clockify_api_key_input.setText("")

        saved_data = {}
        monkeypatch.setattr(config, "update_all", lambda d: saved_data.update(d))
        monkeypatch.setattr(config, "save", lambda: True)
        import windows.settings as settings_module
        monkeypatch.setattr(settings_module, "clear_jira_cache", lambda: None)
        monkeypatch.setattr(settings_module, "clear_clockify_cache", lambda: None)
        monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **kw: None))

        dialog.save_settings()

        assert saved_data['ATLASSIAN_EMAIL'] == 'user@test.com'

    def test_save_success_clears_api_caches(self, dialog, config, monkeypatch):
        jira_cleared = []
        clockify_cleared = []

        monkeypatch.setattr(config, "update_all", lambda d: None)
        monkeypatch.setattr(config, "save", lambda: True)
        import windows.settings as settings_module
        monkeypatch.setattr(settings_module, "clear_jira_cache", lambda: jira_cleared.append(True))
        monkeypatch.setattr(settings_module, "clear_clockify_cache", lambda: clockify_cleared.append(True))
        monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **kw: None))

        dialog.save_settings()

        assert jira_cleared == [True]
        assert clockify_cleared == [True]

    def test_save_failure_shows_critical_message(self, dialog, config, monkeypatch):
        monkeypatch.setattr(config, "update_all", lambda d: None)
        monkeypatch.setattr(config, "save", lambda: False)

        critical_called = []
        monkeypatch.setattr(QMessageBox, "critical", staticmethod(lambda *a, **kw: critical_called.append(True)))

        dialog.save_settings()

        assert critical_called == [True]

    def test_save_failure_does_not_clear_caches(self, dialog, config, monkeypatch):
        jira_cleared = []

        monkeypatch.setattr(config, "update_all", lambda d: None)
        monkeypatch.setattr(config, "save", lambda: False)
        import windows.settings as settings_module
        monkeypatch.setattr(settings_module, "clear_jira_cache", lambda: jira_cleared.append(True))
        monkeypatch.setattr(QMessageBox, "critical", staticmethod(lambda *a, **kw: None))

        dialog.save_settings()

        assert jira_cleared == []
