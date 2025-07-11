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

    def duplicate_workflow_interactive(self):
        """Interactive workflow duplication - clone an existing workflow"""
        print("📋 Workflow Duplication Tool")
        print("Clone an existing workflow with optional modifications")
        print("-" * 50)
        
        # First, get a list of existing workflows
        try:
            existing_workflows = self._get_existing_workflows()
            if not existing_workflows:
                print("❌ No existing workflows found")
                return
            
            print(f"📋 Found {len(existing_workflows)} existing workflow(s):")
            for i, wf in enumerate(existing_workflows[:10], 1):
                print(f"   {i}. {wf['name']} (ID: {wf['id']}) - {wf.get('description', 'No description')}")
            
            if len(existing_workflows) > 10:
                print(f"   ... and {len(existing_workflows) - 10} more")
            
            # Let user select workflow to duplicate
            source_workflow = self._select_workflow_interactive(existing_workflows)
            if not source_workflow:
                print("❌ No workflow selected")
                return
            
            # Get workflow details including steps
            workflow_details = self._get_workflow_details(source_workflow['id'])
            if not workflow_details:
                print(f"❌ Could not retrieve details for workflow '{source_workflow['name']}'")
                return
            
            # Get new name and description
            new_name = questionary.text(
                "New workflow name:",
                default=f"{source_workflow['name']}_copy"
            ).ask()
            
            if not new_name:
                print("❌ New workflow name is required")
                return
            
            new_description = questionary.text(
                "New workflow description (optional):",
                default=workflow_details.get('description', '')
            ).ask() or ""
            
            # Check if new name already exists
            existing = self.api.find_workflows_by_name(new_name)
            if existing:
                overwrite = questionary.confirm(
                    f"Workflow '{new_name}' already exists. Delete and recreate?",
                    default=False
                ).ask()
                if not overwrite:
                    print("Operation cancelled.")
                    return
                
                # Delete existing workflows with the same name
                for wid in existing:
                    self.api.delete_workflow(wid)
                    print(f"Deleted existing workflow ID {wid}")
            
            # Show duplication summary
            print(f"\n📋 Duplication Summary:")
            print(f"   • Source: {source_workflow['name']} (ID: {source_workflow['id']})")
            print(f"   • Target: {new_name}")
            print(f"   • Steps: {len(workflow_details.get('steps', []))} step(s)")
            
            confirm = questionary.confirm(
                f"Proceed with duplicating workflow?",
                default=True
            ).ask()
            
            if not confirm:
                print("Operation cancelled.")
                return
            
            # Perform the duplication
            self._duplicate_workflow(source_workflow, new_name, new_description, workflow_details)
            
        except Exception as e:
            print(f"❌ Error during workflow duplication: {e}")

    def _get_existing_workflows(self) -> List[Dict]:
        """Get list of all existing workflows"""
        try:
            # Set page[limit] to -1 to fetch all workflows instead of default 10
            params = {"page[limit]": -1}
            resp = self.api._request("GET", "/v2/workflows", params=params)
            workflows = resp.json().get("data", [])
            
            # Extract relevant information
            workflow_list = []
            for wf in workflows:
                workflow_info = {
                    'id': wf.get('id'),
                    'name': wf.get('attributes', {}).get('name', 'Unknown'),
                    'description': wf.get('attributes', {}).get('description', ''),
                    'created_at': wf.get('attributes', {}).get('created_at', ''),
                    'updated_at': wf.get('attributes', {}).get('updated_at', '')
                }
                workflow_list.append(workflow_info)
            
            # Sort by name
            workflow_list.sort(key=lambda x: x['name'])
            return workflow_list
            
        except Exception as e:
            print(f"❌ Error fetching workflows: {e}")
            return []

    def _select_workflow_interactive(self, workflows: List[Dict]) -> Optional[Dict]:
        """Interactive workflow selection"""
        if not workflows:
            return None
        
        # Create choices for selection
        choices = []
        for wf in workflows:
            title = f"{wf['name']} (ID: {wf['id']})"
            if wf.get('description'):
                title += f" - {wf['description'][:50]}{'...' if len(wf['description']) > 50 else ''}"
            choices.append(questionary.Choice(title=title, value=wf))
        
        choices.append(questionary.Choice("❌ Cancel", value=None))
        
        selected = questionary.select(
            "Select workflow to duplicate:",
            choices=choices
        ).ask()
        
        return selected

    def _get_workflow_details(self, workflow_id: str) -> Optional[Dict]:
        """Get detailed workflow information including steps"""
        try:
            # Get workflow basic info
            resp = self.api._request("GET", f"/v2/workflows/{workflow_id}")
            workflow_data = resp.json().get("data", {})
            
            # Get workflow steps
            steps_resp = self.api._request("GET", f"/v2/workflows/{workflow_id}/steps")
            steps_data = steps_resp.json().get("data", [])
            
            workflow_details = {
                'id': workflow_data.get('id'),
                'name': workflow_data.get('attributes', {}).get('name', ''),
                'description': workflow_data.get('attributes', {}).get('description', ''),
                'steps': self._parse_workflow_steps(steps_data)
            }
            
            return workflow_details
            
        except Exception as e:
            print(f"❌ Error getting workflow details: {e}")
            return None

    def _parse_workflow_steps(self, steps_data: List[Dict]) -> List[Dict]:
        """Parse workflow steps from API response"""
        parsed_steps = []
        
        # Sort steps by their order/sequence
        sorted_steps = sorted(steps_data, key=lambda x: x.get('attributes', {}).get('id', 0))
        
        for step in sorted_steps:
            attributes = step.get('attributes', {})
            step_type = attributes.get('step_type', '')
            options = attributes.get('options', {})
            
            # Build step structure for duplication
            parsed_step = {
                'type': step_type,
                'attributes': {}
            }
            
            # Extract step-specific attributes
            if step_type in ('extract', 'transform'):
                if 'script' in options:
                    parsed_step['attributes']['script'] = options['script']
                if 'from_date_offset' in options:
                    parsed_step['attributes']['from_date_offset'] = options['from_date_offset']
                if 'to_date_offset' in options:
                    parsed_step['attributes']['to_date_offset'] = options['to_date_offset']
                if 'arguments' in options:
                    parsed_step['attributes']['arguments'] = options['arguments']
                # Note: environment_id will be reassigned during duplication
                
            elif step_type == 'prepare_report':
                if 'report_id' in options:
                    parsed_step['attributes']['report_id'] = options['report_id']
                if 'from_date_offset' in options:
                    parsed_step['attributes']['from_date_offset'] = options['from_date_offset']
                if 'to_date_offset' in options:
                    parsed_step['attributes']['to_date_offset'] = options['to_date_offset']
            
            parsed_steps.append(parsed_step)
        
        return parsed_steps

    def _interactive_step_builder(self) -> tuple[List[Dict], str, str]:
        """Build workflow steps interactively with selection lists"""
        steps = []
        
        # Ask for common offset values once
        from_offset = questionary.text("From date offset (e.g. -1) for all steps:", default="-1").ask()
        to_offset = questionary.text("To date offset (e.g. -1) for all steps:", default="-1").ask()
        
        # Pre-fetch available scripts and reports
        print("📋 Loading available scripts and reports...")
        try:
            scripts = self.api.get_available_scripts()
            reports = self.api.get_available_reports()
            
            extract_scripts = scripts.get("extract", [])
            transform_scripts = scripts.get("transform", [])
            
            print(f"   ✅ Found {len(extract_scripts)} extract scripts")
            print(f"   ✅ Found {len(transform_scripts)} transform scripts")
            print(f"   ✅ Found {len(reports)} reports")
            
        except Exception as e:
            print(f"   ⚠️  Error loading scripts/reports: {e}")
            extract_scripts = []
            transform_scripts = []
            reports = []
                    
        while True:
            step_type = questionary.select(
                "Choose step type (or select Done to finish)",
                choices=["extract", "transform", "prepare_report", "Done"]
            ).ask()
            
            if step_type == "Done":
                break
                
            attrs = {}
            if step_type == "extract":
                # Select extract script
                script_name = self._select_script_interactive(extract_scripts, "extract")
                if not script_name:
                    continue
                    
                attrs["script"] = script_name
                attrs["from_date_offset"] = int(from_offset)
                attrs["to_date_offset"] = int(to_offset)
                
                # Optional arguments
                args = questionary.text("Arguments (optional):").ask()
                attrs["arguments"] = args if args else None
                
            elif step_type == "transform":
                # Select transform script
                script_name = self._select_script_interactive(transform_scripts, "transform")
                if not script_name:
                    continue
                    
                attrs["script"] = script_name
                attrs["from_date_offset"] = int(from_offset)
                attrs["to_date_offset"] = int(to_offset)
                
            elif step_type == "prepare_report":
                # Select report
                report_info = self._select_report_interactive(reports)
                if not report_info:
                    continue
                    
                attrs["report_id"] = int(report_info["id"])
                attrs["from_date_offset"] = int(from_offset)
                attrs["to_date_offset"] = int(to_offset)
                
            steps.append({
                "type": step_type,
                "attributes": attrs
            })
            
        return steps, from_offset, to_offset

    def _select_script_interactive(self, scripts: List[str], script_type: str) -> Optional[str]:
        """Interactive script selection with fallback to manual entry"""
        if not scripts:
            print(f"⚠️  No {script_type} scripts available from API")
            return questionary.text(f"{script_type.capitalize()} script name:").ask()
        
        # Create choices for selection
        choices = []
        for script in scripts:
            choices.append(questionary.Choice(title=script, value=script))
        
        # Add option for manual entry
        choices.append(questionary.Choice(title="✏️  Enter script name manually", value="__manual__"))
        choices.append(questionary.Choice(title="❌ Cancel this step", value=None))
        
        selected = questionary.select(
            f"Select {script_type} script:",
            choices=choices
        ).ask()
        
        if selected == "__manual__":
            return questionary.text(f"{script_type.capitalize()} script name:").ask()
        
        return selected

    def _select_report_interactive(self, reports: List[Dict[str, str]]) -> Optional[Dict[str, str]]:
        """Interactive report selection with fallback to manual entry"""
        if not reports:
            print("⚠️  No reports available from API")
            report_id = questionary.text("Report ID:").ask()
            if report_id:
                return {"id": report_id, "name": f"Manual ID: {report_id}"}
            return None
        
        # Create choices for selection
        choices = []
        for report in reports:
            title = f"{report['name']} (ID: {report['id']})"
            if report.get('description'):
                title += f" - {report['description'][:50]}{'...' if len(report['description']) > 50 else ''}"
            choices.append(questionary.Choice(title=title, value=report))
        
        # Add option for manual entry
        choices.append(questionary.Choice(title="✏️  Enter report ID manually", value="__manual__"))
        choices.append(questionary.Choice(title="❌ Cancel this step", value=None))
        
        selected = questionary.select(
            "Select report:",
            choices=choices
        ).ask()
        
        if selected == "__manual__":
            report_id = questionary.text("Report ID:").ask()
            if report_id:
                return {"id": report_id, "name": f"Manual ID: {report_id}"}
            return None
        
        return selected

    def _duplicate_workflow(self, source_workflow: Dict, new_name: str, new_description: str, workflow_details: Dict):
        """Perform the actual workflow duplication"""
        print(f"🔄 Duplicating workflow '{source_workflow['name']}' as '{new_name}'...")
        
        try:
            steps = workflow_details.get('steps', [])
            
            if not steps:
                # Create simple workflow without steps
                workflow_id = self.api.create_workflow(new_name, new_description)
                print(f"✅ Created workflow '{new_name}' (ID: {workflow_id}) - no steps to duplicate")
                return
            
            # Analyze steps to determine if this is an hourly workflow
            hourly_steps = self._analyze_hourly_pattern(steps)
            
            if hourly_steps:
                print(f"📊 Detected hourly workflow pattern: {len(hourly_steps)} unique step(s) × 24 environments")
                self._duplicate_hourly_workflow(new_name, new_description, hourly_steps)
            else:
                print(f"📊 Detected standard workflow: {len(steps)} step(s)")
                self._duplicate_standard_workflow(new_name, new_description, steps)
                
        except Exception as e:
            print(f"❌ Error during workflow duplication: {e}")
            raise

    def _analyze_hourly_pattern(self, steps: List[Dict]) -> Optional[List[Dict]]:
        """Analyze if workflow follows hourly pattern and extract unique steps"""
        # Group steps by their core attributes (excluding environment-specific data)
        step_groups = {}
        
        for step in steps:
            # Create a signature for the step type and core attributes
            step_type = step.get('type', '')
            attrs = step.get('attributes', {})
            
            # Build signature based on step type
            if step_type in ('extract', 'transform'):
                signature = (
                    step_type,
                    attrs.get('script', ''),
                    attrs.get('from_date_offset', 0),
                    attrs.get('to_date_offset', 0),
                    attrs.get('arguments', '')
                )
            elif step_type == 'prepare_report':
                signature = (
                    step_type,
                    attrs.get('report_id', ''),
                    attrs.get('from_date_offset', 0),
                    attrs.get('to_date_offset', 0)
                )
            else:
                signature = (step_type, str(attrs))
            
            if signature not in step_groups:
                step_groups[signature] = []
            step_groups[signature].append(step)
        
        # Check if we have exactly 24 instances of each unique step (hourly pattern)
        unique_steps = []
        is_hourly = True
        
        for signature, group in step_groups.items():
            if len(group) == 24:
                # Take the first instance as the template
                unique_steps.append(group[0])
            elif len(group) == 1:
                # Single step - could be prepare_report or non-environment step
                unique_steps.append(group[0])
            else:
                # Not a clean 24-hour pattern
                is_hourly = False
                break
        
        if is_hourly and len(step_groups) > 0:
            print(f"📋 Identified {len(unique_steps)} unique step pattern(s)")
            return unique_steps
        else:
            return None

    def _duplicate_hourly_workflow(self, new_name: str, new_description: str, unique_steps: List[Dict]):
        """Duplicate an hourly workflow (24 environments)"""
        print("🕐 Duplicating as hourly workflow...")
        
        # Ensure hourly environments exist
        env_map = self.api.ensure_hourly_environments()
        
        # Duplicate steps for all 24 hours
        all_steps = self._duplicate_steps_hourly(unique_steps, env_map)
        
        # Create workflow with all steps
        try:
            workflow_id = self.api.create_workflow_with_steps(new_name, new_description, all_steps)
            print(f"✅ Workflow '{new_name}' (ID: {workflow_id}) duplicated with {len(all_steps)} steps across 24 hourly environments")
        except Exception as e:
            print(f"❌ Error creating hourly workflow: {e}")
            # Fallback to basic workflow
            print("🔄 Falling back to basic workflow creation...")
            workflow_id = self.api.create_workflow(new_name, new_description)
            print(f"✅ Created basic workflow '{new_name}' (ID: {workflow_id}) - steps may need to be added manually")

    def _duplicate_standard_workflow(self, new_name: str, new_description: str, steps: List[Dict]):
        """Duplicate a standard workflow (as-is)"""
        print("📝 Duplicating as standard workflow...")
        
        try:
            workflow_id = self.api.create_workflow_with_steps(new_name, new_description, steps)
            print(f"✅ Workflow '{new_name}' (ID: {workflow_id}) duplicated with {len(steps)} steps")
        except Exception as e:
            print(f"❌ Error creating standard workflow: {e}")
            # Fallback to basic workflow
            print("🔄 Falling back to basic workflow creation...")
            workflow_id = self.api.create_workflow(new_name, new_description)
            print(f"✅ Created basic workflow '{new_name}' (ID: {workflow_id}) - steps may need to be added manually")

    def list_workflows_interactive(self):
        """Interactive workflow listing with details"""
        print("📋 Listing all workflows...")
        
        try:
            workflows = self._get_existing_workflows()
            
            if not workflows:
                print("❌ No workflows found")
                return
            
            print(f"\n📊 Found {len(workflows)} workflow(s):")
            print("-" * 80)
            
            for i, wf in enumerate(workflows, 1):
                print(f"{i:3}. {wf['name']} (ID: {wf['id']})")
                if wf.get('description'):
                    print(f"     Description: {wf['description']}")
                if wf.get('created_at'):
                    print(f"     Created: {wf['created_at']}")
                
                # Get step count
                try:
                    details = self._get_workflow_details(wf['id'])
                    if details:
                        step_count = len(details.get('steps', []))
                        print(f"     Steps: {step_count}")
                        
                        # Try to identify if it's hourly
                        steps = details.get('steps', [])
                        if steps:
                            hourly_steps = self._analyze_hourly_pattern(steps)
                            if hourly_steps:
                                print(f"     Type: Hourly workflow ({len(hourly_steps)} unique × 24 environments)")
                            else:
                                print(f"     Type: Standard workflow")
                except:
                    print(f"     Steps: Unable to retrieve")
                
                print("-" * 80)
                
        except Exception as e:
            print(f"❌ Error listing workflows: {e}")

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
        """Enhanced workflow management menu with duplication"""
        while True:
            action = questionary.select(
                "Choose a workflow management operation:",
                choices=[
                    "🆕 Create hourly workflow (24 environments)",
                    "📋 Duplicate existing workflow",
                    "📄 List all workflows",
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
            elif action == "📋 Duplicate existing workflow":
                self.duplicate_workflow_interactive()
            elif action == "📄 List all workflows":
                self.list_workflows_interactive()
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
