#!/usr/bin/env python3
import os
import requests
import json
from datetime import datetime
from typing import Optional, Union, Tuple, Dict, Any
import re

class UserError(Exception):
    """Base exception for user-related errors"""
    pass

class APIClient:
    def __init__(self, base_url: Optional[str] = None, token: Optional[str] = None):
        """
        Initialize the API client.
        
        Args:
            base_url: Optional base URL for the API
            token: Optional authentication token
        """
        if base_url is None:
            base_url = os.getenv('URL')
        if token is None:
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
    
    def get_users(self) -> Dict[str, Any]:
        """
        Retrieve all users from the API.
        
        Returns:
            Dictionary of user data
        
        Raises:
            UserError: If API call fails
        """
        try:
            response = requests.get(self.users_endpoint, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise UserError(f"Error fetching users: {e}")
    
    def get_user(self, username: str) -> Dict[str, Any]:
        """
        Retrieve a specific user from the API.
        
        Args:
            username: Username to retrieve
            
        Returns:
            User data dictionary
            
        Raises:
            UserError: If API call fails or user doesn't exist
        """
        try:
            response = requests.get(f"{self.users_endpoint}{username}", headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise UserError(f"Error fetching user '{username}': {e}")
    
    def add_user(
        self, 
        username: str, 
        traffic_limit: Union[int, float, str], 
        expiration_days: Union[int, str],
        password: Optional[str] = None, 
        creation_date: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Add a new user via the API.
        
        Args:
            username: Username for the new user
            traffic_limit: Traffic limit in GB
            expiration_days: Number of days until expiration
            password: Optional password (generated if not provided)
            creation_date: Optional account creation date (uses current date if not provided)
            
        Returns:
            Tuple of (success: bool, message: str)
        """
        # Validate username format
        if not self._validate_username(username):
            return False, "Error: Username can only contain letters and numbers."
        
        # Validate date format if provided
        if creation_date and not self._validate_date_format(creation_date):
            return False, "Invalid date. Please provide a valid date in YYYY-MM-DD format."
        
        # Prepare request data
        data = {
            "username": username,
            "traffic_limit": traffic_limit,
            "expiration_days": expiration_days
        }
        
        # Add optional parameters if provided
        if password:
            data["password"] = password
        if creation_date:
            data["creation_date"] = creation_date
        
        try:
            response = requests.post(
                self.users_endpoint, 
                headers=self.headers, 
                json=data
            )
            
            response.raise_for_status()
            result = response.json()
            
            return True, f"User {username} added successfully."
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 400:
                try:
                    error_data = e.response.json()
                    return False, error_data.get("detail", str(e))
                except (ValueError, json.JSONDecodeError):
                    return False, f"Error: {str(e)}"
            return False, f"Error: {str(e)}"
        except requests.exceptions.RequestException as e:
            return False, f"Error adding user: {str(e)}"
    
    def _validate_username(self, username: str) -> bool:
        """
        Validates that username only contains letters and numbers.
        
        Args:
            username: Username to validate
            
        Returns:
            True if valid, False otherwise
        """
        return bool(re.match(r'^[a-zA-Z0-9]+$', username))
    
    def _validate_date_format(self, date_str: str) -> bool:
        """
        Validates that the date string is in YYYY-MM-DD format and is a valid date.
        
        Args:
            date_str: Date string to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not re.match(r'^[0-9]{4}-[0-9]{2}-[0-9]{2}$', date_str):
            return False
        
        try:
            datetime.strptime(date_str, '%Y-%m-%d')
            return True
        except ValueError:
            return False

def add_user(
    username: str, 
    traffic_limit: Union[int, float, str], 
    expiration_days: Union[int, str],
    password: Optional[str] = None, 
    creation_date: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Add a new user to the system using the API.
    
    Args:
        username: Username for the new user
        traffic_limit: Traffic limit in GB
        expiration_days: Number of days until expiration
        password: Optional password (generated if not provided)
        creation_date: Optional account creation date (uses current date if not provided)
        
    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        client = APIClient()
        return client.add_user(username, traffic_limit, expiration_days, password, creation_date)
    except Exception as e:
        return False, f"Error: {str(e)}"

def main() -> None:
    """
    Main function to run the script directly from command line.
    """
    import sys
    
    if len(sys.argv) < 4 or len(sys.argv) > 6:
        print("Usage: add_user.py <username> <traffic_limit_GB> <expiration_days> [password] [creation_date]")
        sys.exit(1)
    
    username = sys.argv[1]
    traffic_limit = sys.argv[2]
    expiration_days = sys.argv[3]
    password = sys.argv[4] if len(sys.argv) > 4 else None
    creation_date = sys.argv[5] if len(sys.argv) > 5 else None
    
    success, message = add_user(
        username, traffic_limit, expiration_days, password, creation_date
    )
    
    print(message)
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()