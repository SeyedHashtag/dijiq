import requests
from typing import Dict, Any, Optional
from src.models.user import VpnUser


class VpnApiClient:
    def __init__(self, base_url: str, auth_token: Optional[str] = None):
        self.base_url = base_url.rstrip('/')
        self.headers = {"Content-Type": "application/json"}
        
        if auth_token:
            self.headers["Authorization"] = f"Bearer {auth_token}"
    
    def add_user(self, user: VpnUser) -> Dict[str, Any]:
        """
        Add a new VPN user via the API.
        
        Args:
            user: VpnUser object containing user details
            
        Returns:
            API response as dictionary
            
        Raises:
            Exception: If API call fails
        """
        url = f"{self.base_url}/users/"  # Adjust endpoint as needed
        
        try:
            response = requests.post(url, json=user.to_dict(), headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            # Log the error or handle it appropriately
            raise Exception(f"Failed to add user: {str(e)}")
