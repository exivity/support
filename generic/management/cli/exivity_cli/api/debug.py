"""
Debug module to test API endpoints and understand what works on your Exivity server
"""

import json
import requests
from typing import Dict, Any


def test_environment_creation(api, env_name: str = "TEST_ENV"):
    """Test environment creation with different approaches"""
    print(f"🧪 Testing environment creation for '{env_name}'...")
    
    # Test approaches using the SAME validated methods as the main system
    approaches = [
        {
            "name": "Standard API (main system method)",
            "test_func": lambda name: api.create_environment(name)
        },
        {
            "name": "With variables (main system method)",
            "test_func": lambda name: api.create_environment_with_variables(name + "_with_var", {"test_var": "test_value"})
        }
    ]
    
    for i, approach in enumerate(approaches, 1):
        try:
            print(f"\n🔬 Test {i}: {approach['name']}")
            
            # Use the same methods as the main system
            env_id = approach['test_func'](env_name if i == 1 else env_name)
            
            print(f"   ✅ Success! Environment ID: {env_id}")
            
            # Clean up - try to delete the test environment
            if env_id:
                try:
                    api.delete_environment(env_id)
                    print(f"   🧹 Cleaned up test environment (ID: {env_id})")
                except Exception as cleanup_e:
                    if "default environment" in str(cleanup_e).lower():
                        print(f"   🛡️  Cannot delete test environment (ID: {env_id}) - it's the default environment")
                    else:
                        print(f"   ⚠️  Could not clean up test environment (ID: {env_id}): {cleanup_e}")
            
            return True
            
        except Exception as e:
            print(f"   ❌ Failed: {e}")
            if hasattr(e, 'response') and e.response:
                try:
                    error_details = e.response.json()
                    print(f"   📋 Error details: {json.dumps(error_details, indent=2)}")
                except:
                    print(f"   📋 Error text: {e.response.text}")
    
    return False


def test_api_endpoints(api):
    """Test various API endpoints to see what's available"""
    print("🔍 Testing API endpoints availability...")
    
    endpoints_to_test = [
        ("/", "GET", "Root"),
        ("/v1", "GET", "API v1 root"),
        ("/v2", "GET", "API v2 root"),
        ("/v1/environments", "GET", "v1 environments list"),
        ("/v2/environments", "GET", "v2 environments list"),
        ("/v1/workflows", "GET", "v1 workflows list"),
        ("/v2/workflows", "GET", "v2 workflows list"),
        ("/v1/rates", "GET", "v1 rates list"),
        ("/v2/rates", "GET", "v2 rates list"),
    ]
    
    for endpoint, method, description in endpoints_to_test:
        try:
            resp = api._request(method, endpoint)
            print(f"   ✅ {description} ({method} {endpoint}): {resp.status_code}")
            
            # Show some data if it's a list endpoint
            if method == "GET" and resp.status_code == 200:
                try:
                    data = resp.json()
                    if isinstance(data, dict) and "data" in data:
                        count = len(data["data"]) if isinstance(data["data"], list) else 1
                        print(f"      📊 Found {count} items")
                except:
                    pass
                    
        except Exception as e:
            print(f"   ❌ {description} ({method} {endpoint}): {e}")


def test_dump_endpoint(api):
    """Test dump endpoint with different parameter formats"""
    print("🔍 Testing dump endpoint formats...")
    
    dump_formats = [
        {
            "endpoint": "/v1/dump/data",
            "params": {"models": "account,service,rate", "progress": "0"},
            "headers": {"Accept": "text/csv"},
            "description": "v1/dump/data with CSV accept header"
        },
        {
            "endpoint": "/v1/dump/data",
            "params": {"models": "account,service,rate"},
            "headers": {"Accept": "text/csv"},
            "description": "v1/dump/data without progress"
        },
        {
            "endpoint": "/v1/dump/data",
            "params": {"models": "account", "progress": "0"},
            "headers": {"Accept": "text/csv"},
            "description": "v1/dump/data single model"
        },
        {
            "endpoint": "/v2/dump",
            "params": {"data": "account,service,rate", "progress": "0"},
            "headers": {"Accept": "text/csv"},
            "description": "v2/dump with CSV accept"
        },
        {
            "endpoint": "/v1/dump/data",
            "params": {"models": "account,service,rate", "progress": "0"},
            "headers": {},
            "description": "v1/dump/data without accept header"
        }
    ]
    
    for i, format_info in enumerate(dump_formats, 1):
        try:
            endpoint = format_info["endpoint"]
            params = format_info["params"]
            headers = format_info["headers"]
            description = format_info["description"]
            
            print(f"\n🔬 Test {i}: {description}")
            print(f"   URL: {endpoint}")
            print(f"   Params: {params}")
            print(f"   Headers: {headers}")
            
            resp = api._request("GET", endpoint, params=params, headers=headers)
            
            if resp.status_code == 200:
                content = resp.text[:500]  # Show first 500 chars
                print(f"   ✅ Success! Response preview:")
                print(f"   {content}...")
                
                # Count lines and models
                lines = resp.text.split('\n')
                model_count = len([line for line in lines if line.startswith('###model:')])
                print(f"   📊 Found {len(lines)} lines, {model_count} models")
                
                # Show content type
                content_type = resp.headers.get('Content-Type', 'Unknown')
                print(f"   📄 Content-Type: {content_type}")
                
                return True
            else:
                print(f"   ⚠️  Unexpected status: {resp.status_code}")
                
        except Exception as e:
            print(f"   ❌ Failed: {e}")
    
    return False


def debug_session(api):
    """Run a complete debug session"""
    print("🚀 Starting Exivity API Debug Session")
    print("=" * 50)
    
    # Test general API endpoints
    test_api_endpoints(api)
    
    print("\n" + "=" * 50)
    
    # Test dump endpoint
    test_dump_endpoint(api)
    
    print("\n" + "=" * 50)
    
    # Test environment creation
    test_environment_creation(api)
    
    print("\n" + "=" * 50)
    print("🏁 Debug session complete!")
