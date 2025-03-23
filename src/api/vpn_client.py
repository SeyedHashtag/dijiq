import requests
import json
import logging
from typing import Dict, Any, Optional
from src.models.user import VpnUser

# Configure logger
logger = logging.getLogger(__name__)

class VpnApiClient:
    def __init__(self, base_url: str, api_key: Optional[str] = None):
        """
        Initialize the VPN API client.
        
        Args:
            base_url: Base URL of the API
            api_key: API key or token for authentication
        """
        # Ensure base URL ends with a slash
        if not base_url.endswith('/'):
            base_url += '/'
            
        self.base_url = base_url
        self.api_key = api_key
        
        # Define API endpoints
        self.users_endpoint = f"{self.base_url}api/v1/users/"
        
        # Set default headers
        self.headers = {
            'accept': 'application/json',
            'Content-Type': 'application/json'
        }
        
        # Add authorization if token is provided
        if api_key:
            self.headers['Authorization'] = api_key
    
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
        # Prepare the data payload - Include password in the request
        data = {
            "username": user.username,
            "traffic_limit": user.traffic_limit,
            "expiration_days": user.expiration_days,
            "password": user.password  # Include password in the request
        }
        
        logger.info(f"Sending request to: {self.users_endpoint}")
        logger.debug(f"Request payload: {data}")
        
        try:
            # Send the POST request
            response = requests.post(
                self.users_endpoint,
                headers=self.headers,
                json=data
            )
            
            logger.debug(f"API Response Status: {response.status_code}")
            logger.debug(f"API Response Body: {response.text[:200]}...")
            
            # Raise for HTTP errors
            response.raise_for_status()
            
            # Check if response has content before parsing JSON
            if response.text.strip():
                try:
                    return response.json()
                except json.JSONDecodeError as json_err:
                    logger.error(f"Failed to parse JSON response: {str(json_err)}")
                    logger.error(f"Response content: {response.text}")
                    return {"detail": f"Request succeeded but returned non-JSON response", "raw_response": response.text[:100]}
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
