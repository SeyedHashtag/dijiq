#!/usr/bin/env python3

import sys
import json
import argparse
from pathlib import Path

core_scripts_dir = Path(__file__).resolve().parents[1]
if str(core_scripts_dir) not in sys.path:
    sys.path.append(str(core_scripts_dir))

    from paths import NODES_JSON_PATH



def read_nodes():
    if not NODES_JSON_PATH.exists():
        return []
    try:
        with NODES_JSON_PATH.open("r") as f:
            content = f.read()
            if not content:
                return []
            return json.loads(content)
    except json.JSONDecodeError:
        sys.exit(f"Error: Could not decode JSON from {NODES_JSON_PATH}")
    except (IOError, OSError) as e:
        sys.exit(f"Error reading from {NODES_JSON_PATH}: {e}")

def write_nodes(nodes):
    try:
        NODES_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
        with NODES_JSON_PATH.open("w") as f:
            json.dump(nodes, f, indent=4)
    except (IOError, OSError) as e:
        sys.exit(f"Error writing to {NODES_JSON_PATH}: {e}")

def add_node(name: str, ip: str):
    nodes = read_nodes()
    if any(node['name'] == name for node in nodes):
        print(f"Error: A node with the name '{name}' already exists.", file=sys.stderr)
        sys.exit(1)
    if any(node['ip'] == ip for node in nodes):
        print(f"Error: A node with the IP '{ip}' already exists.", file=sys.stderr)
        sys.exit(1)
    
    nodes.append({"name": name, "ip": ip})
    write_nodes(nodes)
    print(f"Successfully added node '{name}' with IP '{ip}'.")

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
        
    print(f"{'Name':<20} {'IP Address'}")
    print(f"{'-'*20} {'-'*15}")
    for node in sorted(nodes, key=lambda x: x['name']):
        print(f"{node['name']:<20} {node['ip']}")

def main():
    parser = argparse.ArgumentParser(description="Manage external node configurations.")
    subparsers = parser.add_subparsers(dest='command', required=True)

    add_parser = subparsers.add_parser('add', help='Add a new node.')
    add_parser.add_argument('--name', type=str, required=True, help='The unique name of the node.')
    add_parser.add_argument('--ip', type=str, required=True, help='The IP address of the node.')

    delete_parser = subparsers.add_parser('delete', help='Delete a node by name.')
    delete_parser.add_argument('--name', type=str, required=True, help='The name of the node to delete.')

    subparsers.add_parser('list', help='List all configured nodes.')
    
    args = parser.parse_args()

    if args.command == 'add':
        add_node(args.name, args.ip)
    elif args.command == 'delete':
        delete_node(args.name)
    elif args.command == 'list':
        list_nodes()

if __name__ == "__main__":
    main()