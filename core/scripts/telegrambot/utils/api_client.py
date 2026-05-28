"""
Unified API client for all dijiq REST API interactions.

This is the single source of truth for all HTTP communication with the dijiq
backend. Import ``APIClient`` from here instead of from individual handler
modules (adduser, edituser, deleteuser, …).

All public methods return parsed JSON data (dict / list / str) on success,
or ``None`` on any failure (network error, 4xx, 5xx).  Callers should check
``if result is None`` to detect failures.
"""

import json
import os
import requests
from dotenv import load_dotenv


TELEGRAM_ENV_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.env'))


def _safe_server_id(value: str, fallback: str = "primary") -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in ("_", "-") else "_" for ch in str(value or "").strip())
    return cleaned or fallback


def _safe_weight(value) -> float:
    try:
        weight = float(value)
    except (TypeError, ValueError):
        return 1.0
    return weight if weight > 0 else 1.0


def _normalise_server_config(config: dict, index: int = 0) -> dict | None:
    if not isinstance(config, dict):
        return None
    url = str(config.get("url") or config.get("URL") or "").strip()
    token = str(config.get("token") or config.get("TOKEN") or "").strip()
    if not url or not token:
        return None
    server_id = _safe_server_id(config.get("id") or config.get("name") or f"server{index + 1}")
    return {
        "id": server_id,
        "name": str(config.get("name") or server_id),
        "url": url,
        "token": token,
        "enabled": bool(config.get("enabled", True)),
        "weight": _safe_weight(config.get("weight", 1)),
    }


def get_server_configs() -> list[dict]:
    """Load configured VPN API servers.

    ``SERVERS_JSON`` is the multi-server source of truth. Legacy ``URL`` and
    ``TOKEN`` remain supported as a single primary server fallback.
    """
    load_dotenv(TELEGRAM_ENV_PATH)
    raw_servers = os.getenv("SERVERS_JSON", "").strip()
    servers: list[dict] = []
    if raw_servers:
        try:
            parsed = json.loads(raw_servers)
            if isinstance(parsed, list):
                for index, item in enumerate(parsed):
                    normalized = _normalise_server_config(item, index)
                    if normalized:
                        servers.append(normalized)
        except json.JSONDecodeError as e:
            print(f"Warning: invalid SERVERS_JSON: {e}")

    if servers:
        return servers

    base_url = os.getenv('URL', '')
    token = os.getenv('TOKEN', '')
    fallback = _normalise_server_config(
        {"id": "primary", "name": "Primary", "url": base_url, "token": token, "enabled": True, "weight": 1},
        0,
    )
    return [fallback] if fallback else []


def save_server_configs(servers: list[dict]) -> bool:
    """Persist server configs to the Telegram bot .env file."""
    normalized = []
    for index, item in enumerate(servers):
        config = _normalise_server_config(item, index)
        if config:
            normalized.append(config)
    if not normalized:
        return False

    os.makedirs(os.path.dirname(TELEGRAM_ENV_PATH), exist_ok=True)
    existing_lines = []
    if os.path.exists(TELEGRAM_ENV_PATH):
        with open(TELEGRAM_ENV_PATH, "r") as f:
            existing_lines = f.readlines()

    updates = {
        "SERVERS_JSON": json.dumps(normalized, separators=(",", ":")),
        "URL": normalized[0]["url"],
        "TOKEN": normalized[0]["token"],
    }
    seen = set()
    new_lines = []
    for line in existing_lines:
        key = line.split("=", 1)[0].strip() if "=" in line else None
        if key in updates:
            new_lines.append(f"{key}={updates[key]}\n")
            seen.add(key)
        else:
            new_lines.append(line)
    for key, value in updates.items():
        if key not in seen:
            new_lines.append(f"{key}={value}\n")

    with open(TELEGRAM_ENV_PATH, "w") as f:
        f.writelines(new_lines)
    os.environ["SERVERS_JSON"] = updates["SERVERS_JSON"]
    os.environ["URL"] = updates["URL"]
    os.environ["TOKEN"] = updates["TOKEN"]
    return True


class APIClient:
    """HTTP client for the dijiq REST API."""

    def __init__(self, server_config: dict | None = None):
        load_dotenv(TELEGRAM_ENV_PATH)

        server_config = _normalise_server_config(server_config or {}, 0) if server_config else None
        base_url: str = server_config["url"] if server_config else os.getenv('URL', '')
        self.token: str = server_config["token"] if server_config else os.getenv('TOKEN', '')
        self.server_id: str = server_config["id"] if server_config else "primary"
        self.server_name: str = server_config["name"] if server_config else "Primary"

        if not base_url or not self.token:
            print("Warning: API URL or TOKEN not found in environment variables.")

        # Normalise: ensure exactly one trailing slash
        self.base_url = base_url.rstrip('/') + '/'
        self.users_endpoint = f"{self.base_url}api/v1/users/"

        self.headers = {
            'accept': 'application/json',
            'Authorization': self.token,
        }

    # ------------------------------------------------------------------ #
    # Private HTTP helpers                                                  #
    # ------------------------------------------------------------------ #

    def _get(self, url: str):
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"[APIClient] GET {url} failed: {e}")
            return None

    def _post(self, url: str, data: dict):
        headers = {**self.headers, 'Content-Type': 'application/json'}
        try:
            response = requests.post(url, headers=headers, json=data, timeout=10)
            response.raise_for_status()
            try:
                return response.json()
            except json.JSONDecodeError:
                return response.text or True
        except requests.exceptions.RequestException as e:
            print(f"[APIClient] POST {url} failed: {e}")
            return None

    def _patch(self, url: str, data: dict):
        headers = {**self.headers, 'Content-Type': 'application/json'}
        try:
            response = requests.patch(url, headers=headers, json=data, timeout=10)
            response.raise_for_status()
            try:
                return response.json()
            except json.JSONDecodeError:
                return {"message": "Updated successfully."}
        except requests.exceptions.RequestException as e:
            print(f"[APIClient] PATCH {url} failed: {e}")
            return None

    def _delete(self, url: str):
        try:
            response = requests.delete(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            try:
                return response.json()
            except json.JSONDecodeError:
                return {"message": "Deleted successfully."}
        except requests.exceptions.RequestException as e:
            print(f"[APIClient] DELETE {url} failed: {e}")
            return None

    # ------------------------------------------------------------------ #
    # User operations                                                       #
    # ------------------------------------------------------------------ #

    def get_users(self):
        """Return list or dict of all users, or ``None`` on failure."""
        return self._get(self.users_endpoint)

    def get_user(self, username: str):
        """Return a single user's detail dict, or ``None`` if not found / on failure."""
        return self._get(f"{self.users_endpoint}{username}")

    def add_user(self, username: str, traffic_limit: int, expiration_days: int, unlimited: bool = False, note: str | None = None):
        """Create a new user. Returns response data or ``None`` on failure."""
        payload = {
            "username": username,
            "traffic_limit": traffic_limit,
            "expiration_days": expiration_days,
            "unlimited": unlimited,
        }
        if note is not None:
            payload["note"] = note
        return self._post(self.users_endpoint, payload)

    def update_user(self, username: str, data: dict):
        """Patch one or more fields of an existing user.

        Returns the API response dict, or ``None`` on failure.
        """
        return self._patch(f"{self.users_endpoint}{username}", data)

    def reset_user(self, username: str):
        """Renew a user's creation date and unblock them."""
        return self.update_user(username, {"renew_creation_date": True, "blocked": False})

    def delete_user(self, username: str):
        """Delete a user. Returns response data or ``None`` on failure."""
        return self._delete(f"{self.users_endpoint}{username}")

    def get_user_uri(self, username: str):
        """Return subscription URI data dict, or ``None`` on failure."""
        return self._get(f"{self.base_url}api/v1/users/{username}/uri")

    # ------------------------------------------------------------------ #
    # Server / stats operations                                             #
    # ------------------------------------------------------------------ #

    def get_online_users(self) -> int:
        """Return the total number of currently online users, or 0 on failure.

        This calls the Hysteria2 local stats endpoint rather than the main
        REST API, but uses the same auth token.
        """
        try:
            response = requests.get(
                "http://127.0.0.1:25413/online",
                headers={'Authorization': self.token},
                timeout=5,
            )
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, dict):
                    return sum(data.values())
                if isinstance(data, list):
                    return sum(data)
        except Exception:
            pass
        return 0


class MultiServerAPI:
    """Coordinates API operations across configured VPN servers."""

    def __init__(self):
        self.servers = get_server_configs()

    def get_client(self, server_id: str | None = None) -> APIClient | None:
        if not self.servers:
            return None
        if server_id:
            for server in self.servers:
                if server["id"] == server_id:
                    return APIClient(server)
        return APIClient(self.servers[0])

    def iter_clients(self, include_disabled: bool = False):
        for server in self.servers:
            if include_disabled or server.get("enabled", True):
                yield server, APIClient(server)

    @staticmethod
    def active_user_count(users) -> int:
        count = 0
        if isinstance(users, dict):
            iterable = users.values()
        elif isinstance(users, list):
            iterable = users
        else:
            return 0
        for user in iterable:
            if isinstance(user, dict) and not bool(user.get("blocked", False)):
                count += 1
        return count

    @staticmethod
    def extract_usernames(users) -> set[str]:
        names = set()
        if isinstance(users, dict):
            names.update(str(name) for name in users.keys() if name)
        elif isinstance(users, list):
            for item in users:
                if isinstance(item, dict) and item.get("username"):
                    names.add(str(item["username"]))
        return names

    def get_server_statuses(self) -> list[dict]:
        statuses = []
        for index, (server, client) in enumerate(self.iter_clients(include_disabled=True)):
            users = client.get_users()
            healthy = users is not None
            active_count = self.active_user_count(users)
            weight = _safe_weight(server.get("weight", 1))
            statuses.append({
                **server,
                "index": index,
                "healthy": healthy,
                "active_count": active_count if healthy else None,
                "load_ratio": (active_count / weight) if healthy else None,
            })
        return statuses

    def select_server_for_new_user(self) -> APIClient | None:
        candidates = []
        for index, (server, client) in enumerate(self.iter_clients(include_disabled=False)):
            users = client.get_users()
            if users is None:
                continue
            active_count = self.active_user_count(users)
            ratio = active_count / _safe_weight(server.get("weight", 1))
            candidates.append((ratio, index, client))
        if not candidates:
            return None
        candidates.sort(key=lambda item: (item[0], item[1]))
        return candidates[0][2]

    def get_all_usernames(self) -> set[str]:
        usernames = set()
        for _, client in self.iter_clients(include_disabled=True):
            users = client.get_users()
            if users is not None:
                usernames.update(self.extract_usernames(users))
        return usernames

    def find_user(self, username: str, preferred_server_id: str | None = None):
        if preferred_server_id:
            client = self.get_client(preferred_server_id)
            if client:
                user = client.get_user(username)
                if user is not None:
                    return client, user
        for _, client in self.iter_clients(include_disabled=True):
            if preferred_server_id and client.server_id == preferred_server_id:
                continue
            user = client.get_user(username)
            if user is not None:
                return client, user
        return None, None

    def iter_all_users(self):
        for _, client in self.iter_clients(include_disabled=True):
            users = client.get_users()
            if users is None:
                continue
            if isinstance(users, dict):
                for username, data in users.items():
                    yield client, username, data
            elif isinstance(users, list):
                for data in users:
                    if isinstance(data, dict):
                        yield client, data.get("username"), data
