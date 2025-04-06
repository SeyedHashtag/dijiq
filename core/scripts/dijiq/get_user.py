#!/usr/bin/env python3
import os
import requests
import json
import sys
import argparse
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# Import the APIClient class from add_user.py to maintain consistency
try:
    from .add_user import APIClient
except ImportError:
    # For standalone usage
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from add_user import APIClient

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
        user_data = client.get_user(username)
        if user_data is None:
            raise Exception(f"User '{username}' not found")
        return user_data
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
    main()