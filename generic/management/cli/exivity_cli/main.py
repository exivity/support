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


class ExivityCLI:
    """Main CLI application class"""
    
    def __init__(self):
        self.api: Optional[ExivityAPI] = None
        self.rate_manager: Optional[RateManager] = None
        self.workflow_manager: Optional[WorkflowManager] = None
        self.environment_manager: Optional[EnvironmentManager] = None
    
    def connect_to_api(self):
        """Interactive API connection setup"""
        print("🔗 Connecting to Exivity API...")
        
        base_url = questionary.text(
            "Base URL (e.g. https://api.example.com):", 
            default="https://localhost"
        ).ask()
        
        verify_ssl = questionary.confirm(
            "Verify SSL certificates? (Choose 'No' for self-signed certificates):", 
            default=True
        ).ask()
        
        username = questionary.text("Username:", default="admin").ask()
        password = questionary.password("Password:", default="exivity").ask()
        
        try:
            self.api = ExivityAPI(
                base_url=base_url, 
                username=username, 
                password=password, 
                verify_ssl=verify_ssl
            )
            
            # Initialize managers
            self.rate_manager = RateManager(self.api)
            self.workflow_manager = WorkflowManager(self.api)
            self.environment_manager = EnvironmentManager(self.api)
            
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
                questionary.Choice("🔄 Reconnect to API", "reconnect"),
                questionary.Choice("❌ Exit", "exit")
            ]
        ).ask()
        
        if choice == "rates":
            self.show_rate_management_menu()
        elif choice == "workflows":
            self.workflow_management_menu()
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
