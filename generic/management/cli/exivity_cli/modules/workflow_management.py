"""
Workflow Management Module

Handles workflow creation, editing, and execution with support for 24-step workflows
and environment-specific configurations.
"""

import json
import os
import uuid
from typing import Dict, List, Optional
from pathlib import Path

import questionary


class WorkflowManager:
    """Handles workflow management operations"""
    
    def __init__(self, api):
        self.api = api
        self.workflows_folder = Path(__file__).parent.parent.parent / "workflows"
        self.environments_folder = Path(__file__).parent.parent.parent / "environments"
        
        # Ensure folders exist
        self.workflows_folder.mkdir(parents=True, exist_ok=True)
        self.environments_folder.mkdir(parents=True, exist_ok=True)

    def create_hourly_workflow_interactive(self):
        """Create workflow with 24-hour environment duplication - original logic"""
        name = questionary.text("Workflow name:").ask()
        if not name:
            print("❌ Workflow name is required")
            return
            
        description = questionary.text("Description (optional):").ask() or ""

        # Check for existing workflows
        existing = self.api.find_workflows_by_name(name)
        if existing:
            confirm = questionary.confirm(
                f"Workflow '{name}' exists (ID(s): {', '.join(existing)}). Delete and recreate?",
                default=False
            ).ask()
            if not confirm:
                print("Aborting – keeping existing workflow.")
                return
            for wid in existing:
                self.api.delete_workflow(wid)
                print(f"Deleted existing workflow ID {wid}")

        # Build steps interactively
        steps, from_offset, to_offset = self._interactive_step_builder()
        if not steps:
            print("No steps defined, aborting")
            return
        
        # Ensure hourly environments exist
        env_map = self.api.ensure_hourly_environments()
        
        # Duplicate steps for all 24 hours
        all_steps = self._duplicate_steps_hourly(steps, env_map)
        
        # Create workflow with all steps using atomic operationstal steps ({len(steps)} steps × 24 environments)")
        try:
            workflow_id = self.api.create_workflow_with_steps(name, description, all_steps)
            print(f"✅ Workflow '{name}' ({workflow_id}) created with {len(all_steps)} steps across 24 hourly environments.")
            print(f"Using offsets: from={from_offset}, to={to_offset}")
        except Exception as e:
            print(f"❌ Error creating workflow: {e}")
            # Fallback to legacy method if atomic operations fail
            print("🔄 Trying fallback method (individual step creation)...")
            try:
                workflow_id = self.api.create_workflow(name, description)
                print(f"✅ Created workflow '{name}' ({workflow_id}), but could not add steps.")
                print("💡 You may need to add steps manually through the GUI.")
            except Exception as e2:
                print(f"❌ Error creating workflow: {e2}")

    def _interactive_step_builder(self) -> tuple[List[Dict], str, str]:
        """Build workflow steps interactively - original logic"""
        steps = []
        
        # Ask for common offset values once
        from_offset = questionary.text("From date offset (e.g. -1) for all steps:", default="-1").ask()
        to_offset = questionary.text("To date offset (e.g. -1) for all steps:", default="-1").ask()
                    
        while True:
            step_type = questionary.select(
                "Choose step type (or select Done to finish)",
                choices=["extract", "transform", "prepare_report", "Done"]
            ).ask()
            
            if step_type == "Done":
                break
                
            attrs = {}
            if step_type in ("extract", "transform"):
                attrs["script"] = questionary.text(f"{step_type.capitalize()} script name:").ask()
                attrs["from_date_offset"] = int(from_offset)
                attrs["to_date_offset"] = int(to_offset)
                if step_type == "extract":
                    args = questionary.text("Arguments (optional):").ask()
                    attrs["arguments"] = args if args else None
            elif step_type == "prepare_report":
                attrs["report_id"] = int(questionary.text("Report ID:").ask())
                attrs["from_date_offset"] = int(from_offset)
                attrs["to_date_offset"] = int(to_offset)
                
            steps.append({
                "type": step_type,
                "attributes": attrs
            })
            
        return steps, from_offset, to_offset

    def _duplicate_steps_hourly(self, steps: List[Dict], env_map: Dict[str, str]) -> List[Dict]:
        """Duplicate steps for each hourly environment - original logic with validation"""
        duplicated = []
        
        print(f"🔄 Duplicating {len(steps)} step(s) across 24 environments...")
        
        for hour in range(24):
            env_name = f"H{hour:02d}"
            
            # Check if environment exists
            if env_name not in env_map:
                print(f"Warning: Environment {env_name} not found, skipping...")
                continue
                
            env_id = env_map[env_name]
            
            for step_index, s in enumerate(steps):
                clone = json.loads(json.dumps(s))  # deep copy
                
                # Add environment_id for extract/transform steps
                if clone["type"] in ("extract", "transform"):
                    clone["attributes"]["environment_id"] = int(env_id)
                
                # Validate step attributes
                if not self._validate_step_attributes(clone, hour, step_index):
                    print(f"⚠️  Warning: Step validation failed for {env_name}, step {step_index + 1}")
                
                duplicated.append(clone)
                
        print(f"✅ Created {len(duplicated)} total steps")
        return duplicated

    def _validate_step_attributes(self, step: Dict, hour: int, step_index: int) -> bool:
        """Validate step attributes before creation"""
        step_type = step.get("type")
        attributes = step.get("attributes", {})
        
        # Check required attributes based on step type
        if step_type == "extract":
            required = ["script", "from_date_offset", "to_date_offset", "environment_id"]
            missing = [attr for attr in required if attr not in attributes]
            if missing:
                print(f"   ❌ Extract step missing: {missing}")
                return False
                
        elif step_type == "transform":
            required = ["script", "from_date_offset", "to_date_offset", "environment_id"]
            missing = [attr for attr in required if attr not in attributes]
            if missing:
                print(f"   ❌ Transform step missing: {missing}")
                return False
                
        elif step_type == "prepare_report":
            required = ["report_id", "from_date_offset", "to_date_offset"]
            missing = [attr for attr in required if attr not in attributes]
            if missing:
                print(f"   ❌ Prepare_report step missing: {missing}")
                return False
        
        # Validate data types
        try:
            if "from_date_offset" in attributes:
                int(attributes["from_date_offset"])
            if "to_date_offset" in attributes:
                int(attributes["to_date_offset"])
            if "environment_id" in attributes:
                int(attributes["environment_id"])
            if "report_id" in attributes:
                int(attributes["report_id"])
        except (ValueError, TypeError) as e:
            print(f"   ❌ Invalid data type in step attributes: {e}")
            return False
        
        return True

    def list_hourly_environments_status(self):
        """Show status of all hourly environments"""
        self.api.list_hourly_environments()

    def recreate_missing_environments(self):
        """Recreate any missing H00-H23 environments"""
        confirm = questionary.confirm(
            "This will create any missing H00-H23 environments. Continue?",
            default=True
        ).ask()
        
        if not confirm:
            print("Operation cancelled.")
            return
        
        try:
            env_map = self.api.ensure_hourly_environments()
            print(f"✅ Successfully ensured all 24 hourly environments exist.")
        except Exception as e:
            print(f"❌ Error ensuring environments: {e}")

    def delete_hourly_environments_interactive(self):
        """Interactive deletion of hourly environments with confirmation"""
        # Show current default environment info
        default_env = self.api.get_default_environment()
        if default_env:
            default_name = default_env.get('attributes', {}).get('name', 'Unknown')
            print(f"🏠 Current default environment: {default_name} (ID: {default_env.get('id')})")
            print("💡 Note: The default environment will be protected from deletion")
        
        confirm = questionary.confirm(
            "⚠️  WARNING: This will delete ALL non-default environments named H00 through H23. Are you sure?",
            default=False
        ).ask()
        
        if not confirm:
            print("Operation cancelled.")
            return
        
        # Double confirmation for safety
        final_confirm = questionary.confirm(
            "This action cannot be undone. Are you absolutely sure?",
            default=False
        ).ask()
        
        if not final_confirm:
            print("Operation cancelled.")
            return
        
        try:
            self.api.delete_hourly_environments()
            
            # Check if any environments still exist and provide guidance
            remaining_envs = []
            for hour in range(24):
                env_name = f"H{hour:02d}"
                if self.api.find_environment_by_name(env_name):
                    remaining_envs.append(env_name)
            
            if remaining_envs:
                default_env = self.api.get_default_environment()
                default_name = default_env.get('attributes', {}).get('name') if default_env else None
                
                print(f"\n📊 {len(remaining_envs)} environment(s) remain: {', '.join(remaining_envs)}")
                
                if default_name in remaining_envs:
                    print(f"✅ {default_name} was protected as the default environment")
                    print("💡 This is expected behavior - the system requires a default environment")
                else:
                    print("⚠️  Some environments could not be deleted due to dependencies")
                    print("💡 These may have active workflows, reports, or other dependencies")
            else:
                print("✅ All hourly environments successfully processed!")
                
        except Exception as e:
            print(f"❌ Error during environment deletion: {e}")

    def debug_environment_creation(self):
        """Debug environment creation issues"""
        from ..api.debug import debug_session
        
        print("🐛 Starting environment creation debug session...")
        debug_session(self.api)

    def workflow_management_menu(self):
        """Main workflow management menu - streamlined"""
        while True:
            action = questionary.select(
                "Choose a workflow management operation:",
                choices=[
                    "🆕 Create hourly workflow (24 environments)",
                    "📋 List hourly environments status",
                    "🔧 Recreate missing hourly environments",
                    "🗑️  Delete hourly environments (H00-H23)",
                    "🐛 Debug environment creation",
                    "🔍 Debug dump endpoint",
                    "🔙 Back to main menu"
                ]
            ).ask()
            
            if action == "🆕 Create hourly workflow (24 environments)":
                self.create_hourly_workflow_interactive()
            elif action == "📋 List hourly environments status":
                self.list_hourly_environments_status()
            elif action == "🔧 Recreate missing hourly environments":
                self.recreate_missing_environments()
            elif action == "🗑️  Delete hourly environments (H00-H23)":
                self.delete_hourly_environments_interactive()
            elif action == "🐛 Debug environment creation":
                self.debug_environment_creation()
            elif action == "🔍 Debug dump endpoint":
                from ..api.debug import test_dump_endpoint
                test_dump_endpoint(self.api)
            elif action == "🔙 Back to main menu":
                break
            
            input("\nPress any key to continue...")
