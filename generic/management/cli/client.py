"""
Exivity API Client

Handles authentication and basic API operations.
"""

import warnings
from typing import Dict, List

import requests
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
        """Make an authenticated request to the API"""
        url = f"{self.base_url}{endpoint}"
        if 'verify' not in kwargs:
            kwargs['verify'] = self.verify_ssl
        resp = self.session.request(method, url, **kwargs)
        if resp.status_code == 401:
            raise RuntimeError("Unauthorized. Token may have expired. Re-authenticate.")
        resp.raise_for_status()
        return resp
