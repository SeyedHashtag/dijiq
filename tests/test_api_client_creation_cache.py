import importlib.util
import os
import sys
import tempfile
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
    def __init__(self, server_id, users, add_results=None):
        self.server_id = server_id
        self.server_name = server_id
        self.users = users
        self.add_results = list(add_results or [])
        self.get_users_calls = 0
        self.add_user_calls = []

    def get_users(self):
        self.get_users_calls += 1
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
        os.environ["SERVER_USERS_CACHE_TTL_SECONDS"] = "30"
        api_client.MultiServerAPI._creation_cache = None

    def tearDown(self):
        api_client.APIClient = self.original_api_client
        api_client.get_server_configs = self.original_get_server_configs
        api_client.time.monotonic = self.original_monotonic
        api_client.MultiServerAPI._creation_cache = None
        if self.original_ttl is None:
            os.environ.pop("SERVER_USERS_CACHE_TTL_SECONDS", None)
        else:
            os.environ["SERVER_USERS_CACHE_TTL_SECONDS"] = self.original_ttl

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
