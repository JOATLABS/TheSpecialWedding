import requests
from typing import Optional, Dict, Any
import json

class ApiClient:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()
        self.token = None
    
    def login(self, email: str, password: str) -> bool:
        """Login and store JWT token"""
        try:
            response = self.session.post(
                f"{self.base_url}/admin/token",
                json={"email": email, "password": password}
            )
            if response.status_code == 200:
                data = response.json()
                self.token = data["access_token"]
                self.session.headers.update({"Authorization": f"Bearer {self.token}"})
                return True
            return False
        except Exception:
            return False
    
    def health_check(self) -> Dict[str, Any]:
        response = self.session.get(f"{self.base_url}/health/")
        return response.json()
    
    def import_guests_csv(self, file_path: str, wedding_id: str = "wedding1") -> Dict[str, Any]:
        with open(file_path, 'rb') as f:
            files = {'file': f}
            params = {'wedding_id': wedding_id}
            response = self.session.post(f"{self.base_url}/admin/guests/import", files=files, params=params)
            if response.status_code == 200:
                return response.json()
            else:
                raise Exception(f"Error importing guests: {response.text}")
    
    def get_all_rsvps(self) -> Dict[str, Any]:
        response = self.session.get(f"{self.base_url}/admin/rsvps")
        return response.json()

    def export_rsvps(self) -> bytes:
        response = self.session.get(f"{self.base_url}/admin/rsvps/export")
        return response.content
    
    def get_guest_details(self, token: str) -> Dict[str, Any]:
        response = self.session.get(f"{self.base_url}/guest/{token}")
        return response.json()