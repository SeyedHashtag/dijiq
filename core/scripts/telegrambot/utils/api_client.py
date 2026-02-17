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


class APIClient:
    """HTTP client for the dijiq REST API."""

    def __init__(self):
        load_dotenv()

        base_url: str = os.getenv('URL', '')
        self.token: str = os.getenv('TOKEN', '')

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

    def add_user(self, username: str, traffic_limit: int, expiration_days: int, unlimited: bool = False):
        """Create a new user. Returns response data or ``None`` on failure."""
        return self._post(self.users_endpoint, {
            "username": username,
            "traffic_limit": traffic_limit,
            "expiration_days": expiration_days,
            "unlimited": unlimited,
        })

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
