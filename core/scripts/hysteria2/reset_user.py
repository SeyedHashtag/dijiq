#!/usr/bin/env python3

import sys
import os
from datetime import date

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from db.database import db

def reset_user(username):
    """
    Resets the data usage, status, and creation date of a user in the database.

    Args:
        username (str): The username to reset.

    Returns:
        int: 0 on success, 1 on failure.
    """
    if db is None:
        print("Error: Database connection failed. Please ensure MongoDB is running.")
        return 1

    try:
        user = db.get_user(username)
        if not user:
            print(f"Error: User '{username}' not found in the database.")
            return 1

        updates = {
            'upload_bytes': 0,
            'download_bytes': 0,
            'status': 'Offline',
            'account_creation_date': date.today().strftime("%Y-%m-%d"),
            'blocked': False
        }

        result = db.update_user(username, updates)
        if result.modified_count > 0:
            print(f"User '{username}' has been reset successfully.")
            return 0
        else:
            print(f"User '{username}' data was already in a reset state. No changes made.")
            return 0

    except Exception as e:
        print(f"An error occurred while resetting the user: {e}")
        return 1

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <username>")
        sys.exit(1)

    username_to_reset = sys.argv[1].lower()
    exit_code = reset_user(username_to_reset)
    sys.exit(exit_code)