import sys
import json
from pathlib import Path

try:
    from hysteria2_api import Hysteria2Client
except ImportError:
    sys.exit("Error: hysteria2_api library not found. Please install it.")

sys.path.append(str(Path(__file__).parent.parent))
from paths import USERS_FILE, CONFIG_FILE, API_BASE_URL

def get_secret() -> str | None:
    if not CONFIG_FILE.exists():
        return None
    try:
        with CONFIG_FILE.open('r') as f:
            config_data = json.load(f)
        return config_data.get("trafficStats", {}).get("secret")
    except (json.JSONDecodeError, IOError):
        return None

def get_users() -> dict:
    if not USERS_FILE.exists():
        return {}
    try:
        with USERS_FILE.open('r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}

def main():
    users_dict = get_users()
    secret = get_secret()

    if secret and users_dict:
        try:
            client = Hysteria2Client(base_url=API_BASE_URL, secret=secret)
            online_clients = client.get_online_clients()
            
            for username, status in online_clients.items():
                if status.is_online and username in users_dict:
                    users_dict[username]['online_count'] = status.connections
        except Exception:
            pass

    users_list = [
        {**user_data, 'username': username, 'online_count': user_data.get('online_count', 0)}
        for username, user_data in users_dict.items()
    ]

    print(json.dumps(users_list, indent=2))

if __name__ == "__main__":
    main()