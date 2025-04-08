#!/usr/bin/env python3

import os
import sys
import re
import argparse
import requests
import json
from datetime import datetime
from dotenv import load_dotenv

# Path to configuration files
CONFIG_ENV = "/etc/dijiq/.configs.env"

class APIClient:
    def __init__(self):
        load_dotenv(CONFIG_ENV)
        
        self.base_url = os.getenv('API_BASE_URL')
        self.token = os.getenv('API_TOKEN')
        
        if not self.base_url:
            print("API base URL not found in configuration.")
            print("Please set up the API configuration first using menu.sh")
            sys.exit(1)
            
        if not self.token:
            print("API token not found in configuration.")
            print("Please set up the API configuration first using menu.sh")
            sys.exit(1)
        
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
            print(f"Error fetching users: {e}")
            return None
    
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
            
            try:
                return response.json()
            except json.JSONDecodeError:
                return response.text
                
        except requests.exceptions.RequestException as e:
            print(f"Error adding user: {e}")
            return None

def validate_username(username):
    if not re.match(r'^[a-zA-Z0-9]+$', username):
        print("Error: Username can only contain letters and numbers.")
        sys.exit(1)
    return username.lower()

def validate_date(date_string):
    if not date_string:
        return datetime.now().strftime('%Y-%m-%d')
        
    if not re.match(r'^\d{4}-\d{2}-\d{2}$', date_string):
        print("Invalid date format. Expected YYYY-MM-DD.")
        sys.exit(1)
        
    try:
        datetime.strptime(date_string, '%Y-%m-%d')
        return date_string
    except ValueError:
        print("Invalid date. Please provide a valid date in YYYY-MM-DD format.")
        sys.exit(1)

def check_user_exists(client, username):
    users = client.get_users()
    if not users:
        return False
        
    for user in users:
        if user.get('username', '').lower() == username.lower():
            return True
    return False

def main():
    parser = argparse.ArgumentParser(description='Add a new user via API')
    parser.add_argument('username', help='Username for the new user')
    parser.add_argument('traffic_limit', type=float, help='Traffic limit in GB')
    parser.add_argument('expiration_days', type=int, help='Number of days until account expiration')
    parser.add_argument('--password', help='Optional password (random if not provided)')
    parser.add_argument('--creation_date', help='Optional creation date (YYYY-MM-DD)')
    
    args = parser.parse_args()
    
    # Validate username
    username = validate_username(args.username)
    
    # Validate creation date if provided
    creation_date = validate_date(args.creation_date) if args.creation_date else None
    
    # Initialize API client
    client = APIClient()
    
    # Check if user already exists
    if check_user_exists(client, username):
        print("User already exists.")
        sys.exit(1)
    
    # Add user via API
    result = client.add_user(
        username=username,
        traffic_limit=args.traffic_limit,
        expiration_days=args.expiration_days,
        password=args.password,
        creation_date=creation_date
    )
    
    if result:
        print(f"User {username} added successfully.")
    else:
        print("Failed to add user.")
        sys.exit(1)

if __name__ == "__main__":
    main()