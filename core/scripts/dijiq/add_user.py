#!/usr/bin/env python3
import os
import requests
import json
import random
import string
import sys
from typing import Dict, Any, Optional, Union, Tuple
from dotenv import load_dotenv

class APIClient:
    def __init__(self, base_url: Optional[str] = None, token: Optional[str] = None):
        """
        Initialize the API client.
        
        Args:
            base_url: Base URL for the API (will use URL env var if not provided)
            token: Authentication token (will use TOKEN env var if not provided)
        """
        if base_url is None or token is None:
            load_dotenv()
            
        self.base_url = base_url or os.getenv('URL')
        self.token = token or os.getenv('TOKEN')
        
        if not self.base_url:
            raise ValueError("API URL is required. Set URL environment variable or pass base_url")
        
        if not self.token:
            raise ValueError("API token is required. Set TOKEN environment variable or pass token")
        
        if not self.base_url.endswith('/'):
            self.base_url += '/'
            
        self.users_endpoint = f"{self.base_url}api/v1/users/"
        
        self.headers = {
            'accept': 'application/json',
            'Authorization': self.token
        }
    
    def get_users(self):
        """Get all users from the API"""
        try:
            response = requests.get(self.users_endpoint, headers=self.headers)
            response.raise_for_status()
            
            try:
                return response.json()
            except json.JSONDecodeError:
                return response.text
        except requests.exceptions.RequestException as e:
            print(f"Error fetching users: {e}", file=sys.stderr)
            return None
    
    def get_user(self, username: str):
        """Get a specific user by username"""
        try:
            user_url = f"{self.users_endpoint}{username}"
            response = requests.get(user_url, headers=self.headers)
            response.raise_for_status()
            
            try:
                return response.json()
            except json.JSONDecodeError:
                return response.text
        except requests.exceptions.RequestException as e:
            print(f"Error fetching user {username}: {e}", file=sys.stderr)
            return None
    
    def add_user(self, username: str, traffic_limit: int, expiration_days: int, 
                 password: Optional[str] = None, creation_date: Optional[str] = None) -> Tuple[bool, str]:
        """
        Add a new user via the API
        
        Args:
            username: Username for the new user
            traffic_limit: Traffic limit in GB
            expiration_days: Number of days until expiration
            password: Optional password (will be generated by API if not provided)
            creation_date: Optional creation date (will use current date if not provided)
            
        Returns:
            Tuple of (success: bool, message: str)
        """
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
        
        post_headers = self.headers.copy()
        post_headers['Content-Type'] = 'application/json'
        
        try:
            response = requests.post(
                self.users_endpoint, 
                headers=post_headers, 
                json=data
            )
            
            # Handle both successful and error responses
            if response.status_code >= 200 and response.status_code < 300:
                try:
                    result = response.json()
                    return True, f"User {username} added successfully."
                except json.JSONDecodeError:
                    return True, response.text
            else:
                try:
                    error_data = response.json()
                    error_message = error_data.get('detail', response.text)
                    return False, f"Error: {error_message}"
                except json.JSONDecodeError:
                    return False, f"Error: {response.text}"
                
        except requests.exceptions.RequestException as e:
            return False, f"Error adding user: {str(e)}"

def generate_random_username(length=8):
    """Generate a random username of specified length"""
    characters = string.ascii_lowercase + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

def main():
    """
    Main function to run the script directly from command line.
    Usage: add_user.py <username> <traffic_limit_GB> <expiration_days> [password] [creation_date]
    """
    if len(sys.argv) < 4 or len(sys.argv) > 6:
        print("Usage: add_user.py <username> <traffic_limit_GB> <expiration_days> [password] [creation_date]")
        sys.exit(1)
    
    username = sys.argv[1]
    traffic_limit = int(sys.argv[2])
    expiration_days = int(sys.argv[3])
    password = sys.argv[4] if len(sys.argv) > 4 else None
    creation_date = sys.argv[5] if len(sys.argv) > 5 else None
    
    try:
        client = APIClient()
        success, message = client.add_user(
            username, traffic_limit, expiration_days, password, creation_date
        )
        
        print(message)
        if not success:
            sys.exit(1)
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()