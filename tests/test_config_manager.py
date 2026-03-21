import os
import tempfile
import pytest
from services.config_manager import ConfigManager


class TestConfigManager:
    """Test cases for ConfigManager"""
    
    def test_init_with_no_env_file(self):
        """Test initialization when .env file doesn't exist"""
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = os.path.join(tmpdir, '.env')
            config = ConfigManager(env_path)
            
            # All values should be empty
            for key in config.ALL_REQUIRED_KEYS:
                assert config.get(key) == ''
    
    def test_load_existing_config(self):
        """Test loading existing configuration"""
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = os.path.join(tmpdir, '.env')
            
            # Create .env file with test data
            with open(env_path, 'w') as f:
                f.write('ATLASSIAN_EMAIL=test@example.com\n')
                f.write('ATLASSIAN_TOKEN=test_token\n')
                f.write('ATLASSIAN_URL=https://test.atlassian.net\n')
                f.write('CLOCKIFY_WORKSPACE=test_workspace\n')
                f.write('CLOCKIFY_API_KEY=test_api_key\n')
            
            config = ConfigManager(env_path)
            
            assert config.get('ATLASSIAN_EMAIL') == 'test@example.com'
            assert config.get('ATLASSIAN_TOKEN') == 'test_token'
            assert config.get('ATLASSIAN_URL') == 'https://test.atlassian.net'
            assert config.get('CLOCKIFY_WORKSPACE') == 'test_workspace'
            assert config.get('CLOCKIFY_API_KEY') == 'test_api_key'
    
    def test_set_and_save(self):
        """Test setting and saving configuration"""
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = os.path.join(tmpdir, '.env')
            config = ConfigManager(env_path)
            
            # Set values
            config.set('ATLASSIAN_EMAIL', 'new@example.com')
            config.set('ATLASSIAN_TOKEN', 'new_token')
            config.set('ATLASSIAN_URL', 'https://new.atlassian.net')
            config.set('CLOCKIFY_WORKSPACE', 'new_workspace')
            config.set('CLOCKIFY_API_KEY', 'new_api_key')
            
            # Save
            assert config.save() is True
            
            # Load in new instance to verify persistence
            config2 = ConfigManager(env_path)
            assert config2.get('ATLASSIAN_EMAIL') == 'new@example.com'
            assert config2.get('ATLASSIAN_TOKEN') == 'new_token'
            assert config2.get('ATLASSIAN_URL') == 'https://new.atlassian.net'
            assert config2.get('CLOCKIFY_WORKSPACE') == 'new_workspace'
            assert config2.get('CLOCKIFY_API_KEY') == 'new_api_key'
    
    def test_is_valid_complete_config(self):
        """Test validation with complete configuration"""
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = os.path.join(tmpdir, '.env')
            config = ConfigManager(env_path)
            
            # Set all required values
            config.set('ATLASSIAN_EMAIL', 'test@example.com')
            config.set('ATLASSIAN_TOKEN', 'test_token')
            config.set('ATLASSIAN_URL', 'https://test.atlassian.net')
            config.set('CLOCKIFY_WORKSPACE', 'test_workspace')
            config.set('CLOCKIFY_API_KEY', 'test_api_key')
            
            is_valid, missing = config.is_valid()
            assert is_valid is True
            assert len(missing) == 0
    
    def test_is_valid_incomplete_config(self):
        """Test validation with incomplete configuration"""
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = os.path.join(tmpdir, '.env')
            config = ConfigManager(env_path)
            
            # Set only some values
            config.set('ATLASSIAN_EMAIL', 'test@example.com')
            config.set('CLOCKIFY_WORKSPACE', 'test_workspace')
            
            is_valid, missing = config.is_valid()
            assert is_valid is False
            assert 'ATLASSIAN_TOKEN' in missing
            assert 'ATLASSIAN_URL' in missing
            assert 'CLOCKIFY_API_KEY' in missing
    
    def test_is_jira_configured(self):
        """Test Jira-specific validation"""
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = os.path.join(tmpdir, '.env')
            config = ConfigManager(env_path)
            
            # Set only Jira values
            config.set('ATLASSIAN_EMAIL', 'test@example.com')
            config.set('ATLASSIAN_TOKEN', 'test_token')
            config.set('ATLASSIAN_URL', 'https://test.atlassian.net')
            
            is_valid, missing = config.is_jira_configured()
            assert is_valid is True
            assert len(missing) == 0
    
    def test_is_clockify_configured(self):
        """Test Clockify-specific validation"""
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = os.path.join(tmpdir, '.env')
            config = ConfigManager(env_path)
            
            # Set only Clockify values
            config.set('CLOCKIFY_WORKSPACE', 'test_workspace')
            config.set('CLOCKIFY_API_KEY', 'test_api_key')
            
            is_valid, missing = config.is_clockify_configured()
            assert is_valid is True
            assert len(missing) == 0
    
    def test_update_all(self):
        """Test bulk update of configuration"""
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = os.path.join(tmpdir, '.env')
            config = ConfigManager(env_path)
            
            # Update all at once
            new_config = {
                'ATLASSIAN_EMAIL': 'bulk@example.com',
                'ATLASSIAN_TOKEN': 'bulk_token',
                'ATLASSIAN_URL': 'https://bulk.atlassian.net',
                'CLOCKIFY_WORKSPACE': 'bulk_workspace',
                'CLOCKIFY_API_KEY': 'bulk_api_key',
            }
            config.update_all(new_config)
            
            # Verify
            for key, value in new_config.items():
                assert config.get(key) == value
    
    def test_get_with_default(self):
        """Test getting value with default"""
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = os.path.join(tmpdir, '.env')
            config = ConfigManager(env_path)
            
            # Get non-existent key with default
            value = config.get('NON_EXISTENT_KEY', 'default_value')
            assert value == 'default_value'
    
    def test_get_all(self):
        """Test getting all configuration"""
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = os.path.join(tmpdir, '.env')
            config = ConfigManager(env_path)
            
            # Set some values
            config.set('ATLASSIAN_EMAIL', 'test@example.com')
            config.set('CLOCKIFY_WORKSPACE', 'test_workspace')
            
            all_config = config.get_all()
            
            # Verify it's a copy
            all_config['ATLASSIAN_EMAIL'] = 'modified@example.com'
            assert config.get('ATLASSIAN_EMAIL') == 'test@example.com'
