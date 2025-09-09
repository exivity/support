"""
Configuration Management for Exivity CLI

Handles loading and managing configuration from YAML files.
"""

import os
import yaml
from typing import Dict, Any, Optional
from pathlib import Path


class Config:
    """Configuration manager for Exivity CLI"""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize configuration manager
        
        Args:
            config_path: Path to config file. If None, looks for config.yaml in CLI directory
        """
        self._config = {}
        self._config_path = self._find_config_file(config_path)
        self.load_config()
    
    def _find_config_file(self, config_path: Optional[str] = None) -> str:
        """Find configuration file"""
        if config_path and os.path.exists(config_path):
            return config_path
        
        # Look for config.yaml in the CLI directory
        cli_dir = Path(__file__).parent.parent
        default_config = cli_dir / "config.yaml"
        
        if default_config.exists():
            return str(default_config)
        
        # If no config found, we'll create a minimal default
        return str(default_config)
    
    def load_config(self):
        """Load configuration from YAML file"""
        try:
            with open(self._config_path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f) or {}
                print(f"📄 Loaded configuration from: {self._config_path}")
        except FileNotFoundError:
            print(f"⚠️  Configuration file not found: {self._config_path}")
            print("   Using default configuration...")
            self._config = self._get_default_config()
        except yaml.YAMLError as e:
            print(f"❌ Error parsing configuration file: {e}")
            print("   Using default configuration...")
            self._config = self._get_default_config()
        except Exception as e:
            print(f"❌ Error loading configuration: {e}")
            print("   Using default configuration...")
            self._config = self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration if file is missing"""
        return {
            "connection": {
                "hostname": "localhost",
                "port": 443,
                "username": "",
                "password": "",
                "token": "",
                "verify_ssl": False,
                "protocol": "https"
            },
            "environments": {
                "count": 24,
                "naming": {
                    "prefix": "hour_",
                    "suffix_format": "{:02d}"
                },
                "variables": [
                    {
                        "name": "hour",
                        "value_format": "{:02d}",
                        "encrypted": False
                    }
                ]
            },
            "workflows": {
                "default_from_offset": 0,
                "default_to_offset": 0,
                "default_timeout": 3600,
                "default_wait": True
            },
            "rates": {
                "default_cogs": 0.0,
                "default_rate": 0.0,
                "csv_export": {
                    "include_service_names": True,
                    "date_format": "YYYYMMDD"
                }
            },
            "api": {
                "timeout": 30,
                "max_retries": 3,
                "retry_delay": 1,
                "default_page_size": 100,
                "max_page_size": 1000
            },
            "logging": {
                "level": "INFO",
                "show_debug_output": False,
                "show_api_requests": False
            },
            "paths": {
                "csv_directory": "csv",
                "logs_directory": "logs",
                "environments_directory": "environments"
            }
        }
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """Get configuration value using dot notation
        
        Args:
            key_path: Path to config value (e.g., 'connection.hostname')
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        keys = key_path.split('.')
        value = self._config
        
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default
    
    def set(self, key_path: str, value: Any):
        """Set configuration value using dot notation
        
        Args:
            key_path: Path to config value (e.g., 'connection.hostname')
            value: Value to set
        """
        keys = key_path.split('.')
        config_ref = self._config
        
        # Navigate to the parent of the target key
        for key in keys[:-1]:
            if key not in config_ref:
                config_ref[key] = {}
            config_ref = config_ref[key]
        
        # Set the final value
        config_ref[keys[-1]] = value
    
    def save_config(self):
        """Save current configuration to file"""
        try:
            with open(self._config_path, 'w', encoding='utf-8') as f:
                yaml.dump(self._config, f, default_flow_style=False, indent=2)
            print(f"💾 Configuration saved to: {self._config_path}")
        except Exception as e:
            print(f"❌ Error saving configuration: {e}")
    
    # Convenience methods for common configuration access
    
    def get_connection_config(self) -> Dict[str, Any]:
        """Get connection configuration"""
        return self.get('connection', {})
    
    def get_base_url(self) -> str:
        """Get base URL for API connections"""
        conn = self.get_connection_config()
        protocol = conn.get('protocol', 'https')
        hostname = conn.get('hostname', 'localhost')
        port = conn.get('port', 443)
        
        if (protocol == 'https' and port == 443) or (protocol == 'http' and port == 80):
            return f"{protocol}://{hostname}"
        else:
            return f"{protocol}://{hostname}:{port}"
    
    def get_environment_config(self) -> Dict[str, Any]:
        """Get environment configuration"""
        return self.get('environments', {})
    
    def get_environment_count(self) -> int:
        """Get number of environments to manage"""
        return self.get('environments.count', 24)
    
    def get_environment_names(self) -> list[str]:
        """Get list of environment names based on configuration"""
        count = self.get_environment_count()
        prefix = self.get('environments.naming.prefix', 'hour_')
        suffix_format = self.get('environments.naming.suffix_format', '{:02d}')
        
        names = []
        for i in range(count):
            suffix = suffix_format.format(i)
            names.append(f"{prefix}{suffix}")
        
        return names
    
    def get_environment_variables(self, env_index: int) -> Dict[str, str]:
        """Get variables for a specific environment
        
        Args:
            env_index: Index of the environment (0-based)
            
        Returns:
            Dictionary of variable name -> value
        """
        variables_config = self.get('environments.variables', [])
        variables = {}
        
        for var_config in variables_config:
            var_name = var_config.get('name', '')
            value_format = var_config.get('value_format', '{}')
            
            if var_name:
                variables[var_name] = value_format.format(env_index)
        
        return variables
    
    def get_workflow_config(self) -> Dict[str, Any]:
        """Get workflow configuration"""
        return self.get('workflows', {})
    
    def get_rates_config(self) -> Dict[str, Any]:
        """Get rates configuration"""
        return self.get('rates', {})
    
    def get_api_config(self) -> Dict[str, Any]:
        """Get API configuration"""
        return self.get('api', {})
    
    def get_logging_config(self) -> Dict[str, Any]:
        """Get logging configuration"""
        return self.get('logging', {})
    
    def show_config(self):
        """Display current configuration"""
        print("📋 Current Configuration:")
        print("=" * 50)
        self._print_dict(self._config, indent=0)
    
    def _print_dict(self, d: Dict[str, Any], indent: int = 0):
        """Recursively print dictionary with indentation"""
        for key, value in d.items():
            spaces = "  " * indent
            if isinstance(value, dict):
                print(f"{spaces}{key}:")
                self._print_dict(value, indent + 1)
            elif isinstance(value, list):
                print(f"{spaces}{key}:")
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        print(f"{spaces}  [{i}]:")
                        self._print_dict(item, indent + 2)
                    else:
                        print(f"{spaces}  - {item}")
            else:
                print(f"{spaces}{key}: {value}")


# Global configuration instance
_config = None

def get_config() -> Config:
    """Get global configuration instance"""
    global _config
    if _config is None:
        _config = Config()
    return _config

def reload_config():
    """Reload configuration from file"""
    global _config
    if _config:
        _config.load_config()
    else:
        _config = Config()
