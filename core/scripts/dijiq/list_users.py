#!/usr/bin/env python3
import os
import requests
import json
from typing import Dict, Any, List, Optional
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
    
    def get_users(self) -> List[Dict[str, Any]]:
        """
        Retrieve all users from the API.
        
        Returns:
            List of user dictionaries or the raw response text if not JSON
            
        Raises:
            Exception: If the API request fails
        """
        try:
            response = requests.get(self.users_endpoint, headers=self.headers)
            response.raise_for_status()
            
            try:
                return response.json()
            except json.JSONDecodeError:
                return response.text
                
        except requests.exceptions.RequestException as e:
            raise Exception(f"Error fetching users: {e}")

def list_users() -> List[Dict[str, Any]]:
    """
    Get a list of all users using the API.
    
    Returns:
        List of user dictionaries
    
    Raises:
        Exception: If the API request fails
    """
    try:
        client = APIClient()
        return client.get_users()
    except Exception as e:
        raise Exception(f"Failed to list users: {str(e)}")

def main() -> None:
    """Main function for command-line usage"""
    try:
        users = list_users()
        
        if isinstance(users, list):
            print(json.dumps(users, indent=4))
        else:
            print(users)
            
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    import sys
    main()