#!/usr/bin/env python3

import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from db.database import db

def remove_user(username):
    if db is None:
        return 1, "Error: Database connection failed. Please ensure MongoDB is running."

    try:
        result = db.delete_user(username)
        if result.deleted_count > 0:
            return 0, f"User {username} removed successfully."
        else:
            return 1, f"Error: User {username} not found."

    except Exception as e:
        return 1, f"An error occurred while removing the user: {e}"

def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <username>")
        sys.exit(1)

    username = sys.argv[1].lower()
    exit_code, message = remove_user(username)
    print(message)
    sys.exit(exit_code)

if __name__ == "__main__":
    main()