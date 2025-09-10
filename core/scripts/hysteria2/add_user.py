#!/usr/bin/env python3

import init_paths
import sys
import os
import subprocess
import re
from datetime import datetime
from db.database import db

def add_user(username, traffic_gb, expiration_days, password=None, creation_date=None, unlimited_user=False):
    if not username or not traffic_gb or not expiration_days:
        print(f"Usage: {sys.argv[0]} <username> <traffic_limit_GB> <expiration_days> [password] [creation_date] [unlimited_user (true/false)]")
        return 1

    if db is None:
        print("Error: Database connection failed. Please ensure MongoDB is running and configured.")
        return 1

    try:
        traffic_bytes = int(float(traffic_gb) * 1073741824)
        expiration_days = int(expiration_days)
    except ValueError:
        print("Error: Traffic limit and expiration days must be numeric.")
        return 1

    username_lower = username.lower()

    if not password:
        try:
            password_process = subprocess.run(['pwgen', '-s', '32', '1'], capture_output=True, text=True, check=True)
            password = password_process.stdout.strip()
        except FileNotFoundError:
            try:
                password = subprocess.check_output(['cat', '/proc/sys/kernel/random/uuid'], text=True).strip()
            except Exception:
                print("Error: Failed to generate password. Please install 'pwgen' or ensure /proc access.")
                return 1

    if not re.match(r"^[a-zA-Z0-9_]+$", username):
        print("Error: Username can only contain letters, numbers, and underscores.")
        return 1

    try:
        if db.get_user(username_lower):
            print("User already exists.")
            return 1

        user_data = {
            "username": username_lower,
            "password": password,
            "max_download_bytes": traffic_bytes,
            "expiration_days": expiration_days,
            "blocked": False,
            "unlimited_user": unlimited_user
        }
        
        if creation_date:
            if not re.match(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$", creation_date):
                print("Invalid date format. Expected YYYY-MM-DD.")
                return 1
            try:
                datetime.strptime(creation_date, "%Y-%m-%d")
                user_data["account_creation_date"] = creation_date
            except ValueError:
                print("Invalid date. Please provide a valid date in YYYY-MM-DD format.")
                return 1

        result = db.add_user(user_data)
        if result:
            print(f"User {username} added successfully.")
            return 0
        else:
            print(f"Error: Failed to add user {username}.")
            return 1

    except Exception as e:
        print(f"An error occurred: {e}")
        return 1

if __name__ == "__main__":
    if len(sys.argv) < 4 or len(sys.argv) > 7:
        print(f"Usage: {sys.argv[0]} <username> <traffic_limit_GB> <expiration_days> [password] [creation_date] [unlimited_user (true/false)]")
        sys.exit(1)

    username = sys.argv[1]
    traffic_gb = sys.argv[2]
    expiration_days = sys.argv[3]
    password = sys.argv[4] if len(sys.argv) > 4 else None
    creation_date = sys.argv[5] if len(sys.argv) > 5 else None
    unlimited_user_str = sys.argv[6] if len(sys.argv) > 6 else "false"
    unlimited_user = unlimited_user_str.lower() == 'true'

    exit_code = add_user(username, traffic_gb, expiration_days, password, creation_date, unlimited_user)
    sys.exit(exit_code)