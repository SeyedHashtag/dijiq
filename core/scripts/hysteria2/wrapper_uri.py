#!/usr/bin/env python3

import os
import sys
import json
import argparse
from functools import lru_cache
from typing import Dict, List, Any

from init_paths import *
from paths import *

@lru_cache(maxsize=None)
def load_json_file(file_path: str) -> Any:
    if not os.path.exists(file_path):
        return None
    try:
        with open(file_path, 'r') as f:
            content = f.read()
            return json.loads(content) if content else None
    except (json.JSONDecodeError, IOError):
        return None

@lru_cache(maxsize=None)
def load_env_file(env_file: str) -> Dict[str, str]:
    env_vars = {}
    if os.path.exists(env_file):
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key] = value.strip()
    return env_vars

def generate_uri(username: str, auth_password: str, ip: str, port: str, 
                 obfs_password: str, sha256: str, sni: str, ip_version: int, 
                 insecure: bool, fragment_tag: str) -> str:
    ip_part = f"[{ip}]" if ip_version == 6 and ':' in ip else ip
    uri_base = f"hy2://{username}:{auth_password}@{ip_part}:{port}"
    
    params = {
        "insecure": "1" if insecure else "0",
        "sni": sni
    }
    if obfs_password:
        params["obfs"] = "salamander"
        params["obfs-password"] = obfs_password
    if sha256:
        params["pinSHA256"] = sha256
    
    query_string = "&".join([f"{k}={v}" for k, v in params.items()])
    return f"{uri_base}?{query_string}#{fragment_tag}"

def process_users(target_usernames: List[str]) -> List[Dict[str, Any]]:
    config = load_json_file(CONFIG_FILE)
    all_users = load_json_file(USERS_FILE)
    nodes = load_json_file(NODES_JSON_PATH) or []
    
    if not config or not all_users:
        print("Error: Could not load hysteria2 configuration or user files.", file=sys.stderr)
        sys.exit(1)

    port = config.get("listen", "").split(":")[-1]
    tls_config = config.get("tls", {})
    sha256 = tls_config.get("pinSHA256", "")
    insecure = tls_config.get("insecure", True)
    obfs_password = config.get("obfs", {}).get("salamander", {}).get("password", "")
    
    hy2_env = load_env_file(CONFIG_ENV)
    ip4 = hy2_env.get('IP4')
    ip6 = hy2_env.get('IP6')
    sni = hy2_env.get('SNI', '')

    ns_env = load_env_file(NORMALSUB_ENV)
    ns_domain = ns_env.get('HYSTERIA_DOMAIN')
    ns_port = ns_env.get('HYSTERIA_PORT')
    ns_subpath = ns_env.get('SUBPATH')

    results = []
    
    for username in target_usernames:
        user_data = all_users.get(username)
        if not user_data or "password" not in user_data:
            results.append({"username": username, "error": "User not found or password not set"})
            continue

        auth_password = user_data["password"]
        user_output = {
            "username": username,
            "ipv4": None,
            "ipv6": None,
            "nodes": [],
            "normal_sub": None
        }

        if ip4 and ip4 != "None":
            user_output["ipv4"] = generate_uri(
                username, auth_password, ip4, port, obfs_password, sha256, sni, 4, insecure, f"{username}-IPv4"
            )
        
        if ip6 and ip6 != "None":
            user_output["ipv6"] = generate_uri(
                username, auth_password, ip6, port, obfs_password, sha256, sni, 6, insecure, f"{username}-IPv6"
            )

        for node in nodes:
            node_name, node_ip = node.get("name"), node.get("ip")
            if not (node_name and node_ip):
                continue
            ip_v = 6 if ':' in node_ip else 4
            tag = f"{username}-{node_name}"
            uri = generate_uri(
                username, auth_password, node_ip, port, obfs_password, sha256, sni, ip_v, insecure, tag
            )
            user_output["nodes"].append({"name": node_name, "uri": uri})
        
        if ns_domain and ns_port and ns_subpath:
            user_output["normal_sub"] = f"https://{ns_domain}:{ns_port}/{ns_subpath}/sub/normal/{auth_password}#{username}"

        results.append(user_output)
        
    return results

def main():
    parser = argparse.ArgumentParser(
        description="Efficiently generate Hysteria2 URIs for multiple users.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument('usernames', nargs='*', help="A list of usernames to process.")
    parser.add_argument('--all', action='store_true', help="Process all users from users.json.")
    
    args = parser.parse_args()
    
    target_usernames = args.usernames
    if args.all:
        all_users = load_json_file(USERS_FILE)
        if all_users:
            target_usernames = list(all_users.keys())
        else:
            print("Error: Could not load users.json to process all users.", file=sys.stderr)
            sys.exit(1)
            
    if not target_usernames:
        parser.print_help()
        sys.exit(1)

    output_list = process_users(target_usernames)
    print(json.dumps(output_list, indent=2))

if __name__ == "__main__":
    main()