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
            
        # Try v2 API first, fall back to v1 if needed
        try:
            params = {
                "filter[account_id]": account_id,
                "filter[service_id]": service_id,
                "filter[effective_date]": f"={formatted_date}"
            }
            resp = self._request("GET", "/v2/rates", params=params)
            data = resp.json().get("data", [])
            return len(data) > 0
        except Exception as e:
            print(f"DEBUG: v2 rates API failed: {e}")
            print("DEBUG: Falling back to v1 rates API for checking...")
            
            # Fall back to v1 API
            try:
                params = {
                    "filter[account_id]": account_id,
                    "filter[service_id]": service_id,
                    "filter[effective_date]": f"={formatted_date}"
                }
                headers = {
                    "Content-Type": "application/vnd.api+json",
                    "Accept": "application/vnd.api+json"
                }
                resp = self._request("GET", "/v1/rates", params=params, headers=headers)
                data = resp.json().get("data", [])
                return len(data) > 0
            except Exception as e2:
                print(f"DEBUG: v1 rates API also failed: {e2}")
                # If both fail, assume it doesn't exist
                return False

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
            
        # Use v2 atomic operations for single rate creation
        import uuid
        
        operation = {
            "op": "add",
            "data": {
                "type": "rate",
                "attributes": {
                    "rate": rate,
                    "rate_col": None,
                    "min_commit": None,
                    "effective_date": formatted_date,
                    "end_date": None,
                    "fixed": None,
                    "fixed_col": None,
                    "cogs_rate": cogs,
                    "cogs_rate_col": None,
                    "cogs_fixed": None,
                    "cogs_fixed_col": None,
                    "tier_aggregation_level": None
                },
                "relationships": {
                    "service": {"data": {"id": str(service_id), "type": "service"}},
                    "account": {"data": {"type": "account", "id": str(account_id)}},
                    "ratetiers": {"data": []}
                },
                "lid": str(uuid.uuid4())
            }
        }
        
        payload = {"atomic:operations": [operation]}
        headers = {
            "Content-Type": "application/vnd.api+json;ext=\"https://jsonapi.org/ext/atomic\"",
            "Accept": "application/vnd.api+json"
        }
        
        try:
            self._request("POST", "/v2/", json=payload, headers=headers)
        except Exception as e:
            print(f"DEBUG: v2 atomic rate creation failed: {e}")
            print("DEBUG: Falling back to v1 rate creation...")
            
            # Fall back to v1 API
            payload_v1 = {
                "data": {
                    "type": "rate",
                    "attributes": {
                        "rate": rate,
                        "rate_col": None,
                        "min_commit": None,
                        "effective_date": formatted_date,
                        "end_date": None,
                        "fixed": None,
                        "fixed_col": None,
                        "cogs_rate": cogs,
                        "cogs_rate_col": None,
                        "cogs_fixed": None,
                        "cogs_fixed_col": None,
                        "tier_aggregation_level": None
                    },
                    "relationships": {
                        "service": {"data": {"id": str(service_id), "type": "service"}},
                        "account": {"data": {"type": "account", "id": str(account_id)}}
                    }
                }
            }
            headers_v1 = {
                "Content-Type": "application/vnd.api+json",
                "Accept": "application/vnd.api+json"
            }
            self._request("POST", "/v1/rates", json=payload_v1, headers=headers_v1)

    def create_rate_revisions_batch(self, rate_data: List[Dict]) -> Dict:
        """Create multiple rate revisions using atomic operations"""
        import uuid
        
        operations = []
        
        for rate in rate_data:
            # Convert date format from YYYYMMDD to YYYY-MM-DD for API
            effective_date = rate["effective_date"]
            if len(effective_date) == 8 and effective_date.isdigit():
                formatted_date = f"{effective_date[:4]}-{effective_date[4:6]}-{effective_date[6:8]}"
            else:
                formatted_date = effective_date
            
            operation = {
                "op": "add",
                "data": {
                    "type": "rate",
                    "attributes": {
                        "rate": float(rate["rate"]),
                        "rate_col": None,
                        "min_commit": None,
                        "effective_date": formatted_date,
                        "end_date": None,
                        "fixed": None,
                        "fixed_col": None,
                        "cogs_rate": float(rate["cogs"]),
                        "cogs_rate_col": None,
                        "cogs_fixed": None,
                        "cogs_fixed_col": None,
                        "tier_aggregation_level": None
                    },
                    "relationships": {
                        "service": {"data": {"id": str(rate["service_id"]), "type": "service"}},
                        "account": {"data": {"type": "account", "id": str(rate["account_id"])}},
                        "ratetiers": {"data": []}
                    },
                    "lid": str(uuid.uuid4())
                }
            }
            operations.append(operation)
        
        payload = {"atomic:operations": operations}
        headers = {
            "Content-Type": "application/vnd.api+json;ext=\"https://jsonapi.org/ext/atomic\"",
            "Accept": "application/vnd.api+json"
        }
        
        resp = self._request("POST", "/v2/", json=payload, headers=headers)
        return resp.json()

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
        
        # Collect all rate data and check for existing revisions
        new_rates = []
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
                
                # Check if rate revision already exists
                if api.rate_revision_exists(acc, svc, eff_date):
                    print(f"Row {row_num}: Rate revision already exists for account {acc}, service {svc} on {eff_date} – skipping.")
                    skipped_count += 1
                    continue
                
                # Add to batch for creation
                new_rates.append({
                    "account_id": acc,
                    "service_id": svc,
                    "rate": rate,
                    "cogs": cogs,
                    "effective_date": eff_date,
                    "row_num": row_num
                })
                
            except ValueError as e:
                print(f"Row {row_num}: Invalid data format - {e}")
                print(f"Row {row_num}: Data: {row}")
                continue
            except Exception as e:
                print(f"Row {row_num}: Error processing row - {e}")
                print(f"Row {row_num}: Data: {row}")
                continue
        
        # Create rates in batches using atomic operations
        processed_count = 0
        if new_rates:
            # Process in batches of 50 to avoid too large requests
            batch_size = 50
            for i in range(0, len(new_rates), batch_size):
                batch = new_rates[i:i+batch_size]
                
                try:
                    print(f"Creating batch of {len(batch)} rate revisions...")
                    result = api.create_rate_revisions_batch(batch)
                    
                    # Count successful creations
                    atomic_results = result.get("atomic:results", [])
                    successful_in_batch = len([r for r in atomic_results if "data" in r])
                    processed_count += successful_in_batch
                    
                    for rate in batch:
                        print(f"Row {rate['row_num']}: Created rate revision for account {rate['account_id']}, service {rate['service_id']} ({rate['effective_date']})")
                    
                except Exception as e:
                    print(f"Error creating batch: {e}")
                    # Fall back to individual creation for this batch
                    print("Falling back to individual rate creation...")
                    for rate in batch:
                        try:
                            api.create_rate_revision(
                                rate["account_id"], 
                                rate["service_id"], 
                                rate["rate"], 
                                rate["cogs"], 
                                rate["effective_date"]
                            )
                            print(f"Row {rate['row_num']}: Created rate revision for account {rate['account_id']}, service {rate['service_id']} ({rate['effective_date']})")
                            processed_count += 1
                        except Exception as e2:
                            print(f"Row {rate['row_num']}: Error creating individual rate - {e2}")
        
        print(f"✅ Finished processing CSV:")
        print(f"   - Processed: {processed_count} rows")
        print(f"   - Skipped: {skipped_count} rows")

# ------------------------- CLI helpers ------------------------- #

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
