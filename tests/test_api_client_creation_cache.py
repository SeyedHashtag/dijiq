import importlib.util
import os
import sys
import tempfile
import threading
import time
import types
import unittest
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "core"
    / "scripts"
    / "telegrambot"
    / "utils"
    / "api_client.py"
)

spec = importlib.util.spec_from_file_location("api_client_under_test", MODULE_PATH)
api_client = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = api_client
if "dotenv" not in sys.modules:
    dotenv_stub = types.ModuleType("dotenv")
    dotenv_stub.load_dotenv = lambda *args, **kwargs: None
    sys.modules["dotenv"] = dotenv_stub
spec.loader.exec_module(api_client)


class FakeClient:
    def __init__(self, server_id, users, add_results=None, delay=0):
        self.server_id = server_id
        self.server_name = server_id
        self.users = users
        self.add_results = list(add_results or [])
        self.delay = delay
        self.get_users_calls = 0
        self.add_user_calls = []

    def get_users(self):
        self.get_users_calls += 1
        if self.delay:
            time.sleep(self.delay)
        return self.users

    def add_user(self, username, traffic_limit, expiration_days, unlimited=False, note=None):
        self.add_user_calls.append({
            "username": username,
            "traffic_limit": traffic_limit,
            "expiration_days": expiration_days,
            "unlimited": unlimited,
            "note": note,
        })
        if self.add_results:
            return self.add_results.pop(0)
        return {"created": True}


class MultiServerCreationCacheTests(unittest.TestCase):
    def setUp(self):
        self.original_api_client = api_client.APIClient
        self.original_get_server_configs = api_client.get_server_configs
        self.original_monotonic = api_client.time.monotonic
        self.original_ttl = os.environ.get("SERVER_USERS_CACHE_TTL_SECONDS")
        self.original_workers = os.environ.get("SERVER_FETCH_WORKERS")
        self.original_read_timeout = os.environ.get("DIJIQ_API_READ_TIMEOUT_SECONDS")
        self.original_write_timeout = os.environ.get("DIJIQ_API_WRITE_TIMEOUT_SECONDS")
        os.environ["SERVER_USERS_CACHE_TTL_SECONDS"] = "30"
        api_client.MultiServerAPI._creation_cache = None
        api_client.MultiServerAPI._user_snapshot_cache = {}

    def tearDown(self):
        api_client.APIClient = self.original_api_client
        api_client.get_server_configs = self.original_get_server_configs
        api_client.time.monotonic = self.original_monotonic
        api_client.MultiServerAPI._creation_cache = None
        api_client.MultiServerAPI._user_snapshot_cache = {}
        if self.original_ttl is None:
            os.environ.pop("SERVER_USERS_CACHE_TTL_SECONDS", None)
        else:
            os.environ["SERVER_USERS_CACHE_TTL_SECONDS"] = self.original_ttl
        if self.original_workers is None:
            os.environ.pop("SERVER_FETCH_WORKERS", None)
        else:
            os.environ["SERVER_FETCH_WORKERS"] = self.original_workers
        if self.original_read_timeout is None:
            os.environ.pop("DIJIQ_API_READ_TIMEOUT_SECONDS", None)
        else:
            os.environ["DIJIQ_API_READ_TIMEOUT_SECONDS"] = self.original_read_timeout
        if self.original_write_timeout is None:
            os.environ.pop("DIJIQ_API_WRITE_TIMEOUT_SECONDS", None)
        else:
            os.environ["DIJIQ_API_WRITE_TIMEOUT_SECONDS"] = self.original_write_timeout

    def make_multi_api(self, clients):
        servers = [
            {"id": server_id, "name": server_id, "url": f"https://{server_id}.test", "token": "token", "enabled": True, "weight": 1}
            for server_id in clients
        ]
        api_client.get_server_configs = lambda: servers
        api_client.APIClient = lambda server: clients[server["id"]]
        return api_client.MultiServerAPI()

    def test_cached_snapshot_serves_selection_and_usernames(self):
        clients = {
            "s1": FakeClient("s1", {
                "a": {"blocked": False},
                "b": {"blocked": False},
            }),
            "s2": FakeClient("s2", {
                "c": {"blocked": True},
            }),
        }
        multi_api = self.make_multi_api(clients)

        creation = multi_api.prepare_new_user_creation()
        selected = multi_api.select_server_for_new_user()

        self.assertEqual(creation["client"].server_id, "s2")
        self.assertEqual(selected.server_id, "s2")
        self.assertEqual(creation["existing_usernames"], {"a", "b", "c"})
        self.assertEqual(clients["s1"].get_users_calls, 1)
        self.assertEqual(clients["s2"].get_users_calls, 1)

    def test_cached_snapshot_prevents_repeated_get_users_inside_ttl(self):
        clients = {
            "s1": FakeClient("s1", {"a": {"blocked": False}}),
            "s2": FakeClient("s2", {}),
        }
        multi_api = self.make_multi_api(clients)

        multi_api.prepare_new_user_creation()
        multi_api.prepare_new_user_creation()
        multi_api.select_server_for_new_user()

        self.assertEqual(clients["s1"].get_users_calls, 1)
        self.assertEqual(clients["s2"].get_users_calls, 1)

    def test_cached_snapshot_expires_after_ttl(self):
        current_time = [100.0]
        api_client.time.monotonic = lambda: current_time[0]
        clients = {
            "s1": FakeClient("s1", {"a": {"blocked": False}}),
            "s2": FakeClient("s2", {}),
        }
        multi_api = self.make_multi_api(clients)

        multi_api.prepare_new_user_creation()
        current_time[0] = 129.0
        multi_api.prepare_new_user_creation()
        current_time[0] = 131.0
        multi_api.prepare_new_user_creation()

        self.assertEqual(clients["s1"].get_users_calls, 2)
        self.assertEqual(clients["s2"].get_users_calls, 2)

    def test_force_refresh_creation_snapshot_bypasses_user_snapshot_cache(self):
        clients = {
            "s1": FakeClient("s1", {"a": {"blocked": False}}),
            "s2": FakeClient("s2", {}),
        }
        multi_api = self.make_multi_api(clients)

        multi_api.prepare_new_user_creation()
        multi_api.prepare_new_user_creation(force_refresh=True)

        self.assertEqual(clients["s1"].get_users_calls, 2)
        self.assertEqual(clients["s2"].get_users_calls, 2)

    def test_record_created_user_updates_cached_usernames_and_load(self):
        clients = {
            "s1": FakeClient("s1", {"a": {"blocked": False}}),
            "s2": FakeClient("s2", {}),
        }
        multi_api = self.make_multi_api(clients)

        self.assertEqual(multi_api.prepare_new_user_creation()["client"].server_id, "s2")
        multi_api.record_created_user("s2", "newuser")
        creation = multi_api.prepare_new_user_creation()

        self.assertEqual(creation["client"].server_id, "s1")
        self.assertIn("newuser", creation["existing_usernames"])
        self.assertEqual(clients["s1"].get_users_calls, 1)
        self.assertEqual(clients["s2"].get_users_calls, 1)

    def test_record_created_user_invalidates_read_snapshots_and_is_idempotent(self):
        clients = {
            "s1": FakeClient("s1", {}),
            "s2": FakeClient("s2", {}),
        }
        multi_api = self.make_multi_api(clients)
        multi_api.prepare_new_user_creation()
        api_client.MultiServerAPI._user_snapshot_cache = {True: {"stale": True}}

        api_client.MultiServerAPI.record_created_user("s1", "newuser")
        api_client.MultiServerAPI.record_created_user("s1", "newuser")
        creation = multi_api.prepare_new_user_creation()

        self.assertEqual(api_client.MultiServerAPI._user_snapshot_cache, {})
        self.assertIn("newuser", creation["existing_usernames"])
        server_state = next(state for state in creation["server_states"] if state["client"].server_id == "s1")
        self.assertEqual(server_state["active_count"], 1)

    def test_rapid_create_user_with_retry_allocates_distinct_usernames_inside_ttl(self):
        def run_prefix(prefix):
            api_client.MultiServerAPI._creation_cache = None
            api_client.MultiServerAPI._user_snapshot_cache = {}
            clients = {
                "s1": FakeClient("s1", {}),
                "s2": FakeClient("s2", {}),
            }
            multi_api = self.make_multi_api(clients)

            def allocate(existing_usernames):
                base = f"{prefix}123"
                for suffix in ("", "a", "b", "c"):
                    username = f"{base}{suffix}"
                    if username not in existing_usernames:
                        return username
                raise AssertionError("no username available")

            created = []
            for _ in range(3):
                username, result, _client = multi_api.create_user_with_retry(
                    allocate,
                    lambda target_client, candidate: target_client.add_user(candidate, 1, 30),
                )
                created.append(username)
                self.assertEqual(result, {"created": True})

            self.assertEqual(created, [f"{prefix}123", f"{prefix}123a", f"{prefix}123b"])
            self.assertEqual(clients["s1"].get_users_calls, 1)
            self.assertEqual(clients["s2"].get_users_calls, 1)

        for prefix in ("s", "r", "t"):
            with self.subTest(prefix=prefix):
                run_prefix(prefix)

    def test_create_user_with_retry_invalidates_cache_and_retries_once(self):
        clients = {
            "s1": FakeClient("s1", {}, add_results=[None, {"created": True}]),
            "s2": FakeClient("s2", {"existing": {"blocked": False}}),
        }
        multi_api = self.make_multi_api(clients)

        username, result, client = multi_api.create_user_with_retry(
            lambda existing_usernames: "newuser",
            lambda target_client, username: target_client.add_user(username, 1, 30),
        )

        self.assertEqual(username, "newuser")
        self.assertEqual(result, {"created": True})
        self.assertEqual(client.server_id, "s1")
        self.assertEqual(len(clients["s1"].add_user_calls), 2)
        self.assertEqual(clients["s1"].get_users_calls, 2)
        self.assertEqual(clients["s2"].get_users_calls, 2)

    def test_iter_all_users_can_exclude_disabled_servers_and_default_includes_them(self):
        clients = {
            "s1": FakeClient("s1", {"active": {"blocked": False}}),
            "s2": FakeClient("s2", {"disabled": {"blocked": False}}),
        }
        servers = [
            {"id": "s1", "name": "s1", "url": "https://s1.test", "token": "token", "enabled": True, "weight": 1},
            {"id": "s2", "name": "s2", "url": "https://s2.test", "token": "token", "enabled": False, "weight": 1},
        ]
        api_client.get_server_configs = lambda: servers
        api_client.APIClient = lambda server: clients[server["id"]]
        multi_api = api_client.MultiServerAPI()

        default_usernames = [username for _, username, _ in multi_api.iter_all_users()]
        enabled_usernames = [username for _, username, _ in multi_api.iter_all_users(include_disabled=False)]

        self.assertEqual(default_usernames, ["active", "disabled"])
        self.assertEqual(enabled_usernames, ["active"])

    def test_iter_all_users_reuses_cached_snapshot_inside_ttl(self):
        clients = {
            "s1": FakeClient("s1", {"active": {"blocked": False}}),
            "s2": FakeClient("s2", {"backup": {"blocked": False}}),
        }
        multi_api = self.make_multi_api(clients)

        first = [username for _, username, _ in multi_api.iter_all_users()]
        second = [username for _, username, _ in multi_api.iter_all_users()]

        self.assertEqual(first, ["active", "backup"])
        self.assertEqual(second, ["active", "backup"])
        self.assertEqual(clients["s1"].get_users_calls, 1)
        self.assertEqual(clients["s2"].get_users_calls, 1)
        self.assertTrue(multi_api.last_user_snapshot_cache_hit)

    def test_iter_all_users_default_snapshot_expires_after_default_ttl(self):
        current_time = [100.0]
        api_client.time.monotonic = lambda: current_time[0]
        clients = {
            "s1": FakeClient("s1", {"active": {"blocked": False}}),
            "s2": FakeClient("s2", {"backup": {"blocked": False}}),
        }
        multi_api = self.make_multi_api(clients)

        list(multi_api.iter_all_users())
        current_time[0] = 129.0
        list(multi_api.iter_all_users())
        current_time[0] = 131.0
        list(multi_api.iter_all_users())

        self.assertEqual(clients["s1"].get_users_calls, 2)
        self.assertEqual(clients["s2"].get_users_calls, 2)

    def test_iter_all_users_explicit_snapshot_ttl_can_reuse_longer(self):
        current_time = [100.0]
        api_client.time.monotonic = lambda: current_time[0]
        clients = {
            "s1": FakeClient("s1", {"active": {"blocked": False}}),
            "s2": FakeClient("s2", {"backup": {"blocked": False}}),
        }
        multi_api = self.make_multi_api(clients)

        list(multi_api.iter_all_users(cache_ttl_seconds=300))
        current_time[0] = 250.0
        list(multi_api.iter_all_users(cache_ttl_seconds=300))

        self.assertEqual(clients["s1"].get_users_calls, 1)
        self.assertEqual(clients["s2"].get_users_calls, 1)
        self.assertTrue(multi_api.last_user_snapshot_cache_hit)

    def test_iter_all_users_force_refresh_bypasses_cached_snapshot(self):
        clients = {
            "s1": FakeClient("s1", {"active": {"blocked": False}}),
            "s2": FakeClient("s2", {"backup": {"blocked": False}}),
        }
        multi_api = self.make_multi_api(clients)

        list(multi_api.iter_all_users())
        list(multi_api.iter_all_users(force_refresh=True))

        self.assertEqual(clients["s1"].get_users_calls, 2)
        self.assertEqual(clients["s2"].get_users_calls, 2)
        self.assertFalse(multi_api.last_user_snapshot_cache_hit)

    def test_iter_all_users_force_refresh_bypasses_explicit_snapshot_ttl(self):
        clients = {
            "s1": FakeClient("s1", {"active": {"blocked": False}}),
            "s2": FakeClient("s2", {"backup": {"blocked": False}}),
        }
        multi_api = self.make_multi_api(clients)

        list(multi_api.iter_all_users(cache_ttl_seconds=300))
        list(multi_api.iter_all_users(force_refresh=True, cache_ttl_seconds=300))

        self.assertEqual(clients["s1"].get_users_calls, 2)
        self.assertEqual(clients["s2"].get_users_calls, 2)
        self.assertFalse(multi_api.last_user_snapshot_cache_hit)

    def test_creation_snapshot_uses_default_ttl_after_longer_user_snapshot_read(self):
        current_time = [100.0]
        api_client.time.monotonic = lambda: current_time[0]
        clients = {
            "s1": FakeClient("s1", {"active": {"blocked": False}}),
            "s2": FakeClient("s2", {}),
        }
        multi_api = self.make_multi_api(clients)

        list(multi_api.iter_all_users(include_disabled=False, cache_ttl_seconds=300))
        current_time[0] = 131.0
        multi_api.prepare_new_user_creation()
        current_time[0] = 160.0
        multi_api.prepare_new_user_creation()

        self.assertEqual(clients["s1"].get_users_calls, 2)
        self.assertEqual(clients["s2"].get_users_calls, 2)

    def test_iter_all_users_cache_signature_changes_when_server_enabled_changes(self):
        clients = {
            "s1": FakeClient("s1", {"active": {"blocked": False}}),
            "s2": FakeClient("s2", {"backup": {"blocked": False}}),
        }
        servers = [
            {"id": "s1", "name": "s1", "url": "https://s1.test", "token": "token", "enabled": True, "weight": 1},
            {"id": "s2", "name": "s2", "url": "https://s2.test", "token": "token", "enabled": True, "weight": 1},
        ]
        api_client.get_server_configs = lambda: servers
        api_client.APIClient = lambda server: clients[server["id"]]

        list(api_client.MultiServerAPI().iter_all_users())
        servers[1]["enabled"] = False
        list(api_client.MultiServerAPI().iter_all_users())

        self.assertEqual(clients["s1"].get_users_calls, 2)
        self.assertEqual(clients["s2"].get_users_calls, 2)

    def test_get_all_usernames_fetches_servers_in_parallel(self):
        os.environ["SERVER_FETCH_WORKERS"] = "3"
        started_count = 0
        lock = threading.Lock()
        all_started = threading.Event()
        release = threading.Event()

        class BlockingClient(FakeClient):
            def get_users(inner_self):
                nonlocal started_count
                inner_self.get_users_calls += 1
                with lock:
                    started_count += 1
                    if started_count == 3:
                        all_started.set()
                release.wait(timeout=1)
                return inner_self.users

        clients = {
            "s1": BlockingClient("s1", {"a": {"blocked": False}}),
            "s2": BlockingClient("s2", {"b": {"blocked": False}}),
            "s3": BlockingClient("s3", {"c": {"blocked": False}}),
        }
        multi_api = self.make_multi_api(clients)
        result = {}

        worker = threading.Thread(target=lambda: result.setdefault("usernames", multi_api.get_all_usernames()))
        worker.start()

        try:
            self.assertTrue(all_started.wait(timeout=0.5))
        finally:
            release.set()
            worker.join(timeout=1)

        self.assertFalse(worker.is_alive())
        self.assertEqual(result["usernames"], {"a", "b", "c"})


class APIClientPoolingTests(unittest.TestCase):
    def setUp(self):
        self.original_session_factory = api_client.requests.Session
        self.original_thread_sessions = getattr(api_client._thread_local, "api_sessions", None)
        self.original_read_timeout = os.environ.get("DIJIQ_API_READ_TIMEOUT_SECONDS")
        self.original_write_timeout = os.environ.get("DIJIQ_API_WRITE_TIMEOUT_SECONDS")
        api_client._thread_local.api_sessions = {}
        api_client.MultiServerAPI._creation_cache = None
        api_client.MultiServerAPI._user_snapshot_cache = {}

    def tearDown(self):
        api_client.requests.Session = self.original_session_factory
        if self.original_thread_sessions is None:
            try:
                del api_client._thread_local.api_sessions
            except AttributeError:
                pass
        else:
            api_client._thread_local.api_sessions = self.original_thread_sessions
        api_client.MultiServerAPI._creation_cache = None
        api_client.MultiServerAPI._user_snapshot_cache = {}
        if self.original_read_timeout is None:
            os.environ.pop("DIJIQ_API_READ_TIMEOUT_SECONDS", None)
        else:
            os.environ["DIJIQ_API_READ_TIMEOUT_SECONDS"] = self.original_read_timeout
        if self.original_write_timeout is None:
            os.environ.pop("DIJIQ_API_WRITE_TIMEOUT_SECONDS", None)
        else:
            os.environ["DIJIQ_API_WRITE_TIMEOUT_SECONDS"] = self.original_write_timeout

    def test_clients_reuse_thread_local_session_for_same_server(self):
        sessions = []

        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {}

        class FakeSession:
            def __init__(self):
                self.request_calls = []

            def mount(self, *_args, **_kwargs):
                return None

            def request(self, method, url, **kwargs):
                self.request_calls.append((method, url, kwargs))
                return FakeResponse()

        def session_factory():
            session = FakeSession()
            sessions.append(session)
            return session

        api_client.requests.Session = session_factory
        server = {"id": "s1", "name": "s1", "url": "https://s1.test", "token": "token", "enabled": True}

        first = api_client.APIClient(server)
        second = api_client.APIClient(server)
        first.get_users()
        second.get_user("alice")

        self.assertEqual(len(sessions), 1)
        self.assertIs(first.session, second.session)
        self.assertEqual([call[0] for call in sessions[0].request_calls], ["GET", "GET"])

    def test_read_write_timeouts_and_write_invalidation_are_applied(self):
        os.environ["DIJIQ_API_READ_TIMEOUT_SECONDS"] = "2.5"
        os.environ["DIJIQ_API_WRITE_TIMEOUT_SECONDS"] = "7.5"
        sessions = []

        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {"ok": True}

        class FakeSession:
            def __init__(self):
                self.request_calls = []

            def mount(self, *_args, **_kwargs):
                return None

            def request(self, method, url, **kwargs):
                self.request_calls.append((method, url, kwargs))
                return FakeResponse()

        def session_factory():
            session = FakeSession()
            sessions.append(session)
            return session

        api_client.requests.Session = session_factory
        server = {"id": "s1", "name": "s1", "url": "https://s1.test", "token": "token", "enabled": True}
        client = api_client.APIClient(server)

        client.get_users()
        api_client.MultiServerAPI._creation_cache = {"usernames": set(), "servers": [], "signature": ()}
        api_client.MultiServerAPI._user_snapshot_cache = {True: {"stale": True}}
        client.update_user("alice", {"blocked": True})
        api_client.MultiServerAPI._creation_cache = {"usernames": set(), "servers": [], "signature": ()}
        api_client.MultiServerAPI._user_snapshot_cache = {True: {"stale": True}}
        client.delete_user("alice")

        self.assertEqual(sessions[0].request_calls[0][2]["timeout"], 2.5)
        self.assertEqual(sessions[0].request_calls[1][2]["timeout"], 7.5)
        self.assertEqual(sessions[0].request_calls[2][2]["timeout"], 7.5)
        self.assertIsNone(api_client.MultiServerAPI._creation_cache)
        self.assertEqual(api_client.MultiServerAPI._user_snapshot_cache, {})


class ServerConfigPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.original_env_path = api_client.TELEGRAM_ENV_PATH
        self.original_env_values = {
            key: os.environ.get(key)
            for key in ("SERVERS_JSON", "URL", "TOKEN")
        }

    def tearDown(self):
        api_client.TELEGRAM_ENV_PATH = self.original_env_path
        for key, value in self.original_env_values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_save_server_configs_preserves_payment_and_checker_settings(self):
        preserved_values = {
            "API_TOKEN": "bot-token",
            "ADMIN_USER_IDS": "[123,456]",
            "CRYPTO_API_KEY": "crypto-key",
            "CARD_TO_CARD_NUMBER": "1111222233334444",
            "CARD_TO_CARD_CHECKER_NUMBER": "5555666677778888",
            "RECEIPT_CHECKER_USER_ID": "987654",
            "RECEIPT_CHECKER_TYPES": "regular,settlement",
            "RECEIPT_CHECKER_SHARE_PERCENT": "10",
            "EXCHANGE_RATE": "58000",
            "CARD_TO_CARD_MODE": "checker",
        }
        initial_lines = [
            "URL=https://old.example\n",
            "TOKEN=old-token\n",
            "SERVERS_JSON=[]\n",
            *[f"{key}={value}\n" for key, value in preserved_values.items()],
        ]
        new_servers = [
            {"id": "primary", "name": "Primary", "url": "https://one.example", "token": "token-one", "enabled": True, "weight": 1},
            {"id": "backup", "name": "backup", "url": "https://two.example", "token": "token-two", "enabled": False, "weight": 2},
        ]

        with tempfile.TemporaryDirectory() as tmp_dir:
            env_path = Path(tmp_dir) / ".env"
            env_path.write_text("".join(initial_lines))
            api_client.TELEGRAM_ENV_PATH = str(env_path)

            self.assertTrue(api_client.save_server_configs(new_servers))

            values = {}
            for line in env_path.read_text().splitlines():
                key, value = line.split("=", 1)
                values[key] = value

        self.assertEqual(values["URL"], "https://one.example")
        self.assertEqual(values["TOKEN"], "token-one")
        self.assertIn('"id":"backup"', values["SERVERS_JSON"])
        for key, value in preserved_values.items():
            self.assertEqual(values[key], value)


if __name__ == "__main__":
    unittest.main()
