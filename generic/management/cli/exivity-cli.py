#!/usr/bin/env python3
"""
Exivity CLI tool

Features:
1. Authenticate with Exivity API via username/password -> Obtain JWT token
2. Update account/service rates from a CSV file
3. Create workflows with interactive steps and duplicate across 24 hourly environments

Dependencies:
- requests
- questionary (for ASCII menu)

Install dependencies:
    pip install requests questionary
"""

import argparse
import csv
import json
import os
import sys
import warnings
from datetime import datetime
from typing import List, Dict

import requests
from urllib3.exceptions import InsecureRequestWarning

try:
    import questionary
except ImportError:
    print("questionary library is required. Install via `pip install questionary`.")
    sys.exit(1)


class ExivityAPI:
    def __init__(self, base_url: str, username: str = None, password: str = None, token: str = None, verify_ssl: bool = True):
        self.base_url = base_url.rstrip('/')  # remove trailing slash
        self.session = requests.Session()
        self.verify_ssl = verify_ssl
        self.token = token
        
        # Configure SSL verification
        if not verify_ssl:
            self.session.verify = False
            # Suppress only the single warning from urllib3 needed for unverified HTTPS requests
            warnings.filterwarnings('ignore', message='Unverified HTTPS request', category=InsecureRequestWarning)
            print("⚠️  WARNING: SSL certificate verification is disabled!")
        
        if username and password:
            self.authenticate(username, password)
        elif token:
            self.set_token(token)
        else:
            raise ValueError("Either username/password or token must be provided")

    # ------------------------- authentication ------------------------- #
    def authenticate(self, username: str, password: str):
        """Obtain JWT and store it"""
        url = f"{self.base_url}/v2/auth/token"
        data = {"username": username, "password": password}
        # Pass verify parameter to the post method
        resp = self.session.post(url, data=data, verify=self.verify_ssl)
        resp.raise_for_status()
        self.token = resp.json()["data"]["attributes"]["token"]
        self.set_token(self.token)

    def set_token(self, token: str):
        self.token = token
        # add Authorization header to session
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})

    # ------------------------- helper ------------------------- #
    def _request(self, method: str, endpoint: str, **kwargs):
        url = f"{self.base_url}{endpoint}"
        # Ensure verify parameter is passed to the request
        if 'verify' not in kwargs:
            kwargs['verify'] = self.verify_ssl
        resp = self.session.request(method, url, **kwargs)
        if resp.status_code == 401:
            raise RuntimeError("Unauthorized. Token may have expired. Re-authenticate.")
        resp.raise_for_status()
        return resp

    # ------------------------- rates ------------------------- #
    def rate_revision_exists(self, account_id: int, service_id: int, effective_date: str) -> bool:
        # Convert date format from YYYYMMDD to YYYY-MM-DD for API
        if len(effective_date) == 8 and effective_date.isdigit():
            formatted_date = f"{effective_date[:4]}-{effective_date[4:6]}-{effective_date[6:8]}"
        else:
            formatted_date = effective_date
            
        # Use v1 API for rates as v2 might not support all rate operations yet
        params = {
            "filter[account_id]": account_id,
            "filter[service_id]": service_id,
            "filter[effective_date]": f"={formatted_date}"
        }
        resp = self._request("GET", "/v1/rates", params=params)
        data = resp.json().get("data", [])
        return len(data) > 0

    def create_rate_revision(
        self,
        account_id: int,
        service_id: int,
        rate: float,
        cogs: float,
        effective_date: str
    ):
        # Convert date format from YYYYMMDD to YYYY-MM-DD for API
        if len(effective_date) == 8 and effective_date.isdigit():
            formatted_date = f"{effective_date[:4]}-{effective_date[4:6]}-{effective_date[6:8]}"
        else:
            formatted_date = effective_date
            
        # Use v1 API for rates
        payload = {
            "data": {
                "type": "rate",
                "attributes": {
                    "rate": rate,
                    "cogs_rate": cogs,
                    "effective_date": formatted_date
                },
                "relationships": {
                    "service": {"data": {"type": "service", "id": str(service_id)}},
                    "account": {"data": {"type": "account", "id": str(account_id)}}
                }
            }
        }
        headers = {
            "Content-Type": "application/vnd.api+json",
            "Accept": "application/vnd.api+json"
        }
        self._request("POST", "/v1/rates", json=payload, headers=headers)

    # ------------------------- environments ------------------------- #
    def get_environments(self) -> Dict[str, Dict]:
        """Get existing environments, returns dict of name -> {id, variables, default_flag}"""
        # Use v2 API with proper pagination parameters like the GUI
        resp = self._request("GET", "/v2/environments?page[offset]=0&page[limit]=-1&include=variables")
        response_data = resp.json()
        data = response_data.get("data", [])
        included = response_data.get("included", [])
        
        # Debug: Print raw API response structure
        print(f"DEBUG: Total data items: {len(data)}")
        print(f"DEBUG: Total included items: {len(included)}")
        
        # Debug: Show what's in included
        variable_count = len([item for item in included if item["type"] == "variable"])
        print(f"DEBUG: Found {variable_count} variables in included data")
        
        # First, create a map of environment names to IDs
        env_name_to_id = {}
        for env in data:
            env_name = env["attributes"]["name"]
            env_id = env["id"]
            env_name_to_id[env_name] = env_id
        
        # Build a map of variables by environment using the hour variable logic
        # Since the variables have "hour" values like "00", "01", "02", etc.
        # we can match them to environments H00, H01, H02, etc.
        variables_by_env = {}
        for item in included:
            if item["type"] == "variable":
                var_name = item["attributes"]["name"]
                var_value = item["attributes"]["value"]
                
                # Special logic for hour variables - map them by value
                if var_name == "hour" and len(var_value) == 2 and var_value.isdigit():
                    expected_env_name = f"H{var_value}"
                    if expected_env_name in env_name_to_id:
                        env_id = env_name_to_id[expected_env_name]
                        if env_id not in variables_by_env:
                            variables_by_env[env_id] = {}
                        variables_by_env[env_id][var_name] = var_value
                        print(f"DEBUG: Mapped variable '{var_name}' = '{var_value}' to env {expected_env_name} (ID: {env_id})")
                    else:
                        print(f"DEBUG: No environment found for hour value '{var_value}' (expected {expected_env_name})")
                else:
                    print(f"DEBUG: Non-hour variable '{var_name}' = '{var_value}' - skipping relationship mapping")
        
        print(f"DEBUG: variables_by_env has {len(variables_by_env)} environments with variables")
        
        result = {}
        for env in data:
            env_id = env["id"]
            env_name = env["attributes"]["name"]
            
            # Get variables for this environment
            env_variables = variables_by_env.get(env_id, {})
            
            result[env_name] = {
                "id": env_id,
                "variables": env_variables,
                "default_flag": env["attributes"].get("default_flag", False)
            }
            
            # Debug: Show what we got for each hourly environment
            if env_name.startswith('H') and len(env_name) == 3:
                print(f"DEBUG: {env_name} (ID: {env_id}) has variables: {list(env_variables.keys())}")
        
        return result

    def create_environment_with_variable(self, env_name: str, var_name: str, var_value: str) -> str:
        """Create environment and variable using atomic operations"""
        operations = [
            {
                "op": "add",
                "data": {
                    "type": "environment",
                    "lid": "new_env",
                    "attributes": {
                        "name": env_name,
                        "default_flag": False
                    }
                }
            },
            {
                "op": "add", 
                "data": {
                    "type": "variable",
                    "attributes": {
                        "name": var_name,
                        "value": var_value,
                        "encrypted": False
                    },
                    "relationships": {
                        "environment": {
                            "data": {
                                "type": "environment",
                                "lid": "new_env"
                            }
                        }
                    }
                }
            }
        ]
        
        payload = {"atomic:operations": operations}
        headers = {
            "Content-Type": "application/vnd.api+json;ext=\"https://jsonapi.org/ext/atomic\"",
            "Accept": "application/vnd.api+json"
        }
        
        resp = self._request("POST", "/v2/", json=payload, headers=headers)
        result = resp.json()
        return result["atomic:results"][0]["data"]["id"]

    def add_variable_to_environment(self, env_id: str, var_name: str, var_value: str):
        """Add a variable to an existing environment"""
        payload = {
            "data": {
                "type": "variable",
                "attributes": {
                    "name": var_name,
                    "value": var_value,
                    "encrypted": False
                },
                "relationships": {
                    "environment": {
                        "data": {
                            "type": "environment",
                            "id": env_id
                        }
                    }
                }
            }
        }
        headers = {
            "Content-Type": "application/vnd.api+json",
            "Accept": "application/vnd.api+json"
        }
        self._request("POST", "/v2/variables", json=payload, headers=headers)

    def ensure_hourly_environments(self) -> Dict[str, str]:
        """Ensure all H00-H23 environments exist with hour variables"""
        print("Checking/creating hourly environments...")
        existing_envs = self.get_environments()
        env_map = {}
        
        for hour in range(24):
            env_name = f"H{hour:02d}"
            hour_str = f"{hour:02d}"
            
            if env_name in existing_envs:
                env_info = existing_envs[env_name]
                env_id = env_info["id"]
                print(f"Environment {env_name} already exists (ID: {env_id})")
                
                # Check if hour variable exists and has correct value
                if "hour" not in env_info["variables"]:
                    try:
                        self.add_variable_to_environment(env_id, "hour", hour_str)
                        print(f"Created variable 'hour' = '{hour_str}' in {env_name}")
                    except Exception as e:
                        # 422 might mean variable already exists - check again
                        if "422" in str(e):
                            print(f"Variable might already exist in {env_name}, checking...")
                        else:
                            print(f"Warning: Could not create variable in {env_name}: {e}")
                elif env_info["variables"]["hour"] != hour_str:
                    print(f"Variable 'hour' in {env_name} has wrong value: '{env_info['variables']['hour']}' (should be '{hour_str}')")
                else:
                    print(f"Variable 'hour' already exists in {env_name} with correct value")
                
                env_map[env_name] = env_id
            else:
                print(f"Environment {env_name} does not exist, creating it...")
                # Try atomic operations first, fall back to individual creation
                try:
                    env_id = self.create_environment_with_variable(env_name, "hour", hour_str)
                    print(f"Created environment {env_name} (ID: {env_id}) with variable 'hour' = '{hour_str}'")
                    env_map[env_name] = env_id
                except Exception as e:
                    print(f"Warning: Atomic operation failed for {env_name}: {e}")
                    # Fall back to individual creation
                    try:
                        env_id = self.create_environment_individually(env_name)
                        self.add_variable_to_environment(env_id, "hour", hour_str)
                        print(f"Created environment {env_name} (ID: {env_id}) with variable 'hour' = '{hour_str}' (fallback)")
                        env_map[env_name] = env_id
                    except Exception as e2:
                        print(f"Error: Could not create environment {env_name}: {e2}")
        
        # Verify all environments were found/created
        missing_envs = []
        for hour in range(24):
            env_name = f"H{hour:02d}"
            if env_name not in env_map:
                missing_envs.append(env_name)
        
        if missing_envs:
            print(f"Error: Missing environments: {', '.join(missing_envs)}")
            raise RuntimeError(f"Could not find all required environments. Missing: {missing_envs}")
        
        print(f"✅ All 24 hourly environments confirmed to exist")
        return env_map

    def create_environment_individually(self, env_name: str) -> str:
        """Create just an environment without variables"""
        payload = {
            "data": {
                "type": "environment",
                "attributes": {
                    "name": env_name,
                    "default_flag": False
                }
            }
        }
        headers = {
            "Content-Type": "application/vnd.api+json",
            "Accept": "application/vnd.api+json"
        }
        resp = self._request("POST", "/v2/environments", json=payload, headers=headers)
        return resp.json()["data"]["id"]

    def delete_environment(self, env_id: str):
        """Delete an environment"""
        headers = {
            "Content-Type": "application/vnd.api+json",
            "Accept": "application/vnd.api+json"
        }
        self._request("DELETE", f"/v2/environments/{env_id}", headers=headers)

    def delete_hourly_environments(self) -> None:
        """Delete all H00-H23 environments, handling default environment properly"""
        print("Checking for hourly environments to delete...")
        existing_envs = self.get_environments()
        
        # Separate default and non-default environments
        default_env = None
        non_default_envs = []
        
        for hour in range(24):
            env_name = f"H{hour:02d}"
            
            if env_name in existing_envs:
                env_info = existing_envs[env_name]
                if env_info["default_flag"]:
                    default_env = (env_name, env_info["id"])
                else:
                    non_default_envs.append((env_name, env_info["id"]))
        
        deleted_count = 0
        
        # First, delete all non-default environments
        for env_name, env_id in non_default_envs:
            try:
                self.delete_environment(env_id)
                print(f"Deleted environment {env_name} (ID: {env_id})")
                deleted_count += 1
            except Exception as e:
                print(f"Error: Could not delete environment {env_name}: {e}")
        
        # Finally, delete the default environment if it exists
        if default_env:
            env_name, env_id = default_env
            try:
                self.delete_environment(env_id)
                print(f"Deleted default environment {env_name} (ID: {env_id})")
                deleted_count += 1
            except Exception as e:
                print(f"Error: Could not delete default environment {env_name}: {e}")
        
        # Check for environments that don't exist
        for hour in range(24):
            env_name = f"H{hour:02d}"
            if env_name not in existing_envs:
                print(f"Environment {env_name} does not exist, skipping...")
        
        print(f"Deleted {deleted_count} hourly environments.")

    def list_hourly_environments(self) -> Dict[str, str]:
        """List status of all H00-H23 environments"""
        print("Current status of hourly environments (H00-H23):")
        print("-" * 70)
        existing_envs = self.get_environments()
        env_map = {}
        
        # Debug: Show what environments we found
        print(f"DEBUG: API returned {len(existing_envs)} total environments")
        hourly_envs_found = [name for name in existing_envs.keys() if name.startswith('H') and len(name) == 3]
        print(f"DEBUG: Found hourly environments: {sorted(hourly_envs_found)}")
        print("-" * 70)
        
        for hour in range(24):
            env_name = f"H{hour:02d}"
            
            if env_name in existing_envs:
                env_info = existing_envs[env_name]
                env_id = env_info["id"]
                variables = env_info["variables"]
                is_default = env_info["default_flag"]
                
                has_hour_var = "hour" in variables
                hour_value = ""
                if has_hour_var:
                    actual_hour_value = variables["hour"]
                    hour_value = f" (hour='{actual_hour_value}')"
                    if actual_hour_value != f"{hour:02d}":
                        hour_value += f" ⚠️  WRONG VALUE (should be '{hour:02d}')"
                else:
                    hour_value = " ❌ NO HOUR VARIABLE"
                
                default_flag = " [DEFAULT]" if is_default else ""
                status = f"✓ EXISTS (ID: {env_id}){hour_value}{default_flag}"
                env_map[env_name] = env_id
            else:
                status = "✗ MISSING"
            
            print(f"{env_name}: {status}")
        
        print("-" * 70)
        existing_count = len(env_map)
        print(f"Total: {existing_count}/24 environments exist")
        
        if existing_count < 24:
            missing = [f"H{h:02d}" for h in range(24) if f"H{h:02d}" not in env_map]
            print(f"Missing: {', '.join(missing)}")
        
        return env_map

    # ------------------------- workflows ------------------------- #
    def create_workflow(self, name: str, description: str = "") -> str:
        payload = {
            "data": {
                "type": "workflow",
                "attributes": {"name": name, "description": description}
            }
        }
        headers = {
            "Content-Type": "application/vnd.api+json",
            "Accept": "application/vnd.api+json"
        }
        resp = self._request("POST", "/v2/workflows", json=payload, headers=headers)
        return resp.json()["data"]["id"]

    def add_workflow_step(
        self,
        workflow_id: str,
        step_order: int,
        step_type: str,
        attributes: Dict
    ):
        payload = {
            "data": {
                "type": "workflowstep",
                "attributes": {
                    "order": step_order,           # added order field
                    "type": step_type,
                    **attributes
                },
                "relationships": {
                    "workflow": {"data": {"type": "workflow", "id": workflow_id}}
                }
            }
        }
        headers = {
            "Content-Type": "application/vnd.api+json",
            "Accept": "application/vnd.api+json"
        }
        self._request("POST", "/v2/workflowsteps", json=payload, headers=headers)

    def find_workflows_by_name(self, name: str) -> List[str]:
        """Return list of workflow IDs matching name."""
        params = {"filter[name]": f"={name}"}
        resp = self._request("GET", "/v2/workflows", params=params)
        return [item["id"] for item in resp.json().get("data", [])]

    def delete_workflow(self, workflow_id: str):
        """Delete a workflow by ID."""
        self._request("DELETE", f"/v2/workflows/{workflow_id}")

    def create_workflow_with_steps(self, name: str, description: str, steps: List[Dict]) -> str:
        """Create workflow with steps using atomic operations"""
        import uuid
        
        workflow_lid = str(uuid.uuid4())
        operations = []
        
        # First operation: create the workflow with proper relationships
        operations.append({
            "op": "add",
            "data": {
                "type": "workflow",
                "attributes": {
                    "name": name,
                    "description": description
                },
                "relationships": {
                    "steps": {"data": []},
                    "schedules": {"data": []}
                },
                "lid": workflow_lid
            }
        })
        
        # Create steps with proper linking
        previous_step_lid = None
        for step in steps:
            step_lid = str(uuid.uuid4())
            
            # Convert our step format to the v2 API format
            step_operation = {
                "op": "add",
                "data": {
                    "type": "workflowstep",
                    "attributes": {
                        "step_type": step["type"],
                        "options": step["attributes"],
                        "wait": True,
                        "timeout": 3600
                    },
                    "relationships": {
                        "workflow": {
                            "data": {
                                "lid": workflow_lid,
                                "type": "workflow"
                            }
                        },
                        "previous": {
                            "data": {
                                "lid": previous_step_lid,
                                "type": "workflowstep"
                            } if previous_step_lid else None
                        }
                    },
                    "lid": step_lid
                }
            }
            
            operations.append(step_operation)
            previous_step_lid = step_lid
        
        payload = {"atomic:operations": operations}
        headers = {
            "Content-Type": "application/vnd.api+json;ext=\"https://jsonapi.org/ext/atomic\"",
            "Accept": "application/vnd.api+json"
        }
        
        resp = self._request("POST", "/v2/", json=payload, headers=headers)
        result = resp.json()
        return result["atomic:results"][0]["data"]["id"]

# ------------------------- CLI helpers ------------------------- #

def update_rates_from_csv(api: ExivityAPI, csv_path: str):
    # Try different encodings to handle various CSV file formats
    encodings_to_try = ['utf-8', 'utf-8-sig', 'cp1252', 'iso-8859-1']
    
    for encoding in encodings_to_try:
        try:
            with open(csv_path, 'r', newline='', encoding=encoding) as f:
                # Read first line to check headers
                first_line = f.readline().strip()
                print(f"DEBUG: First line with {encoding} encoding: '{first_line}'")
                print(f"DEBUG: First line bytes: {first_line.encode('utf-8')}")
                
                # Reset file pointer
                f.seek(0)
                
                reader = csv.DictReader(f)
                fieldnames = reader.fieldnames
                
                print(f"DEBUG: Detected fieldnames: {fieldnames}")
                print(f"DEBUG: Fieldnames as list: {list(fieldnames) if fieldnames else 'None'}")
                
                # Clean fieldnames (remove any hidden characters)
                if fieldnames:
                    cleaned_fieldnames = [field.strip().replace('\ufeff', '') for field in fieldnames]
                    print(f"DEBUG: Cleaned fieldnames: {cleaned_fieldnames}")
                    
                    # Check if we have the required columns after cleaning
                    required_cols = {"account_id", "service_id", "rate", "cogs", "revision_start_date"}
                    missing = required_cols - set(cleaned_fieldnames)
                    
                    if not missing:
                        print(f"✅ Successfully parsed CSV with {encoding} encoding")
                        break
                    else:
                        print(f"Missing columns with {encoding}: {missing}")
                        continue
                else:
                    print(f"No fieldnames detected with {encoding}")
                    continue
                    
        except UnicodeDecodeError:
            print(f"Failed to decode with {encoding}, trying next encoding...")
            continue
        except Exception as e:
            print(f"Error with {encoding}: {e}")
            continue
    else:
        print("Failed to parse CSV with any encoding. Please check the file format.")
        sys.exit(1)

    # Re-open with the successful encoding for processing
    with open(csv_path, 'r', newline='', encoding=encoding) as f:
        reader = csv.DictReader(f)
        
        # Clean the fieldnames
        reader.fieldnames = [field.strip().replace('\ufeff', '') for field in reader.fieldnames]
        
        required_cols = {"account_id", "service_id", "rate", "cogs", "revision_start_date"}
        missing = required_cols - set(reader.fieldnames)
        if missing:
            print(f"CSV missing columns: {', '.join(missing)}")
            print(f"Available columns: {', '.join(reader.fieldnames)}")
            sys.exit(1)

        print(f"Processing CSV file: {csv_path}")
        processed_count = 0
        skipped_count = 0
        
        for row_num, row in enumerate(reader, start=2):  # Start at 2 since row 1 is headers
            try:
                # Clean the row data (remove any hidden characters)
                cleaned_row = {k.strip(): v.strip() for k, v in row.items()}
                
                acc = int(cleaned_row["account_id"])
                svc = int(cleaned_row["service_id"])
                rate = float(cleaned_row["rate"])
                cogs = float(cleaned_row["cogs"])
                eff_date = cleaned_row["revision_start_date"]
                
                if api.rate_revision_exists(acc, svc, eff_date):
                    print(f"Row {row_num}: Rate revision already exists for account {acc}, service {svc} on {eff_date} – skipping.")
                    skipped_count += 1
                    continue
                    
                api.create_rate_revision(acc, svc, rate, cogs, eff_date)
                print(f"Row {row_num}: Created rate revision for account {acc}, service {svc} ({eff_date})")
                processed_count += 1
                
            except ValueError as e:
                print(f"Row {row_num}: Invalid data format - {e}")
                print(f"Row {row_num}: Data: {row}")
                continue
            except Exception as e:
                print(f"Row {row_num}: Error processing row - {e}")
                print(f"Row {row_num}: Data: {row}")
                continue
        
        print(f"✅ Finished processing CSV:")
        print(f"   - Processed: {processed_count} rows")
        print(f"   - Skipped: {skipped_count} rows")


def interactive_step_builder() -> tuple[List[Dict], str, str]:
    """Build workflow steps interactively, returns (steps, from_offset, to_offset)"""
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


def duplicate_steps_hourly(steps: List[Dict], env_map: Dict[str, str]) -> List[Dict]:
    """Duplicate steps for each hourly environment"""
    duplicated = []
    
    for hour in range(24):
        env_name = f"H{hour:02d}"
        
        # Check if environment exists
        if env_name not in env_map:
            print(f"Warning: Environment {env_name} not found, skipping...")
            continue
            
        env_id = env_map[env_name]
        
        for s in steps:
            clone = json.loads(json.dumps(s))  # deep copy
            
            # Add environment_id for extract/transform steps
            if clone["type"] in ("extract", "transform"):
                clone["attributes"]["environment_id"] = int(env_id)
            
            duplicated.append(clone)
    
    return duplicated


def create_workflow_interactively(api: ExivityAPI):
    name = questionary.text("Workflow name:").ask()
    description = questionary.text("Description (optional):").ask()

    # check existing
    existing = api.find_workflows_by_name(name)
    if existing:
        confirm = questionary.confirm(
            f"Workflow '{name}' exists (ID(s): {', '.join(existing)}). Delete and recreate?",
            default=False
        ).ask()
        if not confirm:
            print("Aborting – keeping existing workflow.")
            return
        for wid in existing:
            api.delete_workflow(wid)
            print(f"Deleted existing workflow ID {wid}")

    steps, from_offset, to_offset = interactive_step_builder()
    if not steps:
        print("No steps defined, aborting")
        return
    
    # Ensure hourly environments exist
    env_map = api.ensure_hourly_environments()
    
    # Duplicate steps for all 24 hours
    all_steps = duplicate_steps_hourly(steps, env_map)
    
    # Create workflow with all steps using atomic operations
    try:
        workflow_id = api.create_workflow_with_steps(name, description, all_steps)
        print(f"Workflow '{name}' ({workflow_id}) created with {len(all_steps)} steps across 24 hourly environments.")
        print(f"Using offsets: from={from_offset}, to={to_offset}")
    except Exception as e:
        print(f"Error creating workflow: {e}")
        # Fallback to legacy method if atomic operations fail
        print("Falling back to individual step creation...")
        try:
            workflow_id = api.create_workflow(name, description)
            print(f"Created workflow '{name}' ({workflow_id}), but could not add steps.")
            print("You may need to add steps manually through the GUI.")
        except Exception as e2:
            print(f"Error creating workflow: {e2}")


def delete_hourly_environments_interactively(api: ExivityAPI):
    """Interactive deletion of hourly environments with confirmation"""
    confirm = questionary.confirm(
        "⚠️  WARNING: This will delete ALL environments named H00 through H23 and their variables. Are you sure?",
        default=False
    ).ask()
    
    if not confirm:
        print("Operation cancelled.")
        return
    
    # Double confirmation for safety
    final_confirm = questionary.confirm(
        "This action cannot be undone. Type 'yes' to proceed with deletion:",
        default=False
    ).ask()
    
    if not final_confirm:
        print("Operation cancelled.")
        return
    
    api.delete_hourly_environments()


def list_hourly_environments_status(api: ExivityAPI):
    """Show status of all hourly environments"""
    api.list_hourly_environments()


def recreate_missing_environments(api: ExivityAPI):
    """Recreate any missing H00-H23 environments"""
    confirm = questionary.confirm(
        "This will create any missing H00-H23 environments. Continue?",
        default=True
    ).ask()
    
    if not confirm:
        print("Operation cancelled.")
        return
    
    try:
        env_map = api.ensure_hourly_environments()
        print(f"✅ Successfully ensured all 24 hourly environments exist.")
    except Exception as e:
        print(f"❌ Error ensuring environments: {e}")


def main(): 
    base_url = questionary.text("Base URL (e.g. https://api.example.com):", default="https://localhost").ask()
    
    # Ask about SSL verification for self-signed certificates
    verify_ssl = questionary.confirm(
        "Verify SSL certificates? (Choose 'No' for self-signed certificates):", 
        default=True
    ).ask()
    
    username = questionary.text("Username:", default="admin").ask()
    password = questionary.password("Password:", default="exivity").ask()
    
    try:
        api = ExivityAPI(base_url=base_url, username=username, password=password, verify_ssl=verify_ssl)
    except requests.exceptions.SSLError as e:
        print(f"SSL Error: {e}")
        print("If you're using self-signed certificates, restart and choose 'No' for SSL verification.")
        sys.exit(1)
    except Exception as e:
        print(f"Authentication failed: {e}")
        sys.exit(1)

    while True:
        choice = questionary.select(
            "Main menu",
            choices=[
                "Update rates from CSV",
                "Create hourly workflow",
                "List hourly environments status",
                "Recreate missing hourly environments",
                "Delete hourly environments (H00-H23)",
                "Exit"
            ]
        ).ask()
        if choice == "Update rates from CSV":
            csv_path = questionary.path("CSV file path:").ask()
            update_rates_from_csv(api, csv_path)
        elif choice == "Create hourly workflow":
            create_workflow_interactively(api)
        elif choice == "List hourly environments status":
            list_hourly_environments_status(api)
        elif choice == "Recreate missing hourly environments":
            recreate_missing_environments(api)
        elif choice == "Delete hourly environments (H00-H23)":
            delete_hourly_environments_interactively(api)
        elif choice == "Exit":
            print("Goodbye!")
            break


if __name__ == "__main__":
    main()
