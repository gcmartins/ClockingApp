import os
from typing import Optional, Dict
from dotenv import set_key, find_dotenv, dotenv_values


class ConfigManager:
    """Manages application configuration stored in .env file"""
    
    # Required configuration keys
    REQUIRED_JIRA_KEYS = ['ATLASSIAN_EMAIL', 'ATLASSIAN_TOKEN', 'ATLASSIAN_URL']
    REQUIRED_CLOCKIFY_KEYS = ['CLOCKIFY_WORKSPACE', 'CLOCKIFY_API_KEY']
    ALL_REQUIRED_KEYS = REQUIRED_JIRA_KEYS + REQUIRED_CLOCKIFY_KEYS
    
    def __init__(self, env_path: Optional[str] = None):
        """
        Initialize config manager
        
        Args:
            env_path: Path to .env file. If None, will search for .env in current directory
        """
        self.env_path = env_path or find_dotenv() or '.env'
        self._config = {}
        self.load_config()
    
    def load_config(self) -> None:
        """Load configuration from .env file"""
        # Load values directly from .env file without modifying process environment
        if os.path.exists(self.env_path):
            env_values = dotenv_values(self.env_path)
            self._config = {
                key: env_values.get(key, '') for key in self.ALL_REQUIRED_KEYS
            }
        else:
            # If file doesn't exist, initialize with empty values
            self._config = {
                key: '' for key in self.ALL_REQUIRED_KEYS
            }
    
    def get(self, key: str, default: str = '') -> str:
        """
        Get configuration value
        
        Args:
            key: Configuration key
            default: Default value if key not found
            
        Returns:
            Configuration value
        """
        return self._config.get(key, default)
    
    def set(self, key: str, value: str) -> None:
        """
        Set configuration value (in memory only, call save() to persist)
        
        Args:
            key: Configuration key
            value: Configuration value
        """
        self._config[key] = value
    
    def save(self) -> bool:
        """
        Save configuration to .env file

        Returns:
            True if successful, False otherwise
        """
        try:
            # Write all configuration values (set_key creates the file if missing)
            for key, value in self._config.items():
                set_key(self.env_path, key, value)

            # Reload to ensure consistency
            self.load_config()
            return True
        except Exception as e:
            print(f"Error saving configuration: {e}")
            return False
    
    def get_all(self) -> Dict[str, str]:
        """
        Get all configuration values
        
        Returns:
            Dictionary of all configuration values
        """
        return self._config.copy()
    
    def update_all(self, config: Dict[str, str]) -> None:
        """
        Update multiple configuration values at once
        
        Args:
            config: Dictionary of configuration key-value pairs
        """
        self._config.update(config)
    
    def _is_configured(self, keys: list[str]) -> tuple[bool, list[str]]:
        missing_keys = [key for key in keys if not self._config.get(key, '').strip()]
        return len(missing_keys) == 0, missing_keys

    def is_valid(self) -> tuple[bool, list[str]]:
        """
        Check if all required configuration is present and non-empty

        Returns:
            Tuple of (is_valid, list of missing keys)
        """
        return self._is_configured(self.ALL_REQUIRED_KEYS)

    def is_jira_configured(self) -> tuple[bool, list[str]]:
        """
        Check if Jira configuration is complete

        Returns:
            Tuple of (is_valid, list of missing keys)
        """
        return self._is_configured(self.REQUIRED_JIRA_KEYS)

    def is_clockify_configured(self) -> tuple[bool, list[str]]:
        """
        Check if Clockify configuration is complete

        Returns:
            Tuple of (is_valid, list of missing keys)
        """
        return self._is_configured(self.REQUIRED_CLOCKIFY_KEYS)


# Global instance
_config_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """Get or create the global ConfigManager instance"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager
