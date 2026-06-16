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
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.adapters import HTTPAdapter
from dotenv import load_dotenv


TELEGRAM_ENV_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.env'))
_HTTP_POOL_CONNECTIONS = 8
_HTTP_POOL_MAXSIZE = 16
_thread_local = threading.local()


def _float_env(name, default, minimum=0.1):
    try:
        value = float(os.getenv(name, default))
    except (TypeError, ValueError):
        return float(default)
    return value if value >= minimum else float(default)


def get_api_read_timeout_seconds() -> float:
    return _float_env("DIJIQ_API_READ_TIMEOUT_SECONDS", 6)


def get_api_write_timeout_seconds() -> float:
    return _float_env("DIJIQ_API_WRITE_TIMEOUT_SECONDS", 10)


def _get_thread_session(session_key) -> requests.Session:
    """Return a per-thread pooled HTTP session for a server/auth pair."""
    sessions = getattr(_thread_local, "api_sessions", None)
    if sessions is None:
        sessions = {}
        _thread_local.api_sessions = sessions

    session = sessions.get(session_key)
    if session is None:
        session = requests.Session()
        adapter = HTTPAdapter(pool_connections=_HTTP_POOL_CONNECTIONS, pool_maxsize=_HTTP_POOL_MAXSIZE)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        sessions[session_key] = session
    return session


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
        self._session_key = (self.base_url, self.token)

    # ------------------------------------------------------------------ #
    # Private HTTP helpers                                                  #
    # ------------------------------------------------------------------ #

    @property
    def session(self) -> requests.Session:
        return _get_thread_session(self._session_key)

    def _request(self, method: str, url: str, *, data: dict | None = None, headers: dict | None = None, timeout: float | None = None):
        request_headers = {**self.headers}
        if headers:
            request_headers.update(headers)
        timeout = timeout if timeout is not None else get_api_read_timeout_seconds()
        return self.session.request(method, url, headers=request_headers, json=data, timeout=timeout)

    def _get(self, url: str):
        try:
            response = self._request("GET", url, timeout=get_api_read_timeout_seconds())
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"[APIClient] GET {url} failed: {e}")
            return None

    def _post(self, url: str, data: dict):
        try:
            response = self._request("POST", url, data=data, headers={'Content-Type': 'application/json'}, timeout=get_api_write_timeout_seconds())
            response.raise_for_status()
            try:
                return response.json()
            except ValueError:
                return response.text or True
        except requests.exceptions.RequestException as e:
            print(f"[APIClient] POST {url} failed: {e}")
            return None

    def _patch(self, url: str, data: dict):
        try:
            response = self._request("PATCH", url, data=data, headers={'Content-Type': 'application/json'}, timeout=get_api_write_timeout_seconds())
            response.raise_for_status()
            MultiServerAPI.invalidate_all_caches()
            try:
                return response.json()
            except ValueError:
                return {"message": "Updated successfully."}
        except requests.exceptions.RequestException as e:
            print(f"[APIClient] PATCH {url} failed: {e}")
            return None

    def _delete(self, url: str):
        try:
            response = self._request("DELETE", url, timeout=get_api_write_timeout_seconds())
            response.raise_for_status()
            MultiServerAPI.invalidate_all_caches()
            try:
                return response.json()
            except ValueError:
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
        result = self._post(self.users_endpoint, payload)
        if result is not None:
            MultiServerAPI.record_created_user(self.server_id, username)
        return result

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
            response = self._request(
                "GET",
                "http://127.0.0.1:25413/online",
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

    _creation_cache_lock = threading.RLock()
    _creation_write_lock = threading.RLock()
    _creation_refresh_lock = threading.Lock()
    _user_snapshot_refresh_lock = threading.Lock()
    _creation_cache = None
    _user_snapshot_cache = {}

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
    def _max_parallel_workers(server_count: int) -> int:
        try:
            configured = int(os.getenv("SERVER_FETCH_WORKERS", "8"))
        except (TypeError, ValueError):
            configured = 8
        return max(1, min(server_count, configured))

    def _client_entries(self, include_disabled: bool = False) -> list[dict]:
        entries = []
        for server in self.servers:
            if include_disabled or server.get("enabled", True):
                entries.append({
                    "server": server,
                    "client": APIClient(server),
                    "index": len(entries),
                })
        return entries

    def _fetch_users_for_servers(self, include_disabled: bool = False) -> list[dict]:
        entries = self._client_entries(include_disabled=include_disabled)
        if len(entries) <= 1 or self._max_parallel_workers(len(entries)) == 1:
            for entry in entries:
                entry["users"] = entry["client"].get_users()
            return entries

        results = [None] * len(entries)

        def fetch_users(entry):
            return {**entry, "users": entry["client"].get_users()}

        with ThreadPoolExecutor(max_workers=self._max_parallel_workers(len(entries)), thread_name_prefix="dijiq-api") as executor:
            future_to_index = {executor.submit(fetch_users, entry): index for index, entry in enumerate(entries)}
            for future in as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    results[index] = future.result()
                except Exception as e:
                    entry = entries[index]
                    print(f"[MultiServerAPI] Fetch users for {entry['server'].get('id')} failed: {e}")
                    results[index] = {**entry, "users": None}

        return results

    def _build_user_snapshot(self, include_disabled: bool = False) -> dict:
        return {
            "created_at": time.monotonic(),
            "signature": (bool(include_disabled), self._servers_signature(self.servers)),
            "include_disabled": bool(include_disabled),
            "entries": self._fetch_users_for_servers(include_disabled=include_disabled),
        }

    def _get_user_snapshot(
        self,
        include_disabled: bool = False,
        force_refresh: bool = False,
        cache_ttl_seconds: float | None = None,
    ) -> dict:
        signature = (bool(include_disabled), self._servers_signature(self.servers))
        ttl = self._user_snapshot_cache_ttl_seconds(cache_ttl_seconds)
        now = time.monotonic()
        cache_key = bool(include_disabled)

        with self._creation_cache_lock:
            cached = self.__class__._user_snapshot_cache.get(cache_key)
            if (
                not force_refresh
                and cached is not None
                and cached.get("signature") == signature
                and ttl > 0
                and now - cached.get("created_at", 0) < ttl
            ):
                self.last_user_snapshot_cache_hit = True
                return cached

            has_matching_cached = cached is not None and cached.get("signature") == signature

        refresh_acquired = self.__class__._user_snapshot_refresh_lock.acquire(blocking=not has_matching_cached or force_refresh)
        if not refresh_acquired:
            self.last_user_snapshot_cache_hit = True
            return cached

        try:
            now = time.monotonic()
            with self._creation_cache_lock:
                cached = self.__class__._user_snapshot_cache.get(cache_key)
                if (
                    not force_refresh
                    and cached is not None
                    and cached.get("signature") == signature
                    and ttl > 0
                    and now - cached.get("created_at", 0) < ttl
                ):
                    self.last_user_snapshot_cache_hit = True
                    return cached

            snapshot = self._build_user_snapshot(include_disabled=include_disabled)
            with self._creation_cache_lock:
                self.__class__._user_snapshot_cache[cache_key] = snapshot
            self.last_user_snapshot_cache_hit = False
            return snapshot
        finally:
            self.__class__._user_snapshot_refresh_lock.release()

    @classmethod
    def invalidate_read_snapshot_cache(cls):
        with cls._creation_cache_lock:
            cls._user_snapshot_cache = {}

    @classmethod
    def invalidate_all_caches(cls):
        with cls._creation_cache_lock:
            cls._creation_cache = None
            cls._user_snapshot_cache = {}

    def invalidate_user_snapshot_cache(self):
        self.__class__.invalidate_read_snapshot_cache()

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

    @staticmethod
    def _creation_cache_ttl_seconds() -> float:
        load_dotenv(TELEGRAM_ENV_PATH)
        try:
            ttl = float(os.getenv("SERVER_USERS_CACHE_TTL_SECONDS", "30"))
        except (TypeError, ValueError):
            return 30.0
        return max(0.0, ttl)

    @classmethod
    def _user_snapshot_cache_ttl_seconds(cls, cache_ttl_seconds: float | None = None) -> float:
        if cache_ttl_seconds is None:
            return cls._creation_cache_ttl_seconds()
        try:
            ttl = float(cache_ttl_seconds)
        except (TypeError, ValueError):
            return cls._creation_cache_ttl_seconds()
        return max(0.0, ttl)

    @staticmethod
    def _servers_signature(servers: list[dict]):
        return tuple(
            (
                server.get("id"),
                server.get("url"),
                server.get("token"),
                bool(server.get("enabled", True)),
                _safe_weight(server.get("weight", 1)),
            )
            for server in servers
        )

    def _build_creation_snapshot(self, force_refresh: bool = False) -> dict:
        usernames = set()
        server_states = []

        for entry in self._get_user_snapshot(include_disabled=False, force_refresh=force_refresh).get("entries", []):
            server = entry["server"]
            client = entry["client"]
            users = entry["users"]
            healthy = users is not None
            active_count = self.active_user_count(users) if healthy else None
            weight = _safe_weight(server.get("weight", 1))
            if healthy:
                usernames.update(self.extract_usernames(users))
            server_states.append({
                "server": server,
                "client": client,
                "index": entry["index"],
                "healthy": healthy,
                "active_count": active_count,
                "weight": weight,
                "load_ratio": (active_count / weight) if healthy else None,
            })

        return {
            "created_at": time.monotonic(),
            "signature": self._servers_signature(self.servers),
            "usernames": usernames,
            "servers": server_states,
        }

    def _get_creation_snapshot(self, force_refresh: bool = False) -> dict:
        signature = self._servers_signature(self.servers)
        ttl = self._creation_cache_ttl_seconds()
        now = time.monotonic()

        with self._creation_cache_lock:
            cached = self.__class__._creation_cache
            if (
                not force_refresh
                and cached is not None
                and cached.get("signature") == signature
                and ttl > 0
                and now - cached.get("created_at", 0) < ttl
            ):
                return cached

        with self.__class__._creation_refresh_lock:
            now = time.monotonic()
            with self._creation_cache_lock:
                cached = self.__class__._creation_cache
                if (
                    not force_refresh
                    and cached is not None
                    and cached.get("signature") == signature
                    and ttl > 0
                    and now - cached.get("created_at", 0) < ttl
                ):
                    return cached

            snapshot = self._build_creation_snapshot(force_refresh=force_refresh)
            with self._creation_cache_lock:
                self.__class__._creation_cache = snapshot
            return snapshot

    def invalidate_creation_cache(self):
        self.__class__.invalidate_all_caches()

    def prepare_new_user_creation(self, force_refresh: bool = False) -> dict:
        snapshot = self._get_creation_snapshot(force_refresh=force_refresh)
        candidates = []
        for state in snapshot.get("servers", []):
            if not state.get("healthy"):
                continue
            candidates.append((state["load_ratio"], state["index"], state["client"]))

        selected_client = None
        if candidates:
            candidates.sort(key=lambda item: (item[0], item[1]))
            selected_client = candidates[0][2]

        return {
            "client": selected_client,
            "existing_usernames": set(snapshot.get("usernames", set())),
            "server_states": list(snapshot.get("servers", [])),
        }

    @classmethod
    def record_created_user(cls, server_id: str, username: str):
        if not username:
            return
        with cls._creation_cache_lock:
            cls._user_snapshot_cache = {}
            cached = cls._creation_cache
            if cached is None:
                return
            usernames = cached.setdefault("usernames", set())
            if username in usernames:
                return
            usernames.add(username)
            for state in cached.get("servers", []):
                client = state.get("client")
                state_server_id = getattr(client, "server_id", None) or (state.get("server") or {}).get("id")
                if state_server_id != server_id:
                    continue
                if state.get("healthy"):
                    state["active_count"] = int(state.get("active_count") or 0) + 1
                    weight = _safe_weight(state.get("weight", 1))
                    state["load_ratio"] = state["active_count"] / weight
                break

    def create_user_with_retry(self, username_allocator, creator, fallback_client: APIClient | None = None):
        with self.__class__._creation_write_lock:
            last_username = None
            last_client = None

            for attempt in range(2):
                creation = self.prepare_new_user_creation(force_refresh=attempt > 0)
                target_client = creation.get("client") or fallback_client
                if target_client is None:
                    return None, None, None

                existing_usernames = set(creation.get("existing_usernames") or set())
                if not existing_usernames and fallback_client is not None and target_client is fallback_client:
                    users = fallback_client.get_users()
                    existing_usernames = self.extract_usernames(users)

                username = username_allocator(existing_usernames)
                result = creator(target_client, username)
                last_username = username
                last_client = target_client
                if result is not None:
                    self.record_created_user(target_client.server_id, username)
                    return username, result, target_client

                self.invalidate_creation_cache()

            return last_username, None, last_client

    def get_server_statuses(self) -> list[dict]:
        statuses = []
        for entry in self._fetch_users_for_servers(include_disabled=True):
            server = entry["server"]
            users = entry["users"]
            healthy = users is not None
            active_count = self.active_user_count(users)
            weight = _safe_weight(server.get("weight", 1))
            statuses.append({
                **server,
                "index": entry["index"],
                "healthy": healthy,
                "active_count": active_count if healthy else None,
                "load_ratio": (active_count / weight) if healthy else None,
            })
        return statuses

    def select_server_for_new_user(self) -> APIClient | None:
        return self.prepare_new_user_creation().get("client")

    def get_all_usernames(self) -> set[str]:
        usernames = set()
        for entry in self._get_user_snapshot(include_disabled=True).get("entries", []):
            users = entry["users"]
            if users is not None:
                usernames.update(self.extract_usernames(users))
        return usernames

    def get_user_snapshot_entries(
        self,
        include_disabled: bool = True,
        force_refresh: bool = False,
        cache_ttl_seconds: float | None = None,
    ) -> list[dict]:
        return list(
            self._get_user_snapshot(
                include_disabled=include_disabled,
                force_refresh=force_refresh,
                cache_ttl_seconds=cache_ttl_seconds,
            ).get("entries", [])
        )

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

    def iter_all_users(
        self,
        include_disabled: bool = True,
        force_refresh: bool = False,
        cache_ttl_seconds: float | None = None,
    ):
        for entry in self._get_user_snapshot(
            include_disabled=include_disabled,
            force_refresh=force_refresh,
            cache_ttl_seconds=cache_ttl_seconds,
        ).get("entries", []):
            client = entry["client"]
            users = entry["users"]
            if users is None:
                continue
            if isinstance(users, dict):
                for username, data in users.items():
                    yield client, username, data
            elif isinstance(users, list):
                for data in users:
                    if isinstance(data, dict):
                        yield client, data.get("username"), data
