#!/usr/bin/env python3

import json
import sys
import os
import subprocess
import argparse
import re
from datetime import datetime
from init_paths import *
from paths import *

def add_bulk_users(traffic_gb, expiration_days, count, prefix, start_number, unlimited_user):
    try:
        traffic_bytes = int(float(traffic_gb) * 1073741824)
    except ValueError:
        print("Error: Traffic limit must be a numeric value.")
        return 1

    if not os.path.isfile(USERS_FILE):
        try:
            with open(USERS_FILE, 'w') as f:
                json.dump({}, f)
        except IOError:
            print(f"Error: Could not create {USERS_FILE}.")
            return 1

    try:
        with open(USERS_FILE, 'r+') as f:
            try:
                users_data = json.load(f)
            except json.JSONDecodeError:
                print(f"Error: {USERS_FILE} contains invalid JSON.")
                return 1

            existing_users_lower = {u.lower() for u in users_data}
            new_users_to_add = {}
            creation_date = None

            try:
                password_process = subprocess.run(['pwgen', '-s', '32', str(count)], capture_output=True, text=True, check=True)
                passwords = password_process.stdout.strip().split('\n')
            except (FileNotFoundError, subprocess.CalledProcessError):
                print("Warning: 'pwgen' not found or failed. Falling back to UUID for password generation.")
                passwords = [subprocess.check_output(['cat', '/proc/sys/kernel/random/uuid'], text=True).strip() for _ in range(count)]

            if len(passwords) < count:
                print("Error: Could not generate enough passwords.")
                return 1

            for i in range(count):
                username = f"{prefix}{start_number + i}"
                username_lower = username.lower()

                if not re.match(r"^[a-zA-Z0-9_]+$", username_lower):
                    print(f"Error: Generated username '{username}' contains invalid characters. Use only letters, numbers, and underscores.")
                    continue

                if username_lower in existing_users_lower or username_lower in new_users_to_add:
                    print(f"Warning: User '{username}' already exists. Skipping.")
                    continue

                new_users_to_add[username_lower] = {
                    "password": passwords[i],
                    "max_download_bytes": traffic_bytes,
                    "expiration_days": expiration_days,
                    "account_creation_date": creation_date,
                    "blocked": False,
                    "unlimited_user": unlimited_user
                }
                # print(f"Preparing to add user: {username}")

            if not new_users_to_add:
                print("No new users to add.")
                return 0

            users_data.update(new_users_to_add)
            
            f.seek(0)
            json.dump(users_data, f, indent=4)
            f.truncate()
            
        print(f"\nSuccessfully added {len(new_users_to_add)} users.")
        return 0

    except IOError:
        print(f"Error: Could not read or write to {USERS_FILE}.")
        return 1
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return 1

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Add bulk users to Hysteria2.")
    parser.add_argument("-t", "--traffic-gb", dest="traffic_gb", type=float, required=True, help="Traffic limit for each user in GB.")
    parser.add_argument("-e", "--expiration-days", dest="expiration_days", type=int, required=True, help="Expiration duration for each user in days.")
    parser.add_argument("-c", "--count", type=int, required=True, help="Number of users to create.")
    parser.add_argument("-p", "--prefix", type=str, required=True, help="Prefix for usernames.")
    parser.add_argument("-s", "--start-number", type=int, default=1, help="Starting number for username suffix (default: 1).")
    parser.add_argument("-u", "--unlimited", action='store_true', help="Flag to mark users as unlimited (exempt from IP limits).")

    args = parser.parse_args()

    sys.exit(add_bulk_users(
        traffic_gb=args.traffic_gb,
        expiration_days=args.expiration_days,
        count=args.count,
        prefix=args.prefix,
        start_number=args.start_number,
        unlimited_user=args.unlimited
    ))