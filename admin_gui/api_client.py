import requests
from typing import Optional, Dict, Any, Union
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class ApiClient:
    def __init__(self, base_url: str = None):
        # In Docker networking, 'api' is the service name defined in docker-compose.all.yml
        if base_url is None:
            base_url = "http://api:8000" if os.environ.get("DOCKER_ENV") == "true" else "http://localhost:8000"
        """Initialize the API client with the base URL and optional auth credentials"""
        self.base_url = base_url
        self.session = requests.Session()
        self.email = None
        self.password = None
        
        # Try to load credentials from environment
        self.email = os.getenv("PRIMARY_ADMIN_EMAIL")
        self.password = os.getenv("PRIMARY_ADMIN_PASSWORD")
    
    def login(self, email: str, password: str) -> bool:
        """Set basic auth credentials and verify they work"""
        try:
            self.email = email
            self.password = password
            
            # Test the credentials with a simple API call
            response = self.session.get(
                f"{self.base_url}/admin/rsvps",
                auth=(self.email, self.password)
            )
            
            return response.status_code == 200
        except Exception as e:
            print(f"Login error: {str(e)}")
            return False
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Make an authenticated request to the API"""
        url = f"{self.base_url}/{endpoint.lstrip('/')}" 
        
        # Add auth if we have credentials
        if self.email and self.password and 'auth' not in kwargs:
            kwargs['auth'] = (self.email, self.password)
            
        return self.session.request(method, url, **kwargs)
    
    def health_check(self) -> Dict[str, Any]:
        """Check the API health status"""
        response = self._make_request('GET', '/health/')
        return response.json()
    
    def import_guests_csv(self, file_path: str, wedding_id: str = "wedding1") -> Dict[str, Any]:
        """Import guests from a CSV file"""
        with open(file_path, 'rb') as f:
            files = {'file': f}
            params = {'wedding_id': wedding_id}
            response = self._make_request(
                'POST', 
                '/admin/guests/import', 
                files=files, 
                params=params
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                raise Exception(f"Error importing guests: {response.text}")
    
    def get_all_rsvps(self) -> Union[Dict[str, Any], list]:
        """Get all RSVPs from the API"""
        response = self._make_request('GET', '/admin/rsvps')
        if response.status_code == 200:
            return response.json()
        return []

    def export_rsvps(self) -> bytes:
        """Export RSVPs to CSV format"""
        response = self._make_request('GET', '/admin/rsvps/export')
        if response.status_code == 200:
            return response.content
        return b""
    
    def get_guest_details(self, token: str) -> Dict[str, Any]:
        """Get details for a specific guest by token"""
        params = {'wedding_id': 'wedding1'}  # Default wedding ID
        response = self._make_request(
            'GET', 
            f'/guest/invite/{token}',
            params=params
        )
        if response.status_code == 200:
            return response.json()
        return {}