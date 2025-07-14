"""
Environment Management Module

Handles environment-related operations and configurations.
"""

from typing import Dict, List, Optional
import questionary


class EnvironmentManager:
    """Handles environment management operations"""
    
    def __init__(self, api):
        self.api = api
    
    def list_environments(self):
        """List all environments"""
        try:
            environments = self.api.list_environments()
            
            if not environments:
                print("❌ No environments found")
                return
            
            print(f"📋 Available environments ({len(environments)}):")
            for env in environments:
                env_id = env.get('id', 'N/A')
                env_name = env.get('attributes', {}).get('name', 'Unknown')
                env_desc = env.get('attributes', {}).get('description', '')
                print(f"   • {env_name} (ID: {env_id})")
                if env_desc:
                    print(f"     Description: {env_desc}")
                    
        except Exception as e:
            print(f"❌ Error listing environments: {e}")
    
    def create_environment_interactive(self):
        """Interactive environment creation"""
        print("🆕 Creating new environment...")
        
        name = questionary.text("Environment name:").ask()
        if not name:
            print("❌ Environment name is required")
            return
        
        # Note: Description is NOT supported for environments in the API
        # Using the same validated method as the main system
        
        try:
            env_id = self.api.create_environment(name)  # No description parameter
            print(f"✅ Environment '{name}' created successfully (ID: {env_id})")
        except Exception as e:
            print(f"❌ Error creating environment: {e}")
    
    def delete_environment_interactive(self):
        """Interactive environment deletion"""
        print("🗑️  Deleting environment...")
        
        env_name = questionary.text("Environment name to delete:").ask()
        if not env_name:
            print("❌ Environment name is required")
            return
        
        # Find environment
        env_id = self.api.find_environment_by_name(env_name)
        if not env_id:
            print(f"❌ Environment '{env_name}' not found")
            return
        
        # Confirm deletion
        confirm = questionary.confirm(f"Delete environment '{env_name}' (ID: {env_id})?").ask()
        if not confirm:
            print("Operation cancelled.")
            return
        
        try:
            self.api.delete_environment(env_id)
            print(f"✅ Environment '{env_name}' deleted successfully")
        except Exception as e:
            print(f"❌ Error deleting environment: {e}")
