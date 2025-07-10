"""
Exivity API Client

Handles authentication and basic API operations.
"""

import warnings
import requests
import uuid
from typing import Dict, List, Optional, Any
from urllib3.exceptions import InsecureRequestWarning


class ExivityAPI:
    """Main API client for Exivity"""
    
    def __init__(self, base_url: str, username: str = None, password: str = None, 
                 token: str = None, verify_ssl: bool = True):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.verify_ssl = verify_ssl
        self.token = token
        
        # Configure SSL verification
        if not verify_ssl:
            self.session.verify = False
            warnings.filterwarnings('ignore', message='Unverified HTTPS request', 
                                  category=InsecureRequestWarning)
            print("⚠️  WARNING: SSL certificate verification is disabled!")
        
        if username and password:
            self.authenticate(username, password)
        elif token:
            self.set_token(token)
        else:
            raise ValueError("Either username/password or token must be provided")

    def authenticate(self, username: str, password: str):
        """Obtain JWT and store it"""
        url = f"{self.base_url}/v2/auth/token"
        data = {"username": username, "password": password}
        resp = self.session.post(url, data=data, verify=self.verify_ssl)
        resp.raise_for_status()
        self.token = resp.json()["data"]["attributes"]["token"]
        self.set_token(self.token)

    def set_token(self, token: str):
        """Set the authentication token"""
        self.token = token
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})

    def _request(self, method: str, endpoint: str, **kwargs):
        """Make an authenticated request to the API - simplified like original"""
        url = f"{self.base_url}{endpoint}"
        
        # Ensure verify parameter is passed to the request
        if 'verify' not in kwargs:
            kwargs['verify'] = self.verify_ssl
            
        resp = self.session.request(method, url, **kwargs)
        if resp.status_code == 401:
            raise RuntimeError("Unauthorized. Token may have expired. Re-authenticate.")
        resp.raise_for_status()
        return resp

    def debug_api_endpoints(self):
        """Debug method to check what endpoints are available"""
        print("🔍 Debugging API endpoints...")
        
        # Try to get API documentation or available endpoints
        try:
            resp = self._request("GET", "/")
            print(f"Root endpoint response: {resp.status_code}")
        except Exception as e:
            print(f"Root endpoint failed: {e}")
        
        # Try v2 endpoints
        test_endpoints = ["/v2", "/v2/rates", "/v2/environments", "/v2/workflows"]
        for endpoint in test_endpoints:
            try:
                resp = self._request("GET", endpoint)
                print(f"✅ {endpoint}: {resp.status_code}")
            except Exception as e:
                print(f"❌ {endpoint}: {e}")
        
        # Try v1 endpoints
        test_endpoints_v1 = ["/v1", "/v1/rates", "/v1/environments"]
        for endpoint in test_endpoints_v1:
            try:
                resp = self._request("GET", endpoint)
                print(f"✅ {endpoint}: {resp.status_code}")
            except Exception as e:
                print(f"❌ {endpoint}: {e}")

    # ------------------------- rates ------------------------- #
    def rate_revision_exists(self, account_id: int, service_id: int, effective_date: str) -> bool:
        """Check if a rate revision already exists using dump data (much more efficient)"""
        # Convert date format from YYYYMMDD to YYYY-MM-DD for comparison
        if len(effective_date) == 8 and effective_date.isdigit():
            formatted_date = f"{effective_date[:4]}-{effective_date[4:6]}-{effective_date[6:8]}"
        else:
            formatted_date = effective_date
        
        # Use cached dump data if available, otherwise fetch it
        if not hasattr(self, '_cached_dump_data'):
            self._cached_dump_data = self.fetch_dump_data()
        
        rates = self._cached_dump_data.get('rate', [])
        
        # Check if rate exists in dump data
        for rate in rates:
            if (str(rate.get('account_id', '')) == str(account_id) and 
                str(rate.get('service_id', '')) == str(service_id) and 
                rate.get('effective_date', '') == formatted_date):
                return True
        
        return False

    def clear_dump_cache(self):
        """Clear cached dump data to force fresh fetch on next request"""
        if hasattr(self, '_cached_dump_data'):
            delattr(self, '_cached_dump_data')

    def create_rate_revision(self, account_id: int, service_id: int, rate: float, cogs: float, effective_date: str):
        """Create single rate revision with multiple fallback approaches"""
        # Convert date format from YYYYMMDD to YYYY-MM-DD for API
        if len(effective_date) == 8 and effective_date.isdigit():
            formatted_date = f"{effective_date[:4]}-{effective_date[4:6]}-{effective_date[6:8]}"
        else:
            formatted_date = effective_date
        
        print(f"DEBUG: Creating rate for account_id={account_id}, service_id={service_id}, rate={rate}, cogs={cogs}, date={formatted_date}")
        
        last_error = None  # Track the last error for final exception
        
        # Approach 1: v2 atomic operations (original working version)
        try:
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
            
            print("DEBUG: Trying v2 atomic operations...")
            self._request("POST", "/v2/", json=payload, headers=headers)
            print("DEBUG: v2 atomic rate creation succeeded!")
            return
            
        except Exception as e:
            print(f"DEBUG: v2 atomic rate creation failed: {e}")
            last_error = e
        
        # Approach 2: v1 API standard creation
        try:
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
            
            print("DEBUG: Trying v1 rate creation...")
            self._request("POST", "/v1/rates", json=payload_v1, headers=headers_v1)
            print("DEBUG: v1 rate creation succeeded!")
            return
            
        except Exception as e:
            print(f"DEBUG: v1 rate creation failed: {e}")
            last_error = e
        
        # Approach 3: Simplified v2 rate creation
        try:
            payload_simple = {
                "data": {
                    "type": "rate",
                    "attributes": {
                        "rate": rate,
                        "cogs_rate": cogs,
                        "effective_date": formatted_date
                    },
                    "relationships": {
                        "service": {"data": {"id": str(service_id), "type": "service"}},
                        "account": {"data": {"type": "account", "id": str(account_id)}}
                    }
                }
            }
            headers_simple = {
                "Content-Type": "application/vnd.api+json",
                "Accept": "application/vnd.api+json"
            }
            
            print("DEBUG: Trying simplified v2 rate creation...")
            self._request("POST", "/v2/rates", json=payload_simple, headers=headers_simple)
            print("DEBUG: Simplified v2 rate creation succeeded!")
            return
            
        except Exception as e:
            print(f"DEBUG: Simplified v2 rate creation failed: {e}")
            last_error = e
        
        # If all approaches fail, raise the last exception
        raise Exception(f"All rate creation approaches failed. Last error: {last_error}")

    def create_rate_revisions_batch(self, rate_data: List[Dict]) -> Dict:
        """Create multiple rate revisions using atomic operations - exact copy from working version"""
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

    # ------------------------- workflows ------------------------- #
    def find_workflows_by_name(self, name: str) -> List[str]:
        """Find workflows by name and return their IDs"""
        try:
            resp = self._request("GET", "/v2/workflows", params={"filter[name]": name})
            data = resp.json().get("data", [])
            return [item["id"] for item in data]
        except Exception:
            return []

    def delete_workflow(self, workflow_id: str):
        """Delete a workflow by ID"""
        self._request("DELETE", f"/v2/workflows/{workflow_id}")

    def create_workflow(self, name: str, description: str = "") -> str:
        """Create a basic workflow and return its ID"""
        payload = {
            "data": {
                "type": "workflow",
                "attributes": {
                    "name": name,
                    "description": description
                }
            }
        }
        headers = {
            "Content-Type": "application/vnd.api+json",
            "Accept": "application/vnd.api+json"
        }
        resp = self._request("POST", "/v2/workflows", json=payload, headers=headers)
        return resp.json()["data"]["id"]

    def create_workflow_with_steps(self, name: str, description: str, steps: List[Dict]) -> str:
        """Create a workflow with steps using atomic operations - EXACT format from working GUI"""
        workflow_lid = str(uuid.uuid4())
        operations = []
        
        # Create workflow operation with proper relationships structure
        workflow_operation = {
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
        }
        operations.append(workflow_operation)
        
        # Add step operations with proper chaining and structure
        previous_step_lid = None
        
        for i, step in enumerate(steps):
            step_lid = str(uuid.uuid4())
            
            # Build step options (nested under options, not direct attributes)
            step_options = {}
            
            # Add script name
            if "script" in step["attributes"]:
                step_options["script"] = step["attributes"]["script"]
            
            # Add date offsets for extract/transform steps
            if step["type"] in ("extract", "transform"):
                step_options["from_date_offset"] = step["attributes"].get("from_date_offset", 0)
                step_options["to_date_offset"] = step["attributes"].get("to_date_offset", 0)
                
                # Environment ID as string (required for extract/transform)
                if "environment_id" in step["attributes"]:
                    step_options["environment_id"] = str(step["attributes"]["environment_id"])
            
            # Add report_id for prepare_report steps
            if step["type"] == "prepare_report" and "report_id" in step["attributes"]:
                step_options["report_id"] = step["attributes"]["report_id"]
                step_options["from_date_offset"] = step["attributes"].get("from_date_offset", 0)
                step_options["to_date_offset"] = step["attributes"].get("to_date_offset", 0)
            
            # Add arguments if present (for extract steps)
            if "arguments" in step["attributes"] and step["attributes"]["arguments"]:
                step_options["arguments"] = step["attributes"]["arguments"]
            
            # Build previous relationship
            previous_relationship = {"data": None}
            if previous_step_lid:
                previous_relationship = {
                    "data": {
                        "lid": previous_step_lid,
                        "type": "workflowstep"
                    }
                }
            
            step_operation = {
                "op": "add",
                "data": {
                    "type": "workflowstep",
                    "attributes": {
                        "step_type": step["type"],
                        "options": step_options,  # Nest all options here
                        "wait": True,  # Required
                        "timeout": 3600  # Required
                    },
                    "relationships": {
                        "workflow": {
                            "data": {
                                "lid": workflow_lid,
                                "type": "workflow"
                            }
                        },
                        "previous": previous_relationship
                    },
                    "lid": step_lid
                }
            }
            
            operations.append(step_operation)
            previous_step_lid = step_lid  # For chaining next step
        
        payload = {"atomic:operations": operations}
        headers = {
            "Content-Type": "application/vnd.api+json;ext=\"https://jsonapi.org/ext/atomic\"",
            "Accept": "application/vnd.api+json"
        }
        
        try:
            resp = self._request("POST", "/v2/", json=payload, headers=headers)
            
            # Extract workflow ID from atomic results
            atomic_results = resp.json().get("atomic:results", [])
            
            for result in atomic_results:
                if result.get("data", {}).get("type") == "workflow":
                    workflow_id = result["data"]["id"]
                    return workflow_id
            
            raise Exception("Could not find workflow ID in atomic results")
            
        except Exception as e:
            print(f"❌ Atomic workflow creation failed: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"Response status code: {e.response.status_code}")
                try:
                    error_details = e.response.json()
                    print("Error details:")
                    import json
                    print(json.dumps(error_details, indent=2))
                    
                    # Extract specific error information
                    if "errors" in error_details:
                        for error in error_details["errors"]:
                            status = error.get("status", "Unknown")
                            title = error.get("title", "Unknown Error")
                            detail = error.get("detail", "No details provided")
                            source = error.get("source", {})
                            print(f"Error - Status: {status}, Title: {title}")
                            print(f"Detail: {detail}")
                            if source:
                                print(f"Source: {source}")
                            
                except Exception as json_error:
                    print(f"Could not parse error response as JSON: {json_error}")
                    print(f"Raw error response:")
                    print(e.response.text)
            
            # Re-raise the original exception
            raise e

    # ------------------------- environments ------------------------- #
    def find_environment_by_name(self, name: str) -> Optional[str]:
        """Find environment by name and return its ID"""
        try:
            resp = self._request("GET", "/v2/environments", params={"filter[name]": name})
            data = resp.json().get("data", [])
            return data[0]["id"] if data else None
        except Exception:
            return None

    def create_environment(self, name: str) -> str:
        """Create an environment using the exact v2 API format that works in Postman"""
        # Use the EXACT format that works in Postman - v2/environments endpoint
        # Note: description is NOT a valid field for environments, boolean must be lowercase
        payload = {
            "data": {
                "type": "environment",
                "attributes": {
                    "name": name,
                    "default_flag": False  # lowercase boolean: false
                }
            }
        }
        
        # Note: Do NOT add description - it's not a valid field for environments
        
        # Use exact headers from Postman
        headers = {
            "Content-Type": "application/vnd.api+json",
            "Accept": "application/vnd.api+json"
        }
        
        print(f"DEBUG: Creating environment using v2 API (Postman format): {name}")
        print(f"DEBUG: Payload: {payload}")
        print(f"DEBUG: Headers: {headers}")
        print(f"DEBUG: URL: {self.base_url}/v2/environments")
        
        try:
            resp = self._request("POST", "/v2/environments", json=payload, headers=headers)
            
            # Extract environment ID from response
            response_data = resp.json()
            env_id = response_data["data"]["id"]
            print(f"DEBUG: v2 environment creation succeeded! ID: {env_id}")
            
            return env_id
            
        except Exception as e:
            print(f"DEBUG: v2 environment creation failed: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"DEBUG: Response status code: {e.response.status_code}")
                try:
                    error_details = e.response.json()
                    print(f"DEBUG: Error details JSON: {error_details}")
                    
                    # Extract specific error information
                    if "errors" in error_details:
                        for error in error_details["errors"]:
                            status = error.get("status", "Unknown")
                            title = error.get("title", "Unknown Error")
                            detail = error.get("detail", "No details provided")
                            print(f"DEBUG: Error - Status: {status}, Title: {title}, Detail: {detail}")
                            
                except:
                    print(f"DEBUG: Error response text: {e.response.text}")
            raise Exception(f"Environment creation failed: {e}")

    def create_environment_with_variables(self, name: str, variables: Dict[str, str] = None) -> str:
        """Create an environment with variables using v2 + v1 APIs - two step process"""
        # Step 1: Create the environment using the working v2 format (ignore description parameter)
        env_id = self.create_environment(name)  # Don't pass description since it's not supported
        
        # Step 2: Add variables if provided (separate v1 API calls)
        if variables:
            for var_name, var_value in variables.items():
                try:
                    self.create_environment_variable(env_id, var_name, var_value)
                    print(f"DEBUG: Successfully added variable {var_name}={var_value} to environment {name}")
                except Exception as e:
                    print(f"DEBUG: Failed to add variable {var_name} to environment {name}: {e}")
        
        return env_id

    def ensure_hourly_environments(self) -> Dict[str, str]:
        """Ensure all 24 hourly environments (H00-H23) exist, return name->id map"""
        env_map = {}
        
        print("🔍 Checking hourly environments...")
        
        # First, check what environments already exist
        default_env = self.get_default_environment()
        if default_env:
            default_name = default_env.get('attributes', {}).get('name', 'Unknown')
            print(f"   🏠 Default environment: {default_name} (ID: {default_env.get('id')})")
        else:
            print("   ⚠️  No default environment found")
        
        for hour in range(24):
            env_name = f"H{hour:02d}"
            env_id = self.find_environment_by_name(env_name)
            
            if env_id:
                print(f"   ✅ Environment {env_name} exists (ID: {env_id})")
                env_map[env_name] = env_id
            else:
                print(f"   ➕ Creating environment {env_name}...")
                try:
                    # Create environment with hour variable (don't pass description since it's not supported)
                    hour_value = f"{hour:02d}"
                    variables = {"hour": hour_value}
                    
                    env_id = self.create_environment_with_variables(
                        env_name, 
                        variables
                    )
                    env_map[env_name] = env_id
                    
                    print(f"   ✅ Created environment {env_name} (ID: {env_id}) with hour variable = {hour_value}")
                    
                except Exception as e:
                    print(f"   ❌ Failed to create environment {env_name}: {e}")
                    
                    # Try a simpler approach without variables for this environment
                    print(f"   🔄 Trying to create {env_name} without variables...")
                    try:
                        env_id = self.create_environment(env_name)  # No description
                        env_map[env_name] = env_id
                        print(f"   ✅ Created environment {env_name} (ID: {env_id}) without variables")
                        
                        # Now try to add the hour variable separately
                        try:
                            self.create_environment_variable(env_id, "hour", hour_value)
                            print(f"   ✅ Added hour variable = {hour_value} to {env_name}")
                        except Exception as var_e:
                            print(f"   ⚠️  Could not add hour variable to {env_name}: {var_e}")
                            
                    except Exception as e2:
                        print(f"   ❌ Even simple creation failed for {env_name}: {e2}")
                        continue
        
        return env_map

    def delete_environment(self, env_id: str):
        """Delete an environment by ID - but refuse to delete default environment"""
        try:
            # Check if this is the default environment
            default_env = self.get_default_environment()
            if default_env and default_env.get('id') == env_id:
                raise Exception("Cannot delete the default environment. It must remain as the system default.")
            
            self._request("DELETE", f"/v2/environments/{env_id}")
        except Exception as e:
            if "default environment" in str(e):
                raise e  # Re-raise our custom error
            else:
                # This might be the server refusing to delete default environment too
                raise Exception(f"Failed to delete environment: {e}")

    def delete_hourly_environments(self):
        """Delete all hourly environments H00-H23, but protect the default environment"""
        print("🗑️  Deleting hourly environments...")
        print("💡 Note: Default environment will be protected from deletion")
        
        deleted_count = 0
        protected_count = 0
        
        # Get default environment info
        default_env = self.get_default_environment()
        default_env_name = None
        if default_env:
            default_env_name = default_env.get('attributes', {}).get('name')
            print(f"   🛡️  Protected default environment: {default_env_name} (ID: {default_env.get('id')})")
        
        # Try to delete all hourly environments, but respect default protection
        for hour in range(24):
            env_name = f"H{hour:02d}"
            env_id = self.find_environment_by_name(env_name)
            
            if env_id:
                # Check if this is the default environment
                if default_env and default_env.get('id') == env_id:
                    print(f"   🛡️  Skipping {env_name} (ID: {env_id}) - Default environment cannot be deleted")
                    protected_count += 1
                    continue
                
                try:
                    self.delete_environment(env_id)
                    print(f"   ✅ Deleted {env_name} (ID: {env_id})")
                    deleted_count += 1
                except Exception as e:
                    if "default environment" in str(e).lower():
                        print(f"   🛡️  Protected {env_name} (ID: {env_id}) - Default environment")
                        protected_count += 1
                    else:
                        print(f"   ❌ Failed to delete {env_name}: {e}")
            else:
                print(f"   ⏭️  {env_name} (Not found)")
        
        print(f"\n📊 Deletion summary:")
        print(f"   - Deleted: {deleted_count} environments")
        print(f"   - Protected (default): {protected_count} environments")
        
        if protected_count > 0:
            print(f"💡 The default environment cannot be deleted to maintain system integrity")

    def list_hourly_environments(self):
        """List status of all hourly environments H00-H23"""
        print("📋 Hourly Environments Status:")
        
        existing_count = 0
        missing_count = 0
        
        for hour in range(24):
            env_name = f"H{hour:02d}"
            env_id = self.find_environment_by_name(env_name)
            
            if env_id:
                print(f"   ✅ {env_name} (ID: {env_id})")
                existing_count += 1
            else:
                print(f"   ❌ {env_name} (Missing)")
                missing_count += 1
        
        print(f"\n📊 Summary: {existing_count} existing, {missing_count} missing")

    def create_environment_variable(self, environment_id: str, name: str, value: str, encrypted: bool = False):
        """Create a variable for an environment using v1 API (this one should work)"""
        payload = {
            "data": {
                "type": "variable",
                "attributes": {
                    "name": name,
                    "value": value,
                    "encrypted": encrypted
                },
                "relationships": {
                    "environment": {
                        "data": {
                            "type": "environment",
                            "id": environment_id
                        }
                    }
                }
            }
        }
        
        headers = {
            "Content-Type": "application/vnd.api+json",
            "Accept": "application/vnd.api+json"
        }
        
        print(f"DEBUG: Creating variable {name}={value} for environment {environment_id}")
        print(f"DEBUG: Using v1/variables endpoint")
        
        try:
            resp = self._request("POST", "/v1/variables", json=payload, headers=headers)
            
            response_data = resp.json()
            var_id = response_data["data"]["id"]
            print(f"DEBUG: Variable creation succeeded! ID: {var_id}")
            
            return var_id
            
        except Exception as e:
            print(f"DEBUG: Variable creation failed: {e}")
            if hasattr(e, 'response') and e.response:
                try:
                    error_details = e.response.json()
                    print(f"DEBUG: Variable error details: {error_details}")
                except:
                    print(f"DEBUG: Variable error text: {e.response.text}")
            raise

    def list_environments(self) -> List[Dict]:
        """List all environments"""
        try:
            resp = self._request("GET", "/v2/environments")
            return resp.json().get("data", [])
        except Exception:
            return []

    def get_default_environment(self) -> Optional[Dict]:
        """Get the default environment"""
        try:
            environments = self.list_environments()
            for env in environments:
                if env.get('attributes', {}).get('default_flag') is True:
                    return env
            return None
        except Exception:
            return None

    # ------------------------- dump data for insights ------------------------- #
    def fetch_dump_data(self) -> Dict[str, List[Dict]]:
        """Fetch comprehensive dump data including accounts, services, and rates"""
        try:
            # Use v1/dump/data with correct parameters and content type
            params = {
                "models": "account,adjustment,adjustables,metadata,rate,reportdefinition,service,servicecategory",
                "progress": "0"
            }
            headers = {
                "Accept": "text/csv"  # Important: Accept CSV format, not JSON
            }
            resp = self._request("GET", "/v1/dump/data", params=params, headers=headers)
            
            # Parse the CSV-like response
            return self._parse_dump_response(resp.text)
            
        except Exception as e:
            print(f"❌ Failed to fetch dump data: {e}")
            print(f"DEBUG: Trying alternative dump endpoint formats...")
            
            # Try alternative formats - all using v1/dump/data
            alternatives = [
                {
                    "endpoint": "/v1/dump/data",
                    "params": {"models": "account,rate,service", "progress": "0"},
                    "headers": {"Accept": "text/csv"}
                },
                {
                    "endpoint": "/v1/dump/data", 
                    "params": {"models": "account,service,rate"},
                    "headers": {"Accept": "text/csv"}
                },
                {
                    "endpoint": "/v1/dump/data",
                    "params": {"models": "account", "progress": "0"},
                    "headers": {"Accept": "text/csv"}
                },
                # Fallback to v2 if v1 doesn't work
                {
                    "endpoint": "/v2/dump",
                    "params": {"data": "account,service,rate", "progress": "0"},
                    "headers": {"Accept": "text/csv"}
                }
            ]
            
            for i, alt in enumerate(alternatives, 1):
                try:
                    print(f"DEBUG: Trying alternative {i}: {alt['endpoint']} with params: {alt['params']}")
                    resp = self._request("GET", alt['endpoint'], params=alt['params'], headers=alt['headers'])
                    print(f"DEBUG: Alternative {i} succeeded!")
                    return self._parse_dump_response(resp.text)
                except Exception as e2:
                    print(f"DEBUG: Alternative {i} failed: {e2}")
                    continue
            
            print("DEBUG: All dump formats failed, returning empty data")
            return {}

    def _parse_dump_response(self, dump_text: str) -> Dict[str, List[Dict]]:
        """Parse the dump response text into structured data"""
        models = {}
        current_model = None
        current_headers = None
        
        print(f"DEBUG: Parsing dump response, {len(dump_text)} characters")
        
        lines = dump_text.strip().split('\n')
        print(f"DEBUG: Found {len(lines)} lines in dump")
        
        for line_num, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
                
            # Check for model header
            if line.startswith('###model:') and line.endswith('###'):
                current_model = line.replace('###model:', '').replace('###', '').strip()
                models[current_model] = []
                current_headers = None
                print(f"DEBUG: Found model: {current_model}")
                continue
            
            # Skip if no current model
            if current_model is None:
                continue
            
            # Parse CSV data
            if current_headers is None:
                # First line after model header is the headers
                current_headers = [h.strip() for h in line.split(',')]
                print(f"DEBUG: Headers for {current_model}: {current_headers}")
            else:
                # Data rows - handle CSV parsing with potential commas in quoted strings
                values = self._parse_csv_line(line)
                if len(values) == len(current_headers):
                    row_dict = dict(zip(current_headers, values))
                    models[current_model].append(row_dict)
        
        print(f"DEBUG: Parsed models: {list(models.keys())}")
        for model, data in models.items():
            print(f"DEBUG: Model {model} has {len(data)} records")
        
        return models

    def _parse_csv_line(self, line: str) -> List[str]:
        """Parse a CSV line handling quoted strings with commas"""
        import csv
        import io
        
        # Use CSV reader to properly handle quoted fields
        reader = csv.reader(io.StringIO(line))
        try:
            return next(reader)
        except:
            # Fallback to simple split if CSV parsing fails
            return [v.strip() for v in line.split(',')]

    def get_accounts_summary(self) -> Dict:
        """Get summary of accounts with hierarchy"""
        dump_data = self.fetch_dump_data()
        accounts = dump_data.get('account', [])
        
        summary = {
            'total_accounts': len(accounts),
            'by_level': {},
            'top_level': [],
            'all_accounts': {}
        }
        
        for account in accounts:
            account_id = account.get('id', '')
            level = int(account.get('level', 0))
            name = account.get('name', '').strip('"')
            parent_id = account.get('parent_id', '')
            
            # Count by level
            if level not in summary['by_level']:
                summary['by_level'][level] = 0
            summary['by_level'][level] += 1
            
            # Store all accounts
            summary['all_accounts'][account_id] = {
                'name': name,
                'level': level,
                'parent_id': parent_id if parent_id else None
            }
            
            # Top level accounts (level 1)
            if level == 1:
                summary['top_level'].append({
                    'id': account_id,
                    'name': name
                })
        
        return summary

    def get_services_summary(self) -> Dict:
        """Get summary of services"""
        dump_data = self.fetch_dump_data()
        services = dump_data.get('service', [])
        
        summary = {
            'total_services': len(services),
            'all_services': {}
        }
        
        for service in services:
            service_id = service.get('id', '')
            name = service.get('name', '').strip('"')
            
            summary['all_services'][service_id] = {
                'name': name
            }
        
        return summary

    def get_existing_rates_summary(self) -> Dict:
        """Get summary of existing rates"""
        dump_data = self.fetch_dump_data()
        rates = dump_data.get('rate', [])
        
        summary = {
            'total_rates': len(rates),
            'by_account': {},
            'by_service': {},
            'date_range': {'earliest': None, 'latest': None}
        }
        
        for rate in rates:
            account_id = rate.get('account_id', '')
            service_id = rate.get('service_id', '')
            effective_date = rate.get('effective_date', '')
            
            # Count by account
            if account_id not in summary['by_account']:
                summary['by_account'][account_id] = 0
            summary['by_account'][account_id] += 1
            
            # Count by service
            if service_id not in summary['by_service']:
                summary['by_service'][service_id] = 0
            summary['by_service'][service_id] += 1
            
            # Track date range
            if effective_date:
                if summary['date_range']['earliest'] is None or effective_date < summary['date_range']['earliest']:
                    summary['date_range']['earliest'] = effective_date
                if summary['date_range']['latest'] is None or effective_date > summary['date_range']['latest']:
                    summary['date_range']['latest'] = effective_date
        
        return summary

    def validate_csv_against_system(self, csv_data: List[Dict]) -> Dict:
        """Validate CSV data against actual system accounts and services using dump data"""
        print("🔍 Validating CSV data against system...")
        
        # Fetch dump data once for all validations
        dump_data = self.fetch_dump_data()
        
        # Build lookup dictionaries for fast validation
        accounts_lookup = {account.get('id', ''): account for account in dump_data.get('account', [])}
        services_lookup = {service.get('id', ''): service for service in dump_data.get('service', [])}
        
        # Build existing rates lookup for duplicate checking
        existing_rates = set()
        for rate in dump_data.get('rate', []):
            account_id = rate.get('account_id', '')
            service_id = rate.get('service_id', '')
            effective_date = rate.get('effective_date', '')
            existing_rates.add((account_id, service_id, effective_date))
        
        validation_results = {
            'valid_rows': [],
            'invalid_accounts': [],
            'invalid_services': [],
            'missing_fields': [],
            'duplicate_rates': [],
            'warnings': []
        }
        
        print(f"📊 System data loaded:")
        print(f"   • {len(accounts_lookup)} accounts")
        print(f"   • {len(services_lookup)} services") 
        print(f"   • {len(existing_rates)} existing rates")
        
        for i, row in enumerate(csv_data):
            row_num = i + 2  # Account for header row
            account_id = str(row.get('account_id', '')).strip()
            service_id = str(row.get('service_id', '')).strip()
            effective_date = str(row.get('revision_start_date', '')).strip()
            
            # Check required fields
            if not account_id or not service_id or not effective_date:
                validation_results['missing_fields'].append({
                    'row': row_num,
                    'missing': [k for k, v in {'account_id': account_id, 'service_id': service_id, 'revision_start_date': effective_date}.items() if not v]
                })
                continue
            
            # Validate account exists
            if account_id not in accounts_lookup:
                validation_results['invalid_accounts'].append({
                    'row': row_num,
                    'account_id': account_id
                })
                continue
            
            # Validate service exists
            if service_id not in services_lookup:
                validation_results['invalid_services'].append({
                    'row': row_num,
                    'service_id': service_id
                })
                continue
            
            # Convert date format for comparison
            if len(effective_date) == 8 and effective_date.isdigit():
                formatted_date = f"{effective_date[:4]}-{effective_date[4:6]}-{effective_date[6:8]}"
            else:
                formatted_date = effective_date
            
            # Check if rate already exists using fast lookup
            if (account_id, service_id, formatted_date) in existing_rates:
                validation_results['duplicate_rates'].append({
                    'row': row_num,
                    'account_id': account_id,
                    'service_id': service_id,
                    'effective_date': effective_date
                })
            
            validation_results['valid_rows'].append(row_num)
        
        return validation_results

    def show_system_overview(self):
        """Display comprehensive system overview"""
        print("📊 System Overview")
        print("=" * 50)
        
        try:
            # Get summaries
            accounts = self.get_accounts_summary()
            services = self.get_services_summary()
            rates = self.get_existing_rates_summary()
            
            # Accounts overview
            print(f"👥 Accounts: {accounts['total_accounts']} total")
            for level, count in sorted(accounts['by_level'].items()):
                print(f"   Level {level}: {count} accounts")
            
            print(f"\n🏢 Top-level accounts:")
            for account in accounts['top_level'][:10]:  # Show first 10
                print(f"   • {account['name']} (ID: {account['id']})")
            if len(accounts['top_level']) > 10:
                print(f"   ... and {len(accounts['top_level']) - 10} more")
            
            # Services overview
            print(f"\n⚙️  Services: {services['total_services']} total")
            service_list = list(services['all_services'].items())[:10]
            for service_id, service_info in service_list:
                print(f"   • {service_info['name']} (ID: {service_id})")
            if len(services['all_services']) > 10:
                print(f"   ... and {len(services['all_services']) - 10} more")
            
            # Rates overview
            print(f"\n💰 Rates: {rates['total_rates']} total")
            if rates['date_range']['earliest'] and rates['date_range']['latest']:
                print(f"   Date range: {rates['date_range']['earliest']} to {rates['date_range']['latest']}")
            
            # Top accounts by rate count
            if rates['by_account']:
                top_accounts = sorted(rates['by_account'].items(), key=lambda x: x[1], reverse=True)[:5]
                print(f"\n📈 Accounts with most rates:")
                for account_id, rate_count in top_accounts:
                    account_name = accounts['all_accounts'].get(account_id, {}).get('name', 'Unknown')
                    print(f"   • {account_name} (ID: {account_id}): {rate_count} rates")
            
        except Exception as e:
            print(f"❌ Error generating system overview: {e}")
