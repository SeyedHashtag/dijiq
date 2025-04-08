import os
import requests
import json
from dotenv import load_dotenv

class APIClient:
    def __init__(self):
        load_dotenv('/etc/dijiq/.configs.env')
        
        self.base_url = os.getenv('API_BASE_URL')
        self.token = os.getenv('API_TOKEN')
        
        if not self.base_url:
            raise ValueError("API base URL not found in configuration.")
            
        if not self.token:
            raise ValueError("API token not found in configuration.")
        
        if not self.base_url.endswith('/'):
            self.base_url += '/'
            
        self.users_endpoint = f"{self.base_url}api/v1/users/"
        
        # Add Bearer prefix if not already present in the token
        auth_token = self.token
        if not auth_token.startswith('Bearer '):
            auth_token = f"Bearer {auth_token}"
        
        self.headers = {
            'accept': 'application/json',
            'Authorization': auth_token
        }
        
        # Print debug information
        print(f"API Base URL: {self.base_url}")
        print(f"Authorization header: {auth_token[:10]}...")
    
    def get_users(self):
        try:
            print(f"Making GET request to: {self.users_endpoint}")
            response = requests.get(self.users_endpoint, headers=self.headers)
            print(f"Response status code: {response.status_code}")
            
            if response.status_code != 200:
                print(f"Response body: {response.text[:200]}")
                
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Request exception: {str(e)}")
            raise Exception(f"Error fetching users: {e}")
    
    def add_user(self, username, traffic_limit, expiration_days, password=None, creation_date=None):
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
            print(f"Making POST request to: {self.users_endpoint}")
            print(f"Request data: {data}")
            
            response = requests.post(
                self.users_endpoint, 
                headers=post_headers, 
                json=data
            )
            
            print(f"Response status code: {response.status_code}")
            if response.status_code >= 400:
                print(f"Response body: {response.text[:200]}")
                
            response.raise_for_status()
            
            return response.json()
                
        except requests.exceptions.RequestException as e:
            print(f"Request exception: {str(e)}")
            raise Exception(f"Error adding user: {e}")