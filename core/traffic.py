#!/usr/bin/env python3

import json
import os
import sys
import fcntl
import datetime
from hysteria2_api import Hysteria2Client

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(SCRIPT_DIR, 'scripts'))

from db.database import db

CONFIG_FILE = '/etc/hysteria/config.json'
API_BASE_URL = 'http://127.0.0.1:25413'
LOCKFILE = "/tmp/hysteria_traffic.lock"

def acquire_lock():
    try:
        lock_file = open(LOCKFILE, 'w')
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return lock_file
    except IOError:
        sys.exit(1)

def get_secret():
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
        return config.get('trafficStats', {}).get('secret')
    except (json.JSONDecodeError, FileNotFoundError):
        return None

def format_bytes(bytes_val):
    if bytes_val < 1024: return f"{bytes_val}B"
    elif bytes_val < 1048576: return f"{bytes_val / 1024:.2f}KB"
    elif bytes_val < 1073741824: return f"{bytes_val / 1048576:.2f}MB"
    elif bytes_val < 1099511627776: return f"{bytes_val / 1073741824:.2f}GB"
    else: return f"{bytes_val / 1099511627776:.2f}TB"

def display_traffic_data(data, green, cyan, NC):
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
        status = entry.get("status", "On-hold")
        formatted_tx = format_bytes(upload_bytes)
        formatted_rx = format_bytes(download_bytes)
        print(f"{user:<15} {green}{formatted_tx:<15}{NC} {cyan}{formatted_rx:<15}{NC} {status:<10}")
        print("-------------------------------------------------")

def traffic_status(no_gui=False):
    green, cyan, NC = '\033[0;32m', '\033[0;36m', '\033[0m'
    
    if db is None:
        if not no_gui: print("Error: Database connection failed.")
        return None

    secret = get_secret()
    if not secret:
        if not no_gui: print(f"Error: Secret not found or failed to read {CONFIG_FILE}.")
        return None

    client = Hysteria2Client(base_url=API_BASE_URL, secret=secret)
    try:
        traffic_stats = client.get_traffic_stats(clear=True)
        online_status = client.get_online_clients()
    except Exception as e:
        if not no_gui: print(f"Error communicating with Hysteria2 API: {e}")
        return None

    try:
        all_users = db.get_all_users()
        initial_users_data = {user['_id']: user for user in all_users}
    except Exception as e:
        if not no_gui: print(f"Error fetching users from database: {e}")
        return None

    today_date = datetime.datetime.now().strftime("%Y-%m-%d")
    users_to_update = {}

    for username, user_data in initial_users_data.items():
        updates = {}
        is_online_locally = username in online_status and online_status[username].is_online
        online_count_db = user_data.get('online_count', 0)
        
        is_online_globally = is_online_locally or online_count_db > 0

        if username in traffic_stats:
            new_upload = user_data.get('upload_bytes', 0) + traffic_stats[username].upload_bytes
            new_download = user_data.get('download_bytes', 0) + traffic_stats[username].download_bytes
            if new_upload != user_data.get('upload_bytes'): updates['upload_bytes'] = new_upload
            if new_download != user_data.get('download_bytes'): updates['download_bytes'] = new_download
            
        is_activated = "account_creation_date" in user_data
        
        if not is_activated:
            current_traffic = traffic_stats.get(username)
            has_activity = is_online_globally or (current_traffic and (current_traffic.upload_bytes > 0 or current_traffic.download_bytes > 0))

            if has_activity:
                updates["account_creation_date"] = today_date
                updates["status"] = "Online" if is_online_globally else "Offline"
            else:
                if user_data.get("status") != "On-hold":
                    updates["status"] = "On-hold"
        else:
            new_status = "Online" if is_online_globally else "Offline"
            if user_data.get("status") != new_status:
                updates["status"] = new_status
        
        if updates:
            users_to_update[username] = updates

    if users_to_update:
        try:
            for username, update_data in users_to_update.items():
                db.update_user(username, update_data)
        except Exception as e:
            if not no_gui: print(f"Error updating database: {e}")
            return None

    if not no_gui:
        # For display, merge updates into the initial data
        for username, updates in users_to_update.items():
            initial_users_data[username].update(updates)
        display_traffic_data(initial_users_data, green, cyan, NC)
    
    return initial_users_data

def kick_api_call(usernames, secret):
    try:
        client = Hysteria2Client(base_url=API_BASE_URL, secret=secret)
        client.kick_clients(usernames)
    except Exception as e:
        print(f"Failed to kick users via API: {e}", file=sys.stderr)

def kick_expired_users():
    if db is None:
        print("Error: Database connection failed.", file=sys.stderr)
        return
            
    secret = get_secret()
    if not secret:
        print(f"Error: Secret not found or failed to read {CONFIG_FILE}.", file=sys.stderr)
        return
    
    all_users = db.get_all_users()
    users_to_kick, users_to_block = [], []

    for user in all_users:
        username = user.get('_id')
        if not username or user.get('blocked', False) or not user.get('account_creation_date'):
            continue

        total_bytes = user.get('download_bytes', 0) + user.get('upload_bytes', 0)
        should_block = False
        try:
            if user.get('expiration_days', 0) > 0:
                creation_date = datetime.datetime.strptime(user['account_creation_date'], "%Y-%m-%d")
                if datetime.datetime.now() >= creation_date + datetime.timedelta(days=user['expiration_days']):
                    should_block = True
            
            if not should_block and user.get('max_download_bytes', 0) > 0 and total_bytes >= user['max_download_bytes']:
                should_block = True
                
            if should_block:
                users_to_kick.append(username)
                users_to_block.append(username)
        except (ValueError, TypeError):
            continue
    
    if users_to_block:
        for username in users_to_block:
            db.update_user(username, {'blocked': True})
    
    if users_to_kick:
        for i in range(0, len(users_to_kick), 50):
            kick_api_call(users_to_kick[i:i+50], secret)

if __name__ == "__main__":
    lock_file = acquire_lock()
    try:
        if len(sys.argv) > 1:
            if sys.argv[1] == "kick":
                kick_expired_users()
            elif sys.argv[1] == "--no-gui":
                traffic_status(no_gui=True)
                kick_expired_users()
            else:
                print(f"Usage: python {sys.argv[0]} [kick|--no-gui]")
        else:
            traffic_status(no_gui=False)
    finally:
        fcntl.flock(lock_file, fcntl.LOCK_UN)
        lock_file.close()