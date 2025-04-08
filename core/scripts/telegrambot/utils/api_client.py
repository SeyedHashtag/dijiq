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
        
        self.headers = {
            'accept': 'application/json',
            'Authorization': self.token
        }
    
    def get_users(self):
        try:
            response = requests.get(self.users_endpoint, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
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
            response = requests.post(
                self.users_endpoint, 
                headers=post_headers, 
                json=data
            )
            
            response.raise_for_status()
            
            return response.json()
                
        except requests.exceptions.RequestException as e:
            raise Exception(f"Error adding user: {e}")