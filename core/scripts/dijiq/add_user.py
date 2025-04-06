#!/usr/bin/env python3
import os
import sys
import argparse
from datetime import datetime
import re

# Import the API client
sys.path.append('/etc/dijiq/core')
try:
    from api_client import APIClient
except ImportError:
    # Adjust path if needed for development environment
    script_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(os.path.dirname(script_dir))
    sys.path.append(parent_dir)
    from api_client import APIClient

def validate_username(username: str) -> bool:
    """
    Validates that username only contains letters and numbers.
    Returns True if valid, False otherwise.
    """
    return bool(re.match(r'^[a-zA-Z0-9]+$', username))

def validate_date_format(date_str: str) -> bool:
    """
    Validates that the date string is in YYYY-MM-DD format and is a valid date.
    Returns True if valid, False otherwise.
    """
    if not re.match(r'^[0-9]{4}-[0-9]{2}-[0-9]{2}$', date_str):
        return False
    
    try:
        datetime.strptime(date_str, '%Y-%m-%d')
        return True
    except ValueError:
        return False

def add_user(username, traffic_limit, expiration_days, password=None, creation_date=None):
    """
    Add a user via the API
    
    Args:
        username: Username for the new user
        traffic_limit: Traffic limit in GB
        expiration_days: Number of days until expiration
        password: Optional password (generated if not provided)
        creation_date: Optional creation date (uses current date if not provided)
        
    Returns:
        Tuple of (success: bool, message: str)
    """
    # Input validation
    username_lower = username.lower()
    
    if not validate_username(username):
        return False, "Error: Username can only contain letters and numbers."
    
    try:
        traffic_limit = int(traffic_limit)
        if traffic_limit <= 0:
            return False, "Error: Traffic limit must be greater than 0."
    except ValueError:
        return False, "Error: Traffic limit must be a number."
    
    try:
        expiration_days = int(expiration_days)
        if expiration_days <= 0:
            return False, "Error: Expiration days must be greater than 0."
    except ValueError:
        return False, "Error: Expiration days must be a number."
    
    if creation_date and not validate_date_format(creation_date):
        return False, "Invalid date. Please provide a valid date in YYYY-MM-DD format."
    
    # Use API client to add the user
    try:
        client = APIClient()
        return client.add_user(
            username_lower, 
            traffic_limit,
            expiration_days, 
            password, 
            creation_date
        )
    except Exception as e:
        return False, f"Error: {str(e)}"

def main():
    """
    Command-line interface for adding a user
    """
    parser = argparse.ArgumentParser(description='Add a new user via API')
    parser.add_argument('username', help='Username for the new user')
    parser.add_argument('traffic_limit', help='Traffic limit in GB')
    parser.add_argument('expiration_days', help='Number of days until expiration')
    parser.add_argument('password', nargs='?', default=None, help='Optional password (generated if not provided)')
    parser.add_argument('creation_date', nargs='?', default=None, help='Optional creation date in YYYY-MM-DD format (current date if not provided)')
    
    if len(sys.argv) not in [4, 6]:
        parser.print_help()
        sys.exit(1)
    
    args = parser.parse_args()
    
    success, message = add_user(
        args.username,
        args.traffic_limit,
        args.expiration_days,
        args.password,
        args.creation_date
    )
    
    print(message)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()