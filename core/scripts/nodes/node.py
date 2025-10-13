#!/usr/bin/env python3

import sys
import json
import argparse
from pathlib import Path
import re
from ipaddress import ip_address
import subprocess
from datetime import datetime, timedelta
from init_paths import *
from paths import NODES_JSON_PATH


def is_valid_ip_or_domain(value: str) -> bool:
    if not value or not value.strip():
        return False
    value = value.strip()
    try:
        ip_address(value)
        return True
    except ValueError:
        domain_regex = re.compile(
            r'^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9][a-z0-9-]{0,61}[a-z0-9]$',
            re.IGNORECASE
        )
        return re.match(domain_regex, value) is not None

def is_valid_sni(value: str) -> bool:
    if not value or not value.strip():
        return False
    value = value.strip()
    try:
        ip_address(value)
        return False
    except ValueError:
        if "https://" in value or "http://" in value or "//" in value:
            return False
        domain_regex = re.compile(
            r'^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9][a-z0-9-]{0,61}[a-z0-9]$',
            re.IGNORECASE
        )
        return re.match(domain_regex, value) is not None

def is_valid_sha256_pin(value: str) -> bool:
    if not value or not value.strip():
        return False
    value = value.strip().upper()
    pin_regex = re.compile(r'^([0-9A-F]{2}:){31}[0-9A-F]{2}$')
    return re.match(pin_regex, value) is not None

def read_nodes():
    if not NODES_JSON_PATH.exists():
        return []
    try:
        with NODES_JSON_PATH.open("r") as f:
            content = f.read()
            if not content:
                return []
            return json.loads(content)
    except (json.JSONDecodeError, IOError, OSError) as e:
        sys.exit(f"Error reading or parsing {NODES_JSON_PATH}: {e}")

def write_nodes(nodes):
    try:
        NODES_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
        with NODES_JSON_PATH.open("w") as f:
            json.dump(nodes, f, indent=4)
    except (IOError, OSError) as e:
        sys.exit(f"Error writing to {NODES_JSON_PATH}: {e}")

def add_node(name: str, ip: str, sni: str | None = None, pinSHA256: str | None = None):
    if not is_valid_ip_or_domain(ip):
        print(f"Error: '{ip}' is not a valid IP address or domain name.", file=sys.stderr)
        sys.exit(1)

    if sni and not is_valid_sni(sni):
        print(f"Error: '{sni}' is not a valid domain name for SNI. Do not include http/https and ensure it's not an IP.", file=sys.stderr)
        sys.exit(1)

    if pinSHA256 and not is_valid_sha256_pin(pinSHA256):
        print(f"Error: '{pinSHA256}' is not a valid SHA256 pin format.", file=sys.stderr)
        sys.exit(1)

    nodes = read_nodes()
    if any(node['name'] == name for node in nodes):
        print(f"Error: A node with the name '{name}' already exists.", file=sys.stderr)
        sys.exit(1)
    if any(node['ip'] == ip for node in nodes):
        print(f"Error: A node with the IP/domain '{ip}' already exists.", file=sys.stderr)
        sys.exit(1)
    
    new_node = {"name": name, "ip": ip}
    if sni:
        new_node["sni"] = sni.strip()
    if pinSHA256:
        new_node["pinSHA256"] = pinSHA256.strip().upper()

    nodes.append(new_node)
    write_nodes(nodes)
    print(f"Successfully added node '{name}'.")

def delete_node(name: str):
    nodes = read_nodes()
    original_count = len(nodes)
    nodes = [node for node in nodes if node['name'] != name]
    
    if len(nodes) == original_count:
        print(f"Error: No node with the name '{name}' found.", file=sys.stderr)
        sys.exit(1)

    write_nodes(nodes)
    print(f"Successfully deleted node '{name}'.")

def list_nodes():
    nodes = read_nodes()
    if not nodes:
        print("No nodes configured.")
        return
        
    print(f"{'Name':<20} {'IP / Domain':<25} {'SNI':<25} {'Pin SHA256'}")
    print(f"{'-'*20} {'-'*25} {'-'*25} {'-'*30}")
    for node in sorted(nodes, key=lambda x: x['name']):
        name = node['name']
        ip = node['ip']
        sni = node.get('sni', 'N/A')
        pin = node.get('pinSHA256', 'N/A')
        print(f"{name:<20} {ip:<25} {sni:<25} {pin}")

def generate_cert():
    try:
        script_dir = Path(__file__).parent.resolve()
        key_filepath = script_dir / "blitz.key"
        cert_filepath = script_dir / "blitz.crt"
        
        if cert_filepath.exists():
            try:
                check_cmd = ['openssl', 'x509', '-in', str(cert_filepath), '-noout', '-enddate']
                result = subprocess.run(check_cmd, capture_output=True, text=True, check=True)
                
                end_date_str = result.stdout.strip().split('=')[1]
                end_date = datetime.strptime(end_date_str, '%b %d %H:%M:%S %Y %Z')
                
                if end_date > datetime.now() + timedelta(days=30):
                    print("Existing certificate is valid for more than 30 days.")
                    print("\n")
                    print(cert_filepath.read_text().strip())
                    return
                else:
                    print("Existing certificate is expiring in less than 30 days. Generating a new one.")
            except (subprocess.CalledProcessError, FileNotFoundError, IndexError, ValueError) as e:
                print(f"Could not validate existing certificate: {e}. Generating a new one.")

        print("Generating new certificate and key...")
        openssl_command = [
            'openssl', 'req', '-x509',
            '-newkey', 'ec',
            '-pkeyopt', 'ec_paramgen_curve:prime256v1',
            '-keyout', str(key_filepath),
            '-out', str(cert_filepath),
            '-sha256', '-days', '3650', '-nodes',
            '-subj', '/CN=Blitz'
        ]
        
        result = subprocess.run(openssl_command, capture_output=True, text=True, check=False)

        if result.returncode != 0:
            sys.exit(f"Error generating certificate with OpenSSL:\n{result.stderr}")
        
        cert_content = cert_filepath.read_text()
        
        print("Successfully generated certificate and key:")
        print("\n")
        print(cert_content.strip())

    except FileNotFoundError:
        sys.exit("Error: 'openssl' command not found. Please ensure OpenSSL is installed and in your PATH.")
    except Exception as e:
        sys.exit(f"An unexpected error occurred: {e}")

def main():
    parser = argparse.ArgumentParser(description="Manage external node configurations.")
    subparsers = parser.add_subparsers(dest='command', required=True)

    add_parser = subparsers.add_parser('add', help='Add a new node.')
    add_parser.add_argument('--name', type=str, required=True, help='The unique name of the node.')
    add_parser.add_argument('--ip', type=str, required=True, help='The IP address or domain of the node.')
    add_parser.add_argument('--sni', type=str, help='Optional: The Server Name Indication (e.g., yourdomain.com).')
    add_parser.add_argument('--pinSHA256', type=str, help='Optional: The public key SHA256 pin.')

    delete_parser = subparsers.add_parser('delete', help='Delete a node by name.')
    delete_parser.add_argument('--name', type=str, required=True, help='The name of the node to delete.')

    subparsers.add_parser('list', help='List all configured nodes.')
    
    subparsers.add_parser('generate-cert', help="Generate blitz.crt and blitz.key if they don't exist or are expiring soon.")
    
    args = parser.parse_args()

    if args.command == 'add':
        add_node(args.name, args.ip, args.sni, args.pinSHA256)
    elif args.command == 'delete':
        delete_node(args.name)
    elif args.command == 'list':
        list_nodes()
    elif args.command == 'generate-cert':
        generate_cert()

if __name__ == "__main__":
    main()