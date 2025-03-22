import requests
import logging
from typing import Dict, Any, Optional, Union
from src.models.user import VpnUser

# Configure logger
logger = logging.getLogger(__name__)

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
        # Ensure the endpoint has the correct format - may need adjustment based on your API
        endpoint = "/users/"
        if not endpoint.startswith('/'):
            endpoint = '/' + endpoint
        
        url = f"{self.base_url}{endpoint}"
        
        logger.info(f"Sending request to: {url}")
        logger.debug(f"Request payload: {user.to_dict()}")
        
        try:
            response = requests.post(url, json=user.to_dict(), headers=self.headers)
            logger.debug(f"Response status code: {response.status_code}")
            logger.debug(f"Response content: {response.text[:200]}...")  # Log first 200 chars of response
            
            # Raise for HTTP errors
            response.raise_for_status()
            
            # Check if response has content before parsing JSON
            if response.text.strip():
                try:
                    return response.json()
                except ValueError as json_err:
                    logger.error(f"Failed to parse JSON response: {str(json_err)}")
                    logger.error(f"Response content: {response.text}")
                    return {"detail": f"Request succeeded but returned non-JSON response: {response.text[:100]}..."}
            else:
                # Empty response but status code was ok
                return {"detail": f"User {user.username} was added successfully"}
                
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response status code: {e.response.status_code}")
                logger.error(f"Response content: {e.response.text}")
                error_msg = f"API error: {e.response.status_code} - {e.response.text}"
            else:
                error_msg = f"Connection error: {str(e)}"
            
            raise Exception(f"Failed to add user: {error_msg}")
