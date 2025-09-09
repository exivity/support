#!/usr/bin/env python3
"""
Exivity Management CLI - Main Entry Point
"""

import sys
import requests
from typing import Optional

try:
    import questionary
except ImportError:
    print("questionary library is required. Install via `pip install questionary`.")
    sys.exit(1)

from .api.client import ExivityAPI
from .modules.rate_management import RateManager
from .modules.workflow_management import WorkflowManager
from .modules.environment_management import EnvironmentManager
from .config import get_config


class ExivityCLI:
    """Main CLI application class"""
    
    def __init__(self):
        self.config = get_config()
        self.api: Optional[ExivityAPI] = None
        self.rate_manager: Optional[RateManager] = None
        self.workflow_manager: Optional[WorkflowManager] = None
        self.environment_manager: Optional[EnvironmentManager] = None
    
    def connect_to_api(self):
        """Interactive API connection setup with configuration defaults"""
        print("🔗 Connecting to Exivity API...")
        
        # Get configuration defaults
        conn_config = self.config.get_connection_config()
        default_base_url = self.config.get_base_url()
        
        base_url = questionary.text(
            "Base URL (e.g. https://api.example.com):", 
            default=default_base_url
        ).ask()
        
        verify_ssl = questionary.confirm(
            "Verify SSL certificates? (Choose 'No' for self-signed certificates):", 
            default=conn_config.get('verify_ssl', False)
        ).ask()
        
        # Use configured defaults if available
        default_username = conn_config.get('username', 'admin')
        default_password = conn_config.get('password', 'exivity')
        
        username = questionary.text(
            "Username:", 
            default=default_username if default_username else "admin"
        ).ask()
        
        password = questionary.password(
            "Password:", 
            default=default_password if default_password else "exivity"
        ).ask()
        
        try:
            self.api = ExivityAPI(
                base_url=base_url, 
                username=username, 
                password=password, 
                verify_ssl=verify_ssl,
                config=self.config
            )
            
            # Initialize managers with configuration
            self.rate_manager = RateManager(self.api, self.config)
            self.workflow_manager = WorkflowManager(self.api, self.config)
            self.environment_manager = EnvironmentManager(self.api, self.config)
            
            print("✅ Successfully connected to Exivity API!")
            return True
            
        except requests.exceptions.SSLError as e:
            print(f"❌ SSL Error: {e}")
            print("If you're using self-signed certificates, restart and choose 'No' for SSL verification.")
            return False
        except Exception as e:
            print(f"❌ Authentication failed: {e}")
            return False
    
    def show_main_menu(self):
        """Display the main topic selection menu - streamlined"""
        if not self.api:
            print("❌ Not connected to API. Please connect first.")
            return
        
        print("\n" + "="*60)
        print("🎯 EXIVITY MANAGEMENT CLI")
        print("="*60)
        
        choice = questionary.select(
            "Select a management operation:",
            choices=[
                questionary.Choice("💰 Rate Management", "rates"),
                questionary.Choice("⚙️  Workflow Management", "workflows"), 
                questionary.Choice("🌍 Environment Management", "environments"),
                questionary.Choice("⚙️  Configuration", "config"),
                questionary.Choice("🔄 Reconnect to API", "reconnect"),
                questionary.Choice("❌ Exit", "exit")
            ]
        ).ask()
        
        if choice == "rates":
            self.show_rate_management_menu()
        elif choice == "workflows":
            self.workflow_management_menu()
        elif choice == "environments":
            self.environment_management_menu()
        elif choice == "config":
            self.configuration_menu()
        elif choice == "reconnect":
            self.connect_to_api()
        elif choice == "exit":
            print("👋 Goodbye!")
            return False
        
        return True
    
    def show_rate_management_menu(self):
        """Rate management menu - use enhanced version from rate manager"""
        self.rate_manager.show_rate_management_menu()
    
    def workflow_management_menu(self):
        """Workflow management operations - streamlined"""
        self.workflow_manager.workflow_management_menu()
    
    def environment_management_menu(self):
        """Environment management operations"""
        if not self.environment_manager:
            self.environment_manager = EnvironmentManager(self.api, self.config)
        self.environment_manager.environment_management_menu()
    
    def configuration_menu(self):
        """Configuration management menu"""
        choice = questionary.select(
            "Configuration Options:",
            choices=[
                questionary.Choice("📋 Show Current Configuration", "show"),
                questionary.Choice("🔧 Edit Configuration", "edit"),
                questionary.Choice("🔄 Reload Configuration", "reload"),
                questionary.Choice("💾 Save Configuration", "save"),
                questionary.Choice("↩️  Back to Main Menu", "back")
            ]
        ).ask()
        
        if choice == "show":
            self.config.show_config()
        elif choice == "edit":
            self.edit_configuration_interactive()
        elif choice == "reload":
            self.config.load_config()
            print("✅ Configuration reloaded from file")
        elif choice == "save":
            self.config.save_config()
        elif choice == "back":
            return
        
        if choice != "back":
            self._pause_for_review()
    
    def edit_configuration_interactive(self):
        """Interactive configuration editing"""
        section = questionary.select(
            "Which section would you like to edit?",
            choices=[
                questionary.Choice("🔗 Connection Settings", "connection"),
                questionary.Choice("🌍 Environment Settings", "environments"),
                questionary.Choice("⚙️  Workflow Settings", "workflows"),
                questionary.Choice("💰 Rate Settings", "rates"),
                questionary.Choice("🔧 API Settings", "api"),
                questionary.Choice("↩️  Back", "back")
            ]
        ).ask()
        
        if section == "connection":
            self.edit_connection_config()
        elif section == "environments":
            self.edit_environment_config()
        elif section == "workflows":
            self.edit_workflow_config()
        elif section == "rates":
            self.edit_rates_config()
        elif section == "api":
            self.edit_api_config()
    
    def edit_connection_config(self):
        """Edit connection configuration"""
        print("🔗 Connection Configuration:")
        
        hostname = questionary.text(
            "Hostname:", 
            default=self.config.get('connection.hostname', 'localhost')
        ).ask()
        
        port = questionary.text(
            "Port:", 
            default=str(self.config.get('connection.port', 443))
        ).ask()
        
        protocol = questionary.select(
            "Protocol:",
            choices=["https", "http"],
            default=self.config.get('connection.protocol', 'https')
        ).ask()
        
        verify_ssl = questionary.confirm(
            "Verify SSL certificates:",
            default=self.config.get('connection.verify_ssl', False)
        ).ask()
        
        self.config.set('connection.hostname', hostname)
        self.config.set('connection.port', int(port))
        self.config.set('connection.protocol', protocol)
        self.config.set('connection.verify_ssl', verify_ssl)
        
        print("✅ Connection configuration updated")
    
    def edit_environment_config(self):
        """Edit environment configuration"""
        print("🌍 Environment Configuration:")
        
        count = questionary.text(
            "Number of environments:",
            default=str(self.config.get('environments.count', 24))
        ).ask()
        
        prefix = questionary.text(
            "Environment name prefix:",
            default=self.config.get('environments.naming.prefix', 'hour_')
        ).ask()
        
        suffix_format = questionary.text(
            "Suffix format (Python format string):",
            default=self.config.get('environments.naming.suffix_format', '{:02d}')
        ).ask()
        
        self.config.set('environments.count', int(count))
        self.config.set('environments.naming.prefix', prefix)
        self.config.set('environments.naming.suffix_format', suffix_format)
        
        print("✅ Environment configuration updated")
    
    def edit_workflow_config(self):
        """Edit workflow configuration"""
        print("⚙️  Workflow Configuration:")
        
        default_timeout = questionary.text(
            "Default timeout (seconds):",
            default=str(self.config.get('workflows.default_timeout', 3600))
        ).ask()
        
        default_wait = questionary.confirm(
            "Default wait setting:",
            default=self.config.get('workflows.default_wait', True)
        ).ask()
        
        self.config.set('workflows.default_timeout', int(default_timeout))
        self.config.set('workflows.default_wait', default_wait)
        
        print("✅ Workflow configuration updated")
    
    def edit_rates_config(self):
        """Edit rates configuration"""
        print("💰 Rates Configuration:")
        
        default_rate = questionary.text(
            "Default rate value:",
            default=str(self.config.get('rates.default_rate', 0.0))
        ).ask()
        
        default_cogs = questionary.text(
            "Default COGS value:",
            default=str(self.config.get('rates.default_cogs', 0.0))
        ).ask()
        
        date_format = questionary.select(
            "CSV date format:",
            choices=["YYYYMMDD", "YYYY-MM-DD"],
            default=self.config.get('rates.csv_export.date_format', 'YYYYMMDD')
        ).ask()
        
        self.config.set('rates.default_rate', float(default_rate))
        self.config.set('rates.default_cogs', float(default_cogs))
        self.config.set('rates.csv_export.date_format', date_format)
        
        print("✅ Rates configuration updated")
    
    def edit_api_config(self):
        """Edit API configuration"""
        print("🔧 API Configuration:")
        
        timeout = questionary.text(
            "Request timeout (seconds):",
            default=str(self.config.get('api.timeout', 30))
        ).ask()
        
        page_size = questionary.text(
            "Default page size:",
            default=str(self.config.get('api.default_page_size', 100))
        ).ask()
        
        self.config.set('api.timeout', int(timeout))
        self.config.set('api.default_page_size', int(page_size))
        
        print("✅ API configuration updated")
    
    def _pause_for_review(self):
        """Pause to let user review output before returning to menu"""
        print("\n" + "-"*40)
        questionary.press_any_key_to_continue("Press any key to continue...").ask()
    
    def run(self):
        """Main application loop"""
        print("🚀 Welcome to Exivity Management CLI!")
        print("📦 Topic-Based Navigation System")
        print("=" * 50)
        
        # Connect to API first
        if not self.connect_to_api():
            print("❌ Failed to connect to API. Exiting.")
            return
        
        # Main menu loop
        while True:
            try:
                if not self.show_main_menu():
                    break
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"❌ Unexpected error: {e}")
                continue


def main():
    """Entry point for the CLI application"""
    cli = ExivityCLI()
    cli.run()


if __name__ == "__main__":
    main()
