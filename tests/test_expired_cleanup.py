import importlib.util
import json
import sys
import tempfile
import types
import unittest
from datetime import datetime, timedelta
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "core"
    / "scripts"
    / "telegrambot"
    / "utils"
    / "expired_cleanup.py"
)


class DummyBot:
    def __init__(self):
        self.sent_messages = []
        self.sent_documents = []

    def message_handler(self, *args, **kwargs):
        return lambda func: func

    def send_message(self, chat_id, text, **kwargs):
        self.sent_messages.append((chat_id, text, kwargs))

    def send_document(self, chat_id, document, **kwargs):
        self.sent_documents.append((chat_id, document, kwargs))


_DEFAULT_DELETE_RESULT = object()


class FakeClient:
    def __init__(self, server_id, users=None, delete_result=_DEFAULT_DELETE_RESULT, unavailable=False):
        self.server_id = server_id
        self.users = dict(users or {})
        self.delete_result = {"ok": True} if delete_result is _DEFAULT_DELETE_RESULT else delete_result
        self.unavailable = unavailable
        self.deleted = []

    def get_user(self, username):
        if self.unavailable:
            return None
        return self.users.get(username)

    def get_users(self):
        if self.unavailable:
            return None
        return self.users

    def delete_user(self, username):
        self.deleted.append(username)
        if self.delete_result is not None:
            self.users.pop(username, None)
        return self.delete_result


class FakeMultiAPI:
    def __init__(self, clients):
        self.clients = clients

    def get_client(self, server_id=None):
        if server_id:
            return self.clients.get(server_id)
        return next(iter(self.clients.values()), None)

    def iter_clients(self, include_disabled=False):
        for server_id, client in self.clients.items():
            yield {"id": server_id, "enabled": True}, client


def load_module():
    for name in list(sys.modules):
        if name == "utils" or name.startswith("utils."):
            sys.modules.pop(name, None)

    bot = DummyBot()
    utils_pkg = types.ModuleType("utils")
    utils_pkg.__path__ = []
    sys.modules["utils"] = utils_pkg

    api_client_stub = types.ModuleType("utils.api_client")
    api_client_stub.MultiServerAPI = lambda: FakeMultiAPI({})
    sys.modules["utils.api_client"] = api_client_stub

    command_stub = types.ModuleType("utils.command")
    command_stub.bot = bot
    command_stub.is_admin = lambda user_id: user_id == 1
    sys.modules["utils.command"] = command_stub

    language_stub = types.ModuleType("utils.language")
    language_stub.get_user_language = lambda user_id: "en"
    sys.modules["utils.language"] = language_stub

    translations_stub = types.ModuleType("utils.translations")
    translations_stub.get_message_text = lambda language, key: "{username}:{grace_hours}"
    sys.modules["utils.translations"] = translations_stub

    spec = importlib.util.spec_from_file_location("expired_cleanup_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module._test_bot = bot
    return module


class ExpiredCleanupTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.base = Path(self.tmpdir.name)
        self.cleanup = load_module()
        self.cleanup.TEST_CONFIGS_FILE = str(self.base / "test_configs.json")
        self.cleanup.PAYMENTS_FILE = str(self.base / "payments.json")
        self.cleanup.RESELLERS_FILE = str(self.base / "resellers.json")
        self.cleanup.STATE_FILE = str(self.base / "expired_user_cleanup.json")
        self.now = datetime(2026, 6, 9, 12, 0, 0)

    def write_json(self, path, data):
        Path(path).write_text(json.dumps(data), encoding="utf-8")

    def read_json(self, path):
        return json.loads(Path(path).read_text(encoding="utf-8"))

    def write_default_files(self):
        self.write_json(self.cleanup.TEST_CONFIGS_FILE, {})
        self.write_json(self.cleanup.PAYMENTS_FILE, {})
        self.write_json(self.cleanup.RESELLERS_FILE, {})

    def expired_user(self):
        return {
            "blocked": True,
            "expiration_days": 0,
            "upload_bytes": self.cleanup.GB_BYTES,
            "download_bytes": 2 * self.cleanup.GB_BYTES,
            "max_download_bytes": 5 * self.cleanup.GB_BYTES,
            "status": "expired",
        }

    def test_candidate_discovery_includes_test_customer_and_reseller_configs(self):
        self.write_json(self.cleanup.TEST_CONFIGS_FILE, {
            "101": {"telegram_id": 101, "username": "t101", "server_id": "s1"}
        })
        self.write_json(self.cleanup.PAYMENTS_FILE, {
            "pay1": {"status": "completed", "user_id": 202, "username": "s202", "server_id": "s1"},
            "settlement": {"status": "completed", "type": "settlement", "username": "ignored"},
        })
        self.write_json(self.cleanup.RESELLERS_FILE, {
            "303": {"configs": [{"username": "r303", "server_id": "s2"}]}
        })

        candidates = self.cleanup.discover_cleanup_candidates()

        self.assertEqual(
            {(candidate["source"], candidate["username"]) for candidate in candidates},
            {("test", "t101"), ("customer", "s202"), ("reseller_customer", "r303")},
        )

    def test_first_expired_detection_notifies_and_waits_to_delete(self):
        self.write_json(self.cleanup.TEST_CONFIGS_FILE, {
            "101": {"telegram_id": 101, "username": "t101", "server_id": "s1"}
        })
        self.write_json(self.cleanup.PAYMENTS_FILE, {})
        self.write_json(self.cleanup.RESELLERS_FILE, {})
        client = FakeClient("s1", {"t101": self.expired_user()})

        self.cleanup.run_expired_user_cleanup(now=self.now, multi_api=FakeMultiAPI({"s1": client}))

        state = self.read_json(self.cleanup.STATE_FILE)
        saved_test = self.read_json(self.cleanup.TEST_CONFIGS_FILE)["101"]
        self.assertEqual(client.deleted, [])
        self.assertEqual(len(self.cleanup._test_bot.sent_messages), 1)
        self.assertEqual(state["s1:t101"]["cleanup_status"], "notified")
        self.assertEqual(saved_test["cleanup_status"], "notified")
        self.assertEqual(saved_test["cleanup_notified_at"], "2026-06-09 12:00:00")

    def test_deletes_after_grace_and_saves_last_state(self):
        self.write_json(self.cleanup.TEST_CONFIGS_FILE, {
            "101": {"telegram_id": 101, "username": "t101", "server_id": "s1"}
        })
        self.write_json(self.cleanup.PAYMENTS_FILE, {})
        self.write_json(self.cleanup.RESELLERS_FILE, {})
        client = FakeClient("s1", {"t101": self.expired_user()})

        self.cleanup.run_expired_user_cleanup(now=self.now, multi_api=FakeMultiAPI({"s1": client}))
        self.cleanup.run_expired_user_cleanup(now=self.now + timedelta(hours=25), multi_api=FakeMultiAPI({"s1": client}))

        state = self.read_json(self.cleanup.STATE_FILE)
        saved_test = self.read_json(self.cleanup.TEST_CONFIGS_FILE)["101"]
        last_state = saved_test["cleanup_last_state"]
        self.assertEqual(client.deleted, ["t101"])
        self.assertEqual(saved_test["cleanup_status"], "deleted")
        self.assertEqual(state["s1:t101"]["delete_result"], "deleted")
        self.assertEqual(last_state["days_remaining"], 0)
        self.assertEqual(last_state["gb_limit"], 5.0)
        self.assertEqual(last_state["gb_used"], 3.0)
        self.assertEqual(last_state["gb_remaining"], 2.0)

    def test_renewed_user_clears_pending_cleanup_state(self):
        self.write_json(self.cleanup.TEST_CONFIGS_FILE, {
            "101": {"telegram_id": 101, "username": "t101", "server_id": "s1"}
        })
        self.write_json(self.cleanup.PAYMENTS_FILE, {})
        self.write_json(self.cleanup.RESELLERS_FILE, {})
        client = FakeClient("s1", {"t101": self.expired_user()})

        self.cleanup.run_expired_user_cleanup(now=self.now, multi_api=FakeMultiAPI({"s1": client}))
        client.users["t101"] = {
            "blocked": False,
            "expiration_days": 30,
            "upload_bytes": 0,
            "download_bytes": 0,
            "max_download_bytes": 5 * self.cleanup.GB_BYTES,
        }
        self.cleanup.run_expired_user_cleanup(now=self.now + timedelta(hours=25), multi_api=FakeMultiAPI({"s1": client}))

        self.assertEqual(self.read_json(self.cleanup.STATE_FILE), {})
        self.assertEqual(client.deleted, [])
        self.assertEqual(self.read_json(self.cleanup.TEST_CONFIGS_FILE)["101"]["cleanup_status"], "renewed")

    def test_delete_failure_keeps_retryable_state(self):
        self.write_json(self.cleanup.TEST_CONFIGS_FILE, {
            "101": {"telegram_id": 101, "username": "t101", "server_id": "s1"}
        })
        self.write_json(self.cleanup.PAYMENTS_FILE, {})
        self.write_json(self.cleanup.RESELLERS_FILE, {})
        client = FakeClient("s1", {"t101": self.expired_user()}, delete_result=None)

        self.cleanup.run_expired_user_cleanup(now=self.now, multi_api=FakeMultiAPI({"s1": client}))
        self.cleanup.run_expired_user_cleanup(now=self.now + timedelta(hours=25), multi_api=FakeMultiAPI({"s1": client}))

        state = self.read_json(self.cleanup.STATE_FILE)
        saved_test = self.read_json(self.cleanup.TEST_CONFIGS_FILE)["101"]
        self.assertEqual(client.deleted, ["t101"])
        self.assertEqual(state["s1:t101"]["cleanup_status"], "delete_failed")
        self.assertEqual(saved_test["cleanup_status"], "delete_failed")
        self.assertIn("cleanup_last_state", saved_test)

    def test_unavailable_server_keeps_pending_cleanup_retryable(self):
        self.write_json(self.cleanup.TEST_CONFIGS_FILE, {
            "101": {"telegram_id": 101, "username": "t101", "server_id": "s1"}
        })
        self.write_json(self.cleanup.PAYMENTS_FILE, {})
        self.write_json(self.cleanup.RESELLERS_FILE, {})
        client = FakeClient("s1", {"t101": self.expired_user()})

        self.cleanup.run_expired_user_cleanup(now=self.now, multi_api=FakeMultiAPI({"s1": client}))
        unavailable_client = FakeClient("s1", unavailable=True)
        self.cleanup.run_expired_user_cleanup(
            now=self.now + timedelta(hours=25),
            multi_api=FakeMultiAPI({"s1": unavailable_client}),
        )

        state = self.read_json(self.cleanup.STATE_FILE)
        saved_test = self.read_json(self.cleanup.TEST_CONFIGS_FILE)["101"]
        self.assertEqual(unavailable_client.deleted, [])
        self.assertEqual(state["s1:t101"]["cleanup_status"], "server_unavailable")
        self.assertEqual(state["s1:t101"]["cleanup_error"], "server_unavailable")
        self.assertEqual(saved_test["cleanup_status"], "notified")

    def test_already_missing_after_grace_is_reported_with_null_last_state(self):
        self.write_json(self.cleanup.TEST_CONFIGS_FILE, {
            "101": {"telegram_id": 101, "username": "t101", "server_id": "s1"}
        })
        self.write_json(self.cleanup.PAYMENTS_FILE, {})
        self.write_json(self.cleanup.RESELLERS_FILE, {})
        client = FakeClient("s1", {})

        self.cleanup.run_expired_user_cleanup(now=self.now, multi_api=FakeMultiAPI({"s1": client}))
        self.cleanup.run_expired_user_cleanup(now=self.now + timedelta(hours=25), multi_api=FakeMultiAPI({"s1": client}))

        exported = self.cleanup.get_deleted_users_for_json(now=self.now + timedelta(hours=25))
        self.assertEqual(exported[0]["delete_result"], "already_missing")
        self.assertIsNone(exported[0]["last_state"])

    def test_deleted_users_json_filters_to_past_sixty_days(self):
        self.write_default_files()
        self.write_json(self.cleanup.STATE_FILE, {
            "s1:new": {
                "username": "new",
                "server_id": "s1",
                "source": "customer",
                "telegram_user_id": "101",
                "notified_at": "2026-06-08 12:00:00",
                "deleted_at": "2026-06-09 12:00:00",
                "delete_result": "deleted",
                "last_state": {"days_remaining": 0},
            },
            "s1:old": {
                "username": "old",
                "server_id": "s1",
                "source": "customer",
                "telegram_user_id": "202",
                "notified_at": "2026-03-01 12:00:00",
                "deleted_at": "2026-03-02 12:00:00",
                "delete_result": "deleted",
                "last_state": {"days_remaining": 0},
            },
        })

        exported = self.cleanup.get_deleted_users_for_json(days=60, now=self.now)

        self.assertEqual([entry["username"] for entry in exported], ["new"])


if __name__ == "__main__":
    unittest.main()
