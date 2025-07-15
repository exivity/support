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
            
            self._request("POST", "/v2/", json=payload, headers=headers)
            return  # Success - no debug output needed
            
        except Exception as e:
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
            
            self._request("POST", "/v1/rates", json=payload_v1, headers=headers_v1)
            return
            
        except Exception as e:
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
            
            self._request("POST", "/v2/rates", json=payload_simple, headers=headers_simple)
            return
            
        except Exception as e:
            last_error = e
        
        # If all approaches fail, show debug info and raise the last exception
        print(f"DEBUG: All rate creation approaches failed for account {account_id}, service {service_id}")
        print(f"DEBUG: v2 atomic failed: {last_error}")
        raise Exception(f"All rate creation approaches failed for account {account_id}, service {service_id}. Last error: {last_error}")

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

    def create_list_price_revision(self, service_id: int, rate: float, cogs: float, effective_date: str):
        """Create single list price revision (default rate with no account)"""
        # Convert date format from YYYYMMDD to YYYY-MM-DD for API
        if len(effective_date) == 8 and effective_date.isdigit():
            formatted_date = f"{effective_date[:4]}-{effective_date[4:6]}-{effective_date[6:8]}"
        else:
            formatted_date = effective_date
        
        # Use v2 atomic operations for list price creation
        operation = {
            "op": "add",
            "data": {
                "type": "rate",
                "attributes": {
                    "rate": rate,
                    "rate_col": None,
                    "min_commit": 0,  # List prices typically have min_commit = 0
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
                    "account": {"data": None},  # No account = list price
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
        
        self._request("POST", "/v2/", json=payload, headers=headers)

    def create_list_price_revisions_batch(self, rate_data: List[Dict]) -> Dict:
        """Create multiple list price revisions using atomic operations"""
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
                        "min_commit": 0,  # List prices typically have min_commit = 0
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
                        "account": {"data": None},  # No account = list price
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
        """Create workflow with all steps using atomic operations matching GUI format exactly"""
        operations = []
        
        # Create workflow operation with steps and schedules relationships
        workflow_lid = str(uuid.uuid4())
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
        
        # Create step operations with correct structure matching GUI exactly
        step_lids = []
        for i, step in enumerate(steps):
            step_lid = str(uuid.uuid4())
            step_lids.append(step_lid)
            
            # Build step attributes based on type
            step_type = step.get("type")
            step_attrs = step.get("attributes", {})
            
            # Create proper step structure matching GUI exactly
            step_data = {
                "type": "workflowstep",
                "attributes": {
                    "step_type": step_type,
                    "options": {},
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
                        "data": None if i == 0 else {
                            "lid": step_lids[i-1],
                            "type": "workflowstep"
                        }
                    }
                },
                "lid": step_lid
            }
            
            # Set step-specific options - match GUI format exactly
            if step_type == "extract":
                step_data["attributes"]["options"] = {
                    "script": step_attrs.get("script", ""),
                    "from_date_offset": step_attrs.get("from_date_offset", 0),
                    "to_date_offset": step_attrs.get("to_date_offset", 0)
                }
                
                # Add arguments if provided
                if step_attrs.get("arguments"):
                    step_data["attributes"]["options"]["arguments"] = step_attrs["arguments"]
                
                # Only add environment_id if it's not the default environment (1)
                # GUI doesn't include environment_id for default environment
                if step_attrs.get("environment_id") and step_attrs.get("environment_id") != 1:
                    step_data["attributes"]["options"]["environment_id"] = step_attrs["environment_id"]
                    
            elif step_type == "transform":
                step_data["attributes"]["options"] = {
                    "script": step_attrs.get("script", ""),
                    "from_date_offset": step_attrs.get("from_date_offset", 0),
                    "to_date_offset": step_attrs.get("to_date_offset", 0)
                }
                
                # Only add environment_id if it's not the default environment (1)
                # GUI doesn't include environment_id for default environment
                if step_attrs.get("environment_id") and step_attrs.get("environment_id") != 1:
                    step_data["attributes"]["options"]["environment_id"] = step_attrs["environment_id"]
                    
            elif step_type == "prepare_report":
                step_data["attributes"]["options"] = {
                    "report_id": step_attrs.get("report_id", 0),
                    "from_date_offset": step_attrs.get("from_date_offset", 0),
                    "to_date_offset": step_attrs.get("to_date_offset", 0)
                }
            
            operations.append({
                "op": "add",
                "data": step_data
            })
        
        # Execute atomic operations
        payload = {
            "atomic:operations": operations
        }
        
        # Set proper headers to match GUI
        headers = {
            "Content-Type": "application/vnd.api+json;ext=\"https://jsonapi.org/ext/atomic\"",
            "Accept": "application/vnd.api+json"
        }
        
        try:
            resp = self._request("POST", "/v2/", json=payload, headers=headers)
            results = resp.json().get("atomic:results", [])
            
            if results and len(results) > 0:
                workflow_data = results[0].get("data", {})
                workflow_id = workflow_data.get("id", "")
                
                if workflow_id:
                    return workflow_id
                else:
                    raise Exception("No workflow ID returned from atomic operation")
            else:
                raise Exception("No results returned from atomic operation")
                
        except Exception as e:
            raise

    def get_available_scripts(self) -> Dict[str, List[str]]:
        """Get available extract and transform scripts from v2 endpoints"""
        try:
            scripts = {
                "extract": [],
                "transform": []
            }
            
            # Get extractors
            try:
                resp = self._request("GET", "/v2/extractors")
                extractors = resp.json().get("data", [])
                scripts["extract"] = [
                    extractor.get("attributes", {}).get("name", "")
                    for extractor in extractors
                    if extractor.get("attributes", {}).get("name")
                ]
            except Exception as e:
                print(f"   ⚠️  Error fetching extractors: {e}")
            
            # Get transformers
            try:
                resp = self._request("GET", "/v2/transformers")
                transformers = resp.json().get("data", [])
                scripts["transform"] = [
                    transformer.get("attributes", {}).get("name", "")
                    for transformer in transformers
                    if transformer.get("attributes", {}).get("name")
                ]
            except Exception as e:
                print(f"   ⚠️  Error fetching transformers: {e}")
            
            return scripts
            
        except Exception as e:
            print(f"   ⚠️  Error loading scripts: {e}")
            return {"extract": [], "transform": []}

    def get_available_reports(self) -> List[Dict[str, str]]:
        """Get available report definitions from v2 endpoint"""
        try:
            resp = self._request("GET", "/v2/reportdefinitions")
            reports = resp.json().get("data", [])
            
            report_list = []
            for report in reports:
                attributes = report.get("attributes", {})
                report_info = {
                    "id": report.get("id", ""),
                    "name": attributes.get("name", ""),
                    "description": attributes.get("description", "")
                }
                if report_info["id"] and report_info["name"]:
                    report_list.append(report_info)
            
            return report_list
            
        except Exception as e:
            print(f"   ⚠️  Error loading reports: {e}")
            return []

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
        """Fetch comprehensive dump data including accounts, services, rates, and rate tiers"""
        try:
            # Include ratetier model to detect services with rate tiers
            params = {
                "models": "account,adjustment,adjustables,metadata,rate,ratetier,reportdefinition,service,servicecategory",
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
            
            # Try alternative formats - all using v1/dump/data
            alternatives = [
                {
                    "endpoint": "/v1/dump/data",
                    "params": {"models": "account,rate,ratetier,service", "progress": "0"},
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
                }
            ]
            
            for i, alt in enumerate(alternatives, 1):
                try:
                    resp = self._request("GET", alt['endpoint'], params=alt['params'], headers=alt['headers'])
                    return self._parse_dump_response(resp.text)
                except Exception as e2:
                    continue
            
            return {}

    def _parse_dump_response(self, dump_text: str) -> Dict[str, List[Dict]]:
        """Parse the dump response text into structured data"""
        models = {}
        current_model = None
        current_headers = None
        
        lines = dump_text.strip().split('\n')
        
        for line_num, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
                
            # Check for model header
            if line.startswith('###model:') and line.endswith('###'):
                current_model = line.replace('###model:', '').replace('###', '').strip()
                models[current_model] = []
                current_headers = None
                continue
            
            # Skip if no current model
            if current_model is None:
                continue
            
            # Parse CSV data
            if current_headers is None:
                # First line after model header is the headers
                current_headers = [h.strip() for h in line.split(',')]
            else:
                # Data rows - handle CSV parsing with potential commas in quoted strings
                values = self._parse_csv_line(line)
                if len(values) == len(current_headers):
                    row_dict = dict(zip(current_headers, values))
                    models[current_model].append(row_dict)
        
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
