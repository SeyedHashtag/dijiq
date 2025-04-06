#!/usr/bin/env python3
import os
import requests
import json
import argparse
from typing import Dict, Any, Optional
from dotenv import load_dotenv

class APIClient:
    def __init__(self, base_url: Optional[str] = None, token: Optional[str] = None):
        """
        Initialize the API client.
        
        Args:
            base_url: Optional base URL for the API
            token: Optional authentication token
        """
        if base_url is None:
            load_dotenv()
            base_url = os.getenv('URL')
        if token is None:
            load_dotenv()
            token = os.getenv('TOKEN')
            
        if not base_url:
            raise ValueError("Base URL must be provided either as an argument or via URL environment variable")
        if not token:
            raise ValueError("API token must be provided either as an argument or via TOKEN environment variable")
        
        if not base_url.endswith('/'):
            base_url += '/'
            
        self.base_url = base_url
        self.token = token
        self.users_endpoint = f"{self.base_url}api/v1/users/"
        
        self.headers = {
            'accept': 'application/json',
            'Authorization': self.token,
            'Content-Type': 'application/json'
        }
    
    def get_user(self, username: str) -> Dict[str, Any]:
        """
        Retrieve a specific user from the API.
        
        Args:
            username: Username of the user to retrieve
            
        Returns:
            User data dictionary
            
        Raises:
            Exception: If the API request fails
        """
        try:
            response = requests.get(f"{self.users_endpoint}{username}", headers=self.headers)
            response.raise_for_status()
            
            try:
                return response.json()
            except json.JSONDecodeError:
                raise Exception(f"Invalid response format: {response.text}")
                
        except requests.exceptions.RequestException as e:
            if hasattr(e, 'response') and e.response is not None:
                if e.response.status_code == 404:
                    raise Exception(f"User '{username}' not found")
                try:
                    error_data = e.response.json()
                    error_message = error_data.get('detail', str(e))
                    raise Exception(f"API error: {error_message}")
                except json.JSONDecodeError:
                    pass
            raise Exception(f"Error fetching user: {e}")

def get_user(username: str) -> Dict[str, Any]:
    """
    Get information about a specific user using the API.
    
    Args:
        username: Username to retrieve
        
    Returns:
        User data dictionary
        
    Raises:
        Exception: If the API request fails
    """
    try:
        client = APIClient()
        return client.get_user(username)
    except Exception as e:
        raise Exception(f"Failed to get user: {str(e)}")

def main() -> None:
    """Main function for command-line usage"""
    parser = argparse.ArgumentParser(description='Get information about a specific user')
    parser.add_argument('-u', '--username', required=True, help='Username to retrieve')
    
    try:
        args = parser.parse_args()
        user_data = get_user(args.username)
        print(json.dumps(user_data, indent=4))
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    import sys
    main()