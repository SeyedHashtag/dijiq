#!/usr/bin/env python3
import os
import sys
import json
from typing import Dict, Any, List
import argparse

# Import the APIClient class from add_user.py to maintain consistency
try:
    from .add_user import APIClient
except ImportError:
    # For standalone usage
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from add_user import APIClient

def list_users() -> List[Dict[str, Any]]:
    """
    Get a list of all users using the API.
    
    Returns:
        Dictionary of users keyed by username
    
    Raises:
        Exception: If the API request fails
    """
    try:
        client = APIClient()
        users = client.get_users()
        if users is None:
            raise Exception("Failed to retrieve users from API")
        return users
    except Exception as e:
        raise Exception(f"Failed to list users: {str(e)}")

def main() -> None:
    """Main function for command-line usage"""
    parser = argparse.ArgumentParser(description='List all users in the system')
    
    try:
        users = list_users()
        print(json.dumps(users, indent=4))
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()