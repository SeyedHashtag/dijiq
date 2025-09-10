#!/usr/bin/env python3

import init_paths
import os
import sys
import json
import argparse
from functools import lru_cache
from typing import Dict, List, Any
from db.database import db
from paths import *

@lru_cache(maxsize=None)
def load_json_file(file_path: str) -> Any:
    if not os.path.exists(file_path):
        return None
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            return json.loads(content) if content else None
    except (json.JSONDecodeError, IOError):
        return None

@lru_cache(maxsize=None)
def load_env_file(env_file: str) -> Dict[str, str]:
    env_vars = {}
    if os.path.exists(env_file):
        with open(env_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key] = value.strip()
    return env_vars

def generate_uri(username: str, auth_password: str, ip: str, port: str, 
                 uri_params: Dict[str, str], ip_version: int, fragment_tag: str) -> str:
    ip_part = f"[{ip}]" if ip_version == 6 and ':' in ip else ip
    uri_base = f"hy2://{username}:{auth_password}@{ip_part}:{port}"
    query_string = "&".join([f"{k}={v}" for k, v in uri_params.items()])
    return f"{uri_base}?{query_string}#{fragment_tag}"

def process_users(target_usernames: List[str]) -> List[Dict[str, Any]]:
    config = load_json_file(CONFIG_FILE)
    if not config:
        print("Error: Could not load Hysteria2 configuration file.", file=sys.stderr)
        sys.exit(1)
        
    if db is None:
        print("Error: Database connection failed.", file=sys.stderr)
        sys.exit(1)

    nodes = load_json_file(NODES_JSON_PATH) or []
    port = config.get("listen", "").split(":")[-1]
    tls_config = config.get("tls", {})
    hy2_env = load_env_file(CONFIG_ENV)
    ns_env = load_env_file(NORMALSUB_ENV)

    base_uri_params = {
        "insecure": "1" if tls_config.get("insecure", True) else "0",
        "sni": hy2_env.get('SNI', '')
    }
    obfs_password = config.get("obfs", {}).get("salamander", {}).get("password")
    if obfs_password:
        base_uri_params["obfs"] = "salamander"
        base_uri_params["obfs-password"] = obfs_password
    
    sha256 = tls_config.get("pinSHA256")
    if sha256:
        base_uri_params["pinSHA256"] = sha256
    
    ip4 = hy2_env.get('IP4')
    ip6 = hy2_env.get('IP6')
    ns_domain, ns_port, ns_subpath = ns_env.get('HYSTERIA_DOMAIN'), ns_env.get('HYSTERIA_PORT'), ns_env.get('SUBPATH')

    results = []
    for username in target_usernames:
        user_data = db.get_user(username)
        if not user_data or "password" not in user_data:
            results.append({"username": username, "error": "User not found or password not set"})
            continue

        auth_password = user_data["password"]
        user_output = {"username": username, "ipv4": None, "ipv6": None, "nodes": [], "normal_sub": None}

        if ip4 and ip4 != "None":
            user_output["ipv4"] = generate_uri(username, auth_password, ip4, port, base_uri_params, 4, f"{username}-IPv4")
        if ip6 and ip6 != "None":
            user_output["ipv6"] = generate_uri(username, auth_password, ip6, port, base_uri_params, 6, f"{username}-IPv6")

        for node in nodes:
            if node_name := node.get("name"):
                if node_ip := node.get("ip"):
                    ip_v = 6 if ':' in node_ip else 4
                    tag = f"{username}-{node_name}"
                    uri = generate_uri(username, auth_password, node_ip, port, base_uri_params, ip_v, tag)
                    user_output["nodes"].append({"name": node_name, "uri": uri})
        
        if ns_domain and ns_port and ns_subpath:
            user_output["normal_sub"] = f"https://{ns_domain}:{ns_port}/{ns_subpath}/sub/normal/{auth_password}#{username}"

        results.append(user_output)
        
    return results

def main():
    parser = argparse.ArgumentParser(description="Efficiently generate Hysteria2 URIs for multiple users.")
    parser.add_argument('usernames', nargs='*', help="A list of usernames to process.")
    parser.add_argument('--all', action='store_true', help="Process all users from the database.")
    
    args = parser.parse_args()
    target_usernames = args.usernames
    
    if args.all:
        if db is None:
            print("Error: Database connection failed.", file=sys.stderr)
            sys.exit(1)
        try:
            all_users_docs = db.get_all_users()
            target_usernames = [user['_id'] for user in all_users_docs]
        except Exception as e:
            print(f"Error retrieving all users from database: {e}", file=sys.stderr)
            sys.exit(1)
            
    if not target_usernames:
        parser.print_help()
        sys.exit(1)

    output_list = process_users(target_usernames)
    print(json.dumps(output_list, indent=2))

if __name__ == "__main__":
    main()