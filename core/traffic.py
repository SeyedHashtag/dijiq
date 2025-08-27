#!/usr/bin/env python3
import json
import os
import sys
import time
import fcntl
import shutil
import datetime
from concurrent.futures import ThreadPoolExecutor
from hysteria2_api import Hysteria2Client

CONFIG_FILE = '/etc/hysteria/config.json'
USERS_FILE = '/etc/hysteria/users.json'
API_BASE_URL = 'http://127.0.0.1:25413'
LOCKFILE = "/tmp/kick.lock"
BACKUP_FILE = f"{USERS_FILE}.bak"
MAX_WORKERS = 8

def acquire_lock():
    """Acquires a lock file to prevent concurrent execution"""
    try:
        lock_file = open(LOCKFILE, 'w')
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return lock_file
    except IOError:
        sys.exit(1)

def traffic_status(no_gui=False):
    """Updates and retrieves traffic statistics for all users."""
    green = '\033[0;32m'
    cyan = '\033[0;36m'
    NC = '\033[0m'

    try:
        with open(CONFIG_FILE, 'r') as config_file:
            config = json.load(config_file)
            secret = config.get('trafficStats', {}).get('secret')
    except (json.JSONDecodeError, FileNotFoundError) as e:
        if not no_gui:
            print(f"Error: Failed to read secret from {CONFIG_FILE}. Details: {e}")
        return None

    if not secret:
        if not no_gui:
            print("Error: Secret not found in config.json")
        return None

    client = Hysteria2Client(base_url=API_BASE_URL, secret=secret)

    try:
        traffic_stats = client.get_traffic_stats(clear=True)
        online_status = client.get_online_clients()
    except Exception as e:
        if not no_gui:
            print(f"Error communicating with Hysteria2 API: {e}")
        return None

    users_data = {}
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, 'r') as users_file:
                users_data = json.load(users_file)
        except json.JSONDecodeError:
            if not no_gui:
                print("Error: Failed to parse existing users data JSON file.")
            return None

    for user in users_data:
        users_data[user]["status"] = "Offline"

    for user_id, status in online_status.items():
        if user_id in users_data:
            users_data[user_id]["status"] = "Online" if status.is_online else "Offline"
        else:
            users_data[user_id] = {
                "upload_bytes": 0, "download_bytes": 0,
                "status": "Online" if status.is_online else "Offline"
            }

    for user_id, stats in traffic_stats.items():
        if user_id in users_data:
            users_data[user_id]["upload_bytes"] = users_data[user_id].get("upload_bytes", 0) + stats.upload_bytes
            users_data[user_id]["download_bytes"] = users_data[user_id].get("download_bytes", 0) + stats.download_bytes
        else:
            online = user_id in online_status and online_status[user_id].is_online
            users_data[user_id] = {
                "upload_bytes": stats.upload_bytes, "download_bytes": stats.download_bytes,
                "status": "Online" if online else "Offline"
            }

    today_date = datetime.datetime.now().strftime("%Y-%m-%d")
    for username, user_data in users_data.items():
        is_on_hold = not user_data.get("account_creation_date")

        if is_on_hold:
            is_online = user_data.get("status") == "Online"
            has_traffic = user_data.get("download_bytes", 0) > 0 or user_data.get("upload_bytes", 0) > 0
            
            if is_online or has_traffic:
                user_data["account_creation_date"] = today_date
            else:
                user_data["status"] = "On-hold"

    with open(USERS_FILE, 'w') as users_file:
        json.dump(users_data, users_file, indent=4)

    if not no_gui:
        display_traffic_data(users_data, green, cyan, NC)
    
    return users_data

def display_traffic_data(data, green, cyan, NC):
    """Displays traffic data in a formatted table"""
    if not data:
        print("No traffic data to display.")
        return

    print("Traffic Data:")
    print("-------------------------------------------------")
    print(f"{'User':<15} {'Upload (TX)':<15} {'Download (RX)':<15} {'Status':<10}")
    print("-------------------------------------------------")

    for user, entry in data.items():
        upload_bytes = entry.get("upload_bytes", 0)
        download_bytes = entry.get("download_bytes", 0)
        status = entry.get("status", "Offline")

        formatted_tx = format_bytes(upload_bytes)
        formatted_rx = format_bytes(download_bytes)

        print(f"{user:<15} {green}{formatted_tx:<15}{NC} {cyan}{formatted_rx:<15}{NC} {status:<10}")
        print("-------------------------------------------------")

def format_bytes(bytes_val):
    """Format bytes as human-readable string"""
    if bytes_val < 1024: return f"{bytes_val}B"
    elif bytes_val < 1048576: return f"{bytes_val / 1024:.2f}KB"
    elif bytes_val < 1073741824: return f"{bytes_val / 1048576:.2f}MB"
    elif bytes_val < 1099511627776: return f"{bytes_val / 1073741824:.2f}GB"
    else: return f"{bytes_val / 1099511627776:.2f}TB"

def kick_users(usernames, secret):
    """Kicks specified users from the server"""
    try:
        client = Hysteria2Client(base_url=API_BASE_URL, secret=secret)
        client.kick_clients(usernames)
        return True
    except Exception:
        return False

def process_user(username, user_data, users_data):
    """Process a single user to check if they should be kicked"""
    if user_data.get('blocked', False): return None
    
    account_creation_date = user_data.get('account_creation_date')
    if not account_creation_date: return None

    max_download_bytes = user_data.get('max_download_bytes', 0)
    expiration_days = user_data.get('expiration_days', 0)
    total_bytes = user_data.get('download_bytes', 0) + user_data.get('upload_bytes', 0)
    
    should_block = False
    try:
        if expiration_days > 0:
            creation_date = datetime.datetime.strptime(account_creation_date, "%Y-%m-%d")
            expiration_date = creation_date + datetime.timedelta(days=expiration_days)
            if datetime.datetime.now() >= expiration_date:
                should_block = True
        
        if not should_block and max_download_bytes > 0 and total_bytes >= max_download_bytes:
            should_block = True
            
        if should_block:
            users_data[username]['blocked'] = True
            return username
    except (ValueError, TypeError):
        return None
    
    return None

def kick_expired_users():
    """Kicks users who have exceeded their data limits or whose accounts have expired"""
    lock_file = acquire_lock()
    
    try:
        if not os.path.exists(USERS_FILE): return
        shutil.copy2(USERS_FILE, BACKUP_FILE)
        
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                secret = config.get('trafficStats', {}).get('secret', '')
                if not secret: sys.exit(1)
        except Exception:
            sys.exit(1)
            
        with open(USERS_FILE, 'r') as f:
            users_data = json.load(f)
            
        users_to_kick = []
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = [executor.submit(process_user, u, d, users_data) for u, d in users_data.items()]
            for future in futures:
                result = future.result()
                if result:
                    users_to_kick.append(result)
        
        if users_to_kick:
            with open(USERS_FILE, 'w') as f:
                json.dump(users_data, f, indent=4)
            
            for i in range(0, len(users_to_kick), 50):
                batch = users_to_kick[i:i+50]
                kick_users(batch, secret)
                        
    except Exception:
        if os.path.exists(BACKUP_FILE):
            shutil.copy2(BACKUP_FILE, USERS_FILE)
        sys.exit(1)
    finally:
        fcntl.flock(lock_file, fcntl.LOCK_UN)
        lock_file.close()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "kick":
            kick_expired_users()
        elif sys.argv[1] == "--no-gui":
            traffic_status(no_gui=True)
            kick_expired_users()
        else:
            print(f"Unknown argument: {sys.argv[1]}")
            print("Usage: python traffic.py [kick|--no-gui]")
    else:
        traffic_status(no_gui=False)