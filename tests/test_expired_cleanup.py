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
TRANSLATIONS_PATH = MODULE_PATH.with_name("translations.py")


class DummyBot:
    def __init__(self):
        self.sent_messages = []
        self.sent_documents = []
        self.replies = []
        self.edited_messages = []
        self.answered_callbacks = []

    def message_handler(self, *args, **kwargs):
        return lambda func: func

    def callback_query_handler(self, *args, **kwargs):
        return lambda func: func

    def send_message(self, chat_id, text, **kwargs):
        self.sent_messages.append((chat_id, text, kwargs))

    def send_document(self, chat_id, document, **kwargs):
        self.sent_documents.append((chat_id, document, kwargs))

    def reply_to(self, message, text, **kwargs):
        self.replies.append((message, text, kwargs))

    def edit_message_text(self, text, **kwargs):
        self.edited_messages.append((text, kwargs))

    def answer_callback_query(self, callback_query_id, text=None, **kwargs):
        self.answered_callbacks.append((callback_query_id, text, kwargs))


_DEFAULT_DELETE_RESULT = object()


class FakeClient:
    def __init__(self, server_id, users=None, delete_result=_DEFAULT_DELETE_RESULT, unavailable=False):
        self.server_id = server_id
        self.users = dict(users or {})
        self.delete_result = {"ok": True} if delete_result is _DEFAULT_DELETE_RESULT else delete_result
        self.unavailable = unavailable
        self.deleted = []
        self.get_user_calls = []
        self.get_users_calls = 0

    def get_user(self, username):
        self.get_user_calls.append(username)
        if self.unavailable:
            return None
        return self.users.get(username)

    def get_users(self):
        self.get_users_calls += 1
        if self.unavailable:
            return None
        return self.users

    def delete_user(self, username):
        self.deleted.append(username)
        if self.delete_result is not None:
            self.users.pop(username, None)
        return self.delete_result


class BulkOnlyFakeClient(FakeClient):
    def get_user(self, username):
        self.get_user_calls.append(username)
        return None


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
    translations_stub.get_message_text = (
        lambda language, key: "{account_type}|{username}|{grace_hours}|{state_summary}"
    )
    translations_stub.get_button_text = lambda language, key: "Renew Plan" if key == "renew_plan" else key
    sys.modules["utils.translations"] = translations_stub

    edit_plans_stub = types.ModuleType("utils.edit_plans")
    edit_plans_stub.load_plans = lambda: {}
    sys.modules["utils.edit_plans"] = edit_plans_stub

    renewal_stub = types.ModuleType("utils.renewal")
    renewal_stub.find_customer_renewal_offer = lambda *args, **kwargs: {"eligible": False}
    renewal_stub.find_reseller_renewal_offer = lambda *args, **kwargs: {"eligible": False}
    sys.modules["utils.renewal"] = renewal_stub

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

    def callback_data_from_markup(self, markup):
        callbacks = []
        for row in getattr(markup, "keyboard", []):
            for button in row:
                callback_data = getattr(button, "callback_data", None)
                if callback_data is None and hasattr(button, "to_dict"):
                    callback_data = button.to_dict().get("callback_data")
                if callback_data is None:
                    callback_data = getattr(button, "kwargs", {}).get("callback_data")
                callbacks.append(callback_data)
        for button in getattr(markup, "buttons", []):
            callback_data = getattr(button, "callback_data", None)
            if callback_data is None and hasattr(button, "to_dict"):
                callback_data = button.to_dict().get("callback_data")
            if callback_data is None:
                callback_data = getattr(button, "kwargs", {}).get("callback_data")
            callbacks.append(callback_data)
        return callbacks

    def expired_user(self):
        return {
            "blocked": True,
            "expiration_days": 0,
            "upload_bytes": self.cleanup.GB_BYTES,
            "download_bytes": 2 * self.cleanup.GB_BYTES,
            "max_download_bytes": 5 * self.cleanup.GB_BYTES,
            "status": "expired",
        }

    def test_customer_cleanup_notice_includes_renewal_button_when_eligible(self):
        edit_plans_stub = types.ModuleType("utils.edit_plans")
        edit_plans_stub.load_plans = lambda: {"5": {"price": 10.0, "days": 30, "unlimited": False}}
        sys.modules["utils.edit_plans"] = edit_plans_stub

        renewal_stub = types.ModuleType("utils.renewal")
        renewal_stub.find_customer_renewal_offer = lambda *args, **kwargs: {"eligible": True, "token": "renew-token"}
        renewal_stub.find_reseller_renewal_offer = lambda *args, **kwargs: {"eligible": False}
        sys.modules["utils.renewal"] = renewal_stub

        error = self.cleanup._notify_candidate(
            {
                "source": "customer",
                "telegram_user_id": "1988",
                "username": "alice",
                "server_id": "s1",
                "_api_client": object(),
                "_user_data": self.expired_user(),
            },
            grace_hours=24,
            last_state=self.expired_user(),
        )

        self.assertIsNone(error)
        chat_id, _message, kwargs = self.cleanup._test_bot.sent_messages[-1]
        self.assertEqual(chat_id, 1988)
        callbacks = self.callback_data_from_markup(kwargs["reply_markup"])
        self.assertEqual(callbacks, ["renew_plan:renew-token"])

    def test_user_must_be_blocked_to_be_expired_by_days_or_traffic(self):
        unblocked_expired_days = {
            "blocked": False,
            "expiration_days": 0,
            "upload_bytes": 0,
            "download_bytes": 0,
            "max_download_bytes": 5 * self.cleanup.GB_BYTES,
        }
        unblocked_exhausted_traffic = {
            "blocked": False,
            "expiration_days": 30,
            "upload_bytes": 2 * self.cleanup.GB_BYTES,
            "download_bytes": 3 * self.cleanup.GB_BYTES,
            "max_download_bytes": 5 * self.cleanup.GB_BYTES,
        }
        blocked_active_user = {
            "blocked": True,
            "expiration_days": 30,
            "upload_bytes": self.cleanup.GB_BYTES,
            "download_bytes": self.cleanup.GB_BYTES,
            "max_download_bytes": 5 * self.cleanup.GB_BYTES,
        }

        self.assertFalse(self.cleanup.is_user_expired(unblocked_expired_days))
        self.assertFalse(self.cleanup.is_user_expired(unblocked_exhausted_traffic))
        self.assertFalse(self.cleanup.is_user_expired(blocked_active_user))

    def test_cleanup_renews_pending_user_when_unblocked_even_if_days_expired(self):
        self.write_json(self.cleanup.TEST_CONFIGS_FILE, {
            "101": {"telegram_id": 101, "username": "t101", "server_id": "s1"}
        })
        self.write_json(self.cleanup.PAYMENTS_FILE, {})
        self.write_json(self.cleanup.RESELLERS_FILE, {})
        client = FakeClient("s1", {"t101": self.expired_user()})

        self.cleanup.run_expired_user_cleanup(now=self.now, multi_api=FakeMultiAPI({"s1": client}))
        client.users["t101"] = {
            "blocked": False,
            "expiration_days": 0,
            "upload_bytes": 0,
            "download_bytes": 0,
            "max_download_bytes": 5 * self.cleanup.GB_BYTES,
        }
        self.cleanup.run_expired_user_cleanup(now=self.now + timedelta(hours=25), multi_api=FakeMultiAPI({"s1": client}))

        self.assertEqual(self.read_json(self.cleanup.STATE_FILE), {})
        self.assertEqual(client.deleted, [])
        self.assertEqual(client.get_user_calls, [])
        self.assertEqual(client.get_users_calls, 2)
        self.assertEqual(self.read_json(self.cleanup.TEST_CONFIGS_FILE)["101"]["cleanup_status"], "renewed")

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
        self.assertEqual(client.get_user_calls, [])
        self.assertEqual(len(self.cleanup._test_bot.sent_messages), 1)
        self.assertEqual(state["s1:t101"]["cleanup_status"], "notified")
        self.assertEqual(saved_test["cleanup_status"], "notified")
        self.assertEqual(saved_test["cleanup_notified_at"], "2026-06-09 12:00:00")
        self.assertEqual(saved_test["cleanup_last_state"]["status"], "expired")
        self.assertIn("your test account", self.cleanup._test_bot.sent_messages[0][1])
        self.assertIn("Status: expired", self.cleanup._test_bot.sent_messages[0][1])
        self.assertNotIn("Blocked:", self.cleanup._test_bot.sent_messages[0][1])
        self.assertIn("Days remaining: 0", self.cleanup._test_bot.sent_messages[0][1])
        self.assertIn("GB used: 3.0/5.0", self.cleanup._test_bot.sent_messages[0][1])
        self.assertNotIn("GB remaining:", self.cleanup._test_bot.sent_messages[0][1])

    def test_server_only_expired_user_goes_to_manual_review_without_local_record(self):
        self.write_default_files()
        client = FakeClient("s1", {"orphan": self.expired_user()})

        self.cleanup.run_expired_user_cleanup(now=self.now, multi_api=FakeMultiAPI({"s1": client}))

        state = self.read_json(self.cleanup.STATE_FILE)
        self.assertEqual(client.deleted, [])
        self.assertEqual(client.get_users_calls, 1)
        self.assertEqual(client.get_user_calls, [])
        self.assertEqual(len(self.cleanup._test_bot.sent_messages), 0)
        self.assertEqual(state["s1:orphan"]["cleanup_status"], "manual_review")
        self.assertEqual(state["s1:orphan"]["source"], "server_user")
        self.assertNotIn("delete_after", state["s1:orphan"])
        self.assertNotIn("notification_error", state["s1:orphan"])
        self.assertEqual(state["s1:orphan"]["last_state"]["status"], "expired")

    def test_server_only_manual_review_user_does_not_auto_delete_after_grace(self):
        self.write_default_files()
        client = FakeClient("s1", {"orphan": self.expired_user()})

        self.cleanup.run_expired_user_cleanup(now=self.now, multi_api=FakeMultiAPI({"s1": client}))
        self.cleanup.run_expired_user_cleanup(now=self.now + timedelta(hours=25), multi_api=FakeMultiAPI({"s1": client}))

        state = self.read_json(self.cleanup.STATE_FILE)
        self.assertEqual(client.deleted, [])
        self.assertEqual(state["s1:orphan"]["cleanup_status"], "manual_review")
        self.assertEqual(state["s1:orphan"]["last_state"]["status"], "expired")

    def test_server_only_manual_review_user_is_marked_renewed_when_renewed(self):
        self.write_default_files()
        client = FakeClient("s1", {"orphan": self.expired_user()})

        self.cleanup.run_expired_user_cleanup(now=self.now, multi_api=FakeMultiAPI({"s1": client}))
        client.users["orphan"] = {
            "blocked": False,
            "expiration_days": 30,
            "upload_bytes": 0,
            "download_bytes": 0,
            "max_download_bytes": 5 * self.cleanup.GB_BYTES,
        }
        self.cleanup.run_expired_user_cleanup(now=self.now + timedelta(hours=25), multi_api=FakeMultiAPI({"s1": client}))

        state = self.read_json(self.cleanup.STATE_FILE)
        self.assertEqual(state["s1:orphan"]["cleanup_status"], "renewed")
        self.assertEqual(client.deleted, [])

    def test_legacy_server_only_notified_record_is_migrated_to_manual_review(self):
        self.write_default_files()
        self.write_json(self.cleanup.STATE_FILE, {
            "s1:orphan": {
                "username": "orphan",
                "server_id": "s1",
                "source": "server_user",
                "cleanup_status": "notified",
                "notified_at": "2026-06-09 08:00:00",
                "delete_after": "2026-06-09 11:00:00",
                "notification_error": "missing_recipient",
                "last_state": {"status": "expired", "days_remaining": 0},
            }
        })
        client = FakeClient("s1", {"orphan": self.expired_user()})

        self.cleanup.run_expired_user_cleanup(now=self.now + timedelta(hours=25), multi_api=FakeMultiAPI({"s1": client}))

        state = self.read_json(self.cleanup.STATE_FILE)
        self.assertEqual(client.deleted, [])
        self.assertEqual(state["s1:orphan"]["cleanup_status"], "manual_review")
        self.assertNotIn("delete_after", state["s1:orphan"])
        self.assertNotIn("notification_error", state["s1:orphan"])
        self.assertNotIn("notified_at", state["s1:orphan"])

    def test_renewed_server_only_user_reexpiring_returns_to_manual_review(self):
        self.write_default_files()
        self.write_json(self.cleanup.STATE_FILE, {
            "s1:orphan": {
                "username": "orphan",
                "server_id": "s1",
                "source": "server_user",
                "cleanup_status": "renewed",
                "last_state": {"status": "active", "days_remaining": 30},
            }
        })
        client = FakeClient("s1", {"orphan": self.expired_user()})

        self.cleanup.run_expired_user_cleanup(now=self.now, multi_api=FakeMultiAPI({"s1": client}))

        state = self.read_json(self.cleanup.STATE_FILE)
        self.assertEqual(client.deleted, [])
        self.assertEqual(state["s1:orphan"]["cleanup_status"], "manual_review")
        self.assertEqual(state["s1:orphan"]["last_state"]["status"], "expired")

    def test_paid_customer_notification_includes_account_type(self):
        self.write_json(self.cleanup.TEST_CONFIGS_FILE, {})
        self.write_json(self.cleanup.PAYMENTS_FILE, {
            "pay1": {"status": "completed", "user_id": 202, "username": "p202", "server_id": "s1"}
        })
        self.write_json(self.cleanup.RESELLERS_FILE, {})
        client = FakeClient("s1", {"p202": self.expired_user()})

        self.cleanup.run_expired_user_cleanup(now=self.now, multi_api=FakeMultiAPI({"s1": client}))

        self.assertEqual(len(self.cleanup._test_bot.sent_messages), 1)
        self.assertIn("your paid account", self.cleanup._test_bot.sent_messages[0][1])
        saved_payment = self.read_json(self.cleanup.PAYMENTS_FILE)["pay1"]
        self.assertEqual(saved_payment["cleanup_last_state"]["status"], "expired")

    def test_reseller_customer_notification_includes_account_type(self):
        self.write_json(self.cleanup.TEST_CONFIGS_FILE, {})
        self.write_json(self.cleanup.PAYMENTS_FILE, {})
        self.write_json(self.cleanup.RESELLERS_FILE, {
            "303": {"configs": [{"username": "r303", "server_id": "s1"}]}
        })
        client = FakeClient("s1", {"r303": self.expired_user()})

        self.cleanup.run_expired_user_cleanup(now=self.now, multi_api=FakeMultiAPI({"s1": client}))

        self.assertEqual(len(self.cleanup._test_bot.sent_messages), 1)
        self.assertEqual(self.cleanup._test_bot.sent_messages[0][0], 303)
        self.assertIn("your customer account", self.cleanup._test_bot.sent_messages[0][1])
        saved_config = self.read_json(self.cleanup.RESELLERS_FILE)["303"]["configs"][0]
        self.assertEqual(saved_config["cleanup_last_state"]["status"], "expired")

    def test_bot_record_missing_from_vpn_is_ignored_without_notification(self):
        self.write_json(self.cleanup.TEST_CONFIGS_FILE, {
            "101": {"telegram_id": 101, "username": "missing101", "server_id": "s1"}
        })
        self.write_json(self.cleanup.PAYMENTS_FILE, {})
        self.write_json(self.cleanup.RESELLERS_FILE, {})
        client = FakeClient("s1", {})

        self.cleanup.run_expired_user_cleanup(now=self.now, multi_api=FakeMultiAPI({"s1": client}))

        state = self.read_json(self.cleanup.STATE_FILE)
        saved_test = self.read_json(self.cleanup.TEST_CONFIGS_FILE)["101"]
        self.assertEqual(self.cleanup._test_bot.sent_messages, [])
        self.assertEqual(state, {})
        self.assertNotIn("cleanup_status", saved_test)
        self.assertNotIn("cleanup_delete_result", saved_test)
        self.assertNotIn("cleanup_deleted_at", saved_test)
        self.assertNotIn("cleanup_notified_at", saved_test)
        self.assertNotIn("cleanup_last_state", saved_test)

    def test_non_expired_bot_record_does_not_trigger_per_user_vpn_lookup(self):
        self.write_json(self.cleanup.TEST_CONFIGS_FILE, {
            "101": {"telegram_id": 101, "username": "missing101", "server_id": "s1"}
        })
        self.write_json(self.cleanup.PAYMENTS_FILE, {
            "pay1": {"status": "completed", "user_id": 202, "username": "missing202", "server_id": "s1"}
        })
        self.write_json(self.cleanup.RESELLERS_FILE, {})
        client = FakeClient("s1", {
            "active": {
                "blocked": False,
                "expiration_days": 30,
                "upload_bytes": 0,
                "download_bytes": 0,
                "max_download_bytes": 5 * self.cleanup.GB_BYTES,
            }
        })

        self.cleanup.run_expired_user_cleanup(now=self.now, multi_api=FakeMultiAPI({"s1": client}))

        self.assertEqual(client.get_users_calls, 1)
        self.assertEqual(client.get_user_calls, [])
        self.assertEqual(self.read_json(self.cleanup.STATE_FILE), {})

    def test_state_cleanup_uses_bulk_scan_for_renewal_without_per_user_lookup(self):
        self.write_json(self.cleanup.TEST_CONFIGS_FILE, {
            "101": {"telegram_id": 101, "username": "t101", "server_id": "s1"}
        })
        self.write_json(self.cleanup.PAYMENTS_FILE, {})
        self.write_json(self.cleanup.RESELLERS_FILE, {})
        self.write_json(self.cleanup.STATE_FILE, {
            "s1:t101": {
                "username": "t101",
                "server_id": "s1",
                "source": "test",
                "telegram_user_id": "101",
                "cleanup_status": "notified",
                "notified_at": "2026-06-09 08:00:00",
                "delete_after": "2026-06-09 11:00:00",
                "last_state": {"days_remaining": 0},
            }
        })
        client = FakeClient("s1", {
            "t101": {
                "blocked": False,
                "expiration_days": 30,
                "upload_bytes": 0,
                "download_bytes": 0,
                "max_download_bytes": 5 * self.cleanup.GB_BYTES,
            }
        })

        self.cleanup.run_expired_user_cleanup(now=self.now + timedelta(hours=25), multi_api=FakeMultiAPI({"s1": client}))

        self.assertEqual(client.get_users_calls, 1)
        self.assertEqual(client.get_user_calls, [])
        self.assertEqual(client.deleted, [])
        self.assertEqual(self.read_json(self.cleanup.STATE_FILE), {})
        self.assertEqual(self.read_json(self.cleanup.TEST_CONFIGS_FILE)["101"]["cleanup_status"], "renewed")

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
        self.write_default_files()
        self.write_json(self.cleanup.STATE_FILE, {
            "s1:t101": {
                "username": "t101",
                "server_id": "s1",
                "source": "server_user",
                "cleanup_status": "notified",
                "notified_at": "2026-06-09 08:00:00",
                "delete_after": "2026-06-09 11:00:00",
                "last_state": None,
            }
        })
        client = FakeClient("s1", {})

        self.cleanup.run_expired_user_cleanup(now=self.now + timedelta(hours=25), multi_api=FakeMultiAPI({"s1": client}))

        exported = self.cleanup.get_deleted_users_for_json(now=self.now + timedelta(hours=25))
        self.assertEqual(self.cleanup._test_bot.sent_messages, [])
        self.assertEqual(exported[0]["delete_result"], "already_missing")
        self.assertIsNone(exported[0]["last_state"])

    def test_due_cleanup_uses_bulk_scan_when_single_user_lookup_misses_existing_user(self):
        self.write_json(self.cleanup.TEST_CONFIGS_FILE, {})
        self.write_json(self.cleanup.PAYMENTS_FILE, {})
        self.write_json(self.cleanup.RESELLERS_FILE, {
            "303": {"configs": [{"username": "r303", "server_id": "s1"}]}
        })
        self.write_json(self.cleanup.STATE_FILE, {
            "s1:r303": {
                "username": "r303",
                "server_id": "s1",
                "source": "reseller_customer",
                "reseller_id": "303",
                "cleanup_status": "notified",
                "notified_at": "2026-06-09 08:00:00",
                "delete_after": "2026-06-09 11:00:00",
                "last_state": {"days_remaining": 0},
            }
        })
        traffic_exhausted_user = {
            "blocked": True,
            "expiration_days": 40,
            "upload_bytes": 6 * self.cleanup.GB_BYTES,
            "download_bytes": 4 * self.cleanup.GB_BYTES,
            "max_download_bytes": 10 * self.cleanup.GB_BYTES,
            "status": "Offline",
        }
        client = BulkOnlyFakeClient("s1", {"r303": traffic_exhausted_user})

        self.cleanup.run_expired_user_cleanup(now=self.now + timedelta(hours=25), multi_api=FakeMultiAPI({"s1": client}))

        state = self.read_json(self.cleanup.STATE_FILE)
        saved_config = self.read_json(self.cleanup.RESELLERS_FILE)["303"]["configs"][0]
        self.assertEqual(client.deleted, ["r303"])
        self.assertEqual(state["s1:r303"]["cleanup_status"], "deleted")
        self.assertEqual(state["s1:r303"]["delete_result"], "deleted")
        self.assertEqual(saved_config["cleanup_status"], "deleted")

    def test_refresh_repairs_already_missing_when_bulk_scan_finds_existing_user(self):
        self.write_json(self.cleanup.TEST_CONFIGS_FILE, {})
        self.write_json(self.cleanup.PAYMENTS_FILE, {})
        self.write_json(self.cleanup.RESELLERS_FILE, {
            "303": {"configs": [{
                "username": "r303",
                "server_id": "s1",
                "cleanup_status": "already_missing",
                "cleanup_deleted_at": "2026-06-09 12:00:00",
                "cleanup_delete_result": "already_missing",
            }]}
        })
        self.write_json(self.cleanup.STATE_FILE, {
            "s1:r303": {
                "username": "r303",
                "server_id": "s1",
                "source": "reseller_customer",
                "reseller_id": "303",
                "cleanup_status": "already_missing",
                "delete_result": "already_missing",
                "notified_at": "2026-06-09 08:00:00",
                "delete_after": "2026-06-09 11:00:00",
                "deleted_at": "2026-06-09 12:00:00",
                "last_state": {"days_remaining": 0},
            }
        })
        traffic_exhausted_user = {
            "blocked": True,
            "expiration_days": 40,
            "upload_bytes": 6 * self.cleanup.GB_BYTES,
            "download_bytes": 4 * self.cleanup.GB_BYTES,
            "max_download_bytes": 10 * self.cleanup.GB_BYTES,
            "status": "Offline",
        }
        client = BulkOnlyFakeClient("s1", {"r303": traffic_exhausted_user})

        self.cleanup.run_expired_user_cleanup(now=self.now + timedelta(hours=25), multi_api=FakeMultiAPI({"s1": client}))

        state = self.read_json(self.cleanup.STATE_FILE)
        saved_config = self.read_json(self.cleanup.RESELLERS_FILE)["303"]["configs"][0]
        self.assertEqual(client.deleted, ["r303"])
        self.assertEqual(state["s1:r303"]["cleanup_status"], "deleted")
        self.assertEqual(state["s1:r303"]["delete_result"], "deleted")
        self.assertEqual(saved_config["cleanup_status"], "deleted")
        self.assertEqual(saved_config["cleanup_delete_result"], "deleted")

    def test_refresh_clears_stale_missing_reason_when_repaired_user_is_still_pending(self):
        self.write_json(self.cleanup.TEST_CONFIGS_FILE, {})
        self.write_json(self.cleanup.PAYMENTS_FILE, {})
        self.write_json(self.cleanup.RESELLERS_FILE, {
            "303": {"configs": [{
                "username": "r303",
                "server_id": "s1",
                "cleanup_status": "already_missing",
                "cleanup_deleted_at": "2026-06-09 12:00:00",
                "cleanup_delete_result": "already_missing",
            }]}
        })
        self.write_json(self.cleanup.STATE_FILE, {
            "s1:r303": {
                "username": "r303",
                "server_id": "s1",
                "source": "reseller_customer",
                "reseller_id": "303",
                "cleanup_status": "already_missing",
                "delete_result": "already_missing",
                "notified_at": "2026-06-09 08:00:00",
                "delete_after": "2026-06-09 14:00:00",
                "deleted_at": "2026-06-09 12:00:00",
                "last_state": {"days_remaining": 0},
            }
        })
        traffic_exhausted_user = {
            "blocked": True,
            "expiration_days": 40,
            "upload_bytes": 6 * self.cleanup.GB_BYTES,
            "download_bytes": 4 * self.cleanup.GB_BYTES,
            "max_download_bytes": 10 * self.cleanup.GB_BYTES,
            "status": "Offline",
        }
        client = BulkOnlyFakeClient("s1", {"r303": traffic_exhausted_user})

        self.cleanup.run_expired_user_cleanup(now=self.now, multi_api=FakeMultiAPI({"s1": client}))

        state = self.read_json(self.cleanup.STATE_FILE)
        saved_config = self.read_json(self.cleanup.RESELLERS_FILE)["303"]["configs"][0]
        records = self.cleanup.get_expired_cleanup_records(filter_key="pending", now=self.now)
        record = next(item for item in records if item["username"] == "r303")
        self.assertEqual(client.deleted, [])
        self.assertEqual(state["s1:r303"]["cleanup_status"], "notified")
        self.assertNotIn("delete_result", state["s1:r303"])
        self.assertNotIn("deleted_at", state["s1:r303"])
        self.assertNotIn("cleanup_delete_result", saved_config)
        self.assertNotIn("cleanup_deleted_at", saved_config)
        self.assertEqual(record["reason_code"], "traffic_exhausted")

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
        self.assertEqual(exported[0]["reason_code"], "time_expired")
        self.assertIn("reason", exported[0])

    def test_admin_cleanup_counts_split_pending_due_and_history(self):
        self.write_default_files()
        self.write_json(self.cleanup.STATE_FILE, {
            "s1:pending": {
                "username": "pending",
                "server_id": "s1",
                "source": "customer",
                "cleanup_status": "notified",
                "notified_at": "2026-06-09 10:00:00",
                "delete_after": "2026-06-09 14:00:00",
                "last_state": {"days_remaining": 0},
            },
            "s1:due": {
                "username": "due",
                "server_id": "s1",
                "source": "customer",
                "cleanup_status": "notified",
                "notified_at": "2026-06-09 08:00:00",
                "delete_after": "2026-06-09 11:00:00",
                "last_state": {"days_remaining": 0},
            },
            "s1:deleted": {
                "username": "deleted",
                "server_id": "s1",
                "source": "test",
                "cleanup_status": "deleted",
                "delete_result": "deleted",
                "deleted_at": "2026-06-09 09:00:00",
                "last_state": {"days_remaining": 0},
            },
            "s1:failed": {
                "username": "failed",
                "server_id": "s1",
                "source": "customer",
                "cleanup_status": "delete_failed",
                "last_state": {"days_remaining": 0},
            },
            "s1:unavailable": {
                "username": "unavailable",
                "server_id": "s1",
                "source": "customer",
                "cleanup_status": "server_unavailable",
                "last_state": {"days_remaining": 0},
            },
            "s1:renewed": {
                "username": "renewed",
                "server_id": "s1",
                "source": "customer",
                "cleanup_status": "renewed",
                "last_state": {"days_remaining": 10},
            },
            "s1:review": {
                "username": "review",
                "server_id": "s1",
                "source": "server_user",
                "cleanup_status": "manual_review",
                "last_state": {"days_remaining": 0},
            },
            "s1:duplicate": {
                "username": "duplicate",
                "server_id": "s1",
                "source": "server_user",
                "cleanup_status": "manual_review",
                "manual_review_reason": "duplicate_payment",
                "last_state": {"days_remaining": 30},
            },
        })

        counts = self.cleanup.get_expired_cleanup_counts(now=self.now)

        self.assertEqual(counts["manual_review"], 1)
        self.assertEqual(counts["duplicate_payment"], 1)
        self.assertEqual(counts["pending"], 1)
        self.assertEqual(counts["due"], 1)
        self.assertEqual(counts["deleted"], 1)
        self.assertEqual(counts["delete_failed"], 1)
        self.assertEqual(counts["server_unavailable"], 1)
        self.assertEqual(counts["renewed"], 1)

    def test_cleanup_export_includes_reason_codes(self):
        self.write_default_files()
        self.write_json(self.cleanup.STATE_FILE, {
            "s1:time": {
                "username": "time",
                "server_id": "s1",
                "source": "customer",
                "cleanup_status": "notified",
                "delete_after": "2026-06-09 14:00:00",
                "last_state": {"days_remaining": 0, "upload_bytes": 0, "download_bytes": 0, "max_download_bytes": 10},
            },
            "s1:traffic": {
                "username": "traffic",
                "server_id": "s1",
                "source": "customer",
                "cleanup_status": "notified",
                "delete_after": "2026-06-09 14:00:00",
                "last_state": {"days_remaining": 5, "upload_bytes": 6, "download_bytes": 4, "max_download_bytes": 10},
            },
            "s1:missing": {
                "username": "missing",
                "server_id": "s1",
                "source": "customer",
                "cleanup_status": "already_missing",
                "delete_result": "already_missing",
                "deleted_at": "2026-06-09 12:00:00",
                "last_state": None,
            },
            "s1:unavailable": {
                "username": "unavailable",
                "server_id": "s1",
                "source": "customer",
                "cleanup_status": "server_unavailable",
                "last_state": {"days_remaining": 0},
            },
            "s1:failed": {
                "username": "failed",
                "server_id": "s1",
                "source": "customer",
                "cleanup_status": "delete_failed",
                "last_state": {"days_remaining": 0},
            },
        })

        exported = self.cleanup.get_expired_cleanup_export_records(filter_key="all", now=self.now)
        reasons = {record["username"]: record["reason_code"] for record in exported}

        self.assertEqual(reasons["time"], "time_expired")
        self.assertEqual(reasons["traffic"], "traffic_exhausted")
        self.assertEqual(reasons["missing"], "missing_on_server")
        self.assertEqual(reasons["unavailable"], "server_unavailable")
        self.assertEqual(reasons["failed"], "delete_failed")

    def test_admin_cleanup_default_ui_shows_pending_not_history(self):
        self.write_default_files()
        self.write_json(self.cleanup.STATE_FILE, {
            "s1:pending": {
                "username": "pending",
                "server_id": "s1",
                "source": "customer",
                "cleanup_status": "notified",
                "delete_after": "2099-06-09 14:00:00",
                "last_state": {"days_remaining": 0},
            },
            "s1:deleted": {
                "username": "deleted",
                "server_id": "s1",
                "source": "test",
                "cleanup_status": "deleted",
                "delete_result": "deleted",
                "deleted_at": "2026-06-09 12:00:00",
                "last_state": {"days_remaining": 0},
            },
        })

        text = self.cleanup._build_admin_cleanup_text("en", filter_key="queue", page=0, now=self.now)
        markup = self.cleanup._build_admin_cleanup_markup(filter_key="queue", page=0, now=self.now)
        callbacks = self.callback_data_from_markup(markup)

        self.assertIn("Pending: *1*", text)
        self.assertIn("View: *Pending*", text)
        self.assertIn("waiting for the grace period", text)
        self.assertIn("`pending`", text)
        self.assertNotIn("`deleted`", text)
        self.assertIn("admin_expired_cleanup:list:duplicate_payment:0", callbacks)
        self.assertIn("admin_expired_cleanup:list:deleted:0", callbacks)
        self.assertNotIn("admin_expired_cleanup:list:queue:0", callbacks)
        self.assertIn("admin_expired_cleanup:export:pending", callbacks)
        self.assertIn("admin_expired_cleanup:export:all", callbacks)

    def test_manual_review_ui_shows_records_and_review_actions(self):
        self.write_default_files()
        self.write_json(self.cleanup.STATE_FILE, {
            "s1:orphan": {
                "username": "orphan",
                "server_id": "s1",
                "source": "server_user",
                "cleanup_status": "manual_review",
                "last_state": {"days_remaining": 0},
            },
        })

        text = self.cleanup._build_admin_cleanup_text("en", filter_key="manual_review", page=0, now=self.now)
        markup = self.cleanup._build_admin_cleanup_markup(filter_key="manual_review", page=0, now=self.now)
        callbacks = self.callback_data_from_markup(markup)

        self.assertIn("Manual Review: *1*", text)
        self.assertIn("`orphan`", text)
        review_callbacks = [callback for callback in callbacks if callback and callback.startswith("aec:")]
        self.assertTrue(any(callback.startswith("aec:rd:mr:") for callback in review_callbacks))
        self.assertTrue(any(callback.startswith("aec:rk:mr:") for callback in review_callbacks))
        self.assertTrue(all(len(callback.encode("utf-8")) <= 64 for callback in review_callbacks))

    def test_duplicate_payment_manual_review_stays_visible_for_active_user(self):
        self.write_default_files()
        state_key = "s1:duplicate-user-b"
        self.write_json(self.cleanup.STATE_FILE, {
            state_key: {
                "username": "duplicate-user-b",
                "server_id": "s1",
                "source": "server_user",
                "cleanup_status": "manual_review",
                "manual_review_reason": "duplicate_payment",
                "payment_id": "duplicate-payment-id",
                "keeper_username": "duplicate-user-a",
                "review_note": "Duplicate generated by repeated receipt approval; keep duplicate-user-a.",
                "last_state": {"status": "active"},
            },
        })
        active_duplicate = {
            "blocked": False,
            "expiration_days": 30,
            "upload_bytes": 0,
            "download_bytes": 0,
            "max_download_bytes": 100 * self.cleanup.GB_BYTES,
            "status": "active",
        }
        client = FakeClient("s1", {"duplicate-user-b": active_duplicate})

        self.cleanup.run_expired_user_cleanup(now=self.now, multi_api=FakeMultiAPI({"s1": client}))

        state = self.read_json(self.cleanup.STATE_FILE)
        self.assertEqual(state[state_key]["cleanup_status"], "manual_review")
        self.assertEqual(state[state_key]["manual_review_reason"], "duplicate_payment")
        self.assertEqual(state[state_key]["last_state"]["status"], "active")

        manual_text = self.cleanup._build_admin_cleanup_text("en", filter_key="manual_review", page=0, now=self.now)
        duplicate_text = self.cleanup._build_admin_cleanup_text("en", filter_key="duplicate_payment", page=0, now=self.now)
        duplicate_markup = self.cleanup._build_admin_cleanup_markup(filter_key="duplicate_payment", page=0, now=self.now)
        callbacks = self.callback_data_from_markup(duplicate_markup)

        self.assertNotIn("`duplicate-user-b`", manual_text)
        self.assertIn("`duplicate-user-b`", duplicate_text)
        self.assertIn("Duplicate payment review", duplicate_text)
        self.assertIn("Manual reason: `duplicate\\_payment`", duplicate_text)
        self.assertIn("Duplicate configs from repeated payment creation", duplicate_text)
        review_callbacks = [callback for callback in callbacks if callback and callback.startswith("aec:")]
        self.assertTrue(any(callback.startswith("aec:rd:dp:") for callback in review_callbacks))
        self.assertTrue(any(callback.startswith("aec:rk:dp:") for callback in review_callbacks))
        self.assertTrue(all(len(callback.encode("utf-8")) <= 64 for callback in review_callbacks))

    def test_manual_review_action_callbacks_fit_telegram_limit(self):
        self.write_default_files()
        self.write_json(self.cleanup.STATE_FILE, {
            "s1:orphan": {
                "username": "orphan",
                "server_id": "s1",
                "source": "server_user",
                "cleanup_status": "manual_review",
                "last_state": {"days_remaining": 0},
            },
            "s1:duplicate": {
                "username": "duplicate",
                "server_id": "s1",
                "source": "server_user",
                "cleanup_status": "manual_review",
                "manual_review_reason": "duplicate_payment",
                "last_state": {"days_remaining": 30},
            },
        })

        manual_callbacks = self.callback_data_from_markup(
            self.cleanup._build_admin_cleanup_markup(filter_key="manual_review", page=0, now=self.now)
        )
        duplicate_callbacks = self.callback_data_from_markup(
            self.cleanup._build_admin_cleanup_markup(filter_key="duplicate_payment", page=0, now=self.now)
        )
        review_callbacks = [
            callback
            for callback in manual_callbacks + duplicate_callbacks
            if callback and callback.startswith("aec:")
        ]

        self.assertEqual(len(review_callbacks), 4)
        self.assertTrue(all(len(callback.encode("utf-8")) <= 64 for callback in review_callbacks))

    def test_manual_review_keep_updates_metadata_but_keeps_record_visible(self):
        self.write_default_files()
        state_key = "s1:orphan"
        self.write_json(self.cleanup.STATE_FILE, {
            state_key: {
                "username": "orphan",
                "server_id": "s1",
                "source": "server_user",
                "cleanup_status": "manual_review",
                "last_state": {"days_remaining": 0},
            },
        })
        record_id = self.cleanup._state_record_id(state_key)
        call = types.SimpleNamespace(
            id="callback-1",
            data=f"aec:rk:mr:{record_id}",
            from_user=types.SimpleNamespace(id=1),
            message=types.SimpleNamespace(chat=types.SimpleNamespace(id=10), message_id=20),
        )

        self.cleanup.handle_admin_expired_cleanup(call)

        state = self.read_json(self.cleanup.STATE_FILE)
        self.assertEqual(state[state_key]["cleanup_status"], "manual_review")
        self.assertEqual(state[state_key]["review_status"], "kept")
        self.assertEqual(state[state_key]["reviewed_by"], "1")
        self.assertEqual(self.cleanup._test_bot.answered_callbacks[-1][1], "Kept for later review.")
        text = self.cleanup._test_bot.edited_messages[-1][0]
        self.assertIn("`orphan`", text)
        self.assertIn("Review: `kept`", text)

    def test_manual_review_delete_rechecks_and_deletes_expired_user(self):
        self.write_default_files()
        state_key = "s1:orphan"
        self.write_json(self.cleanup.STATE_FILE, {
            state_key: {
                "username": "orphan",
                "server_id": "s1",
                "source": "server_user",
                "cleanup_status": "manual_review",
                "last_state": {"days_remaining": 0},
            },
        })
        client = FakeClient("s1", {"orphan": self.expired_user()})
        original_multi_api = self.cleanup.MultiServerAPI
        self.cleanup.MultiServerAPI = lambda: FakeMultiAPI({"s1": client})
        self.addCleanup(setattr, self.cleanup, "MultiServerAPI", original_multi_api)
        record_id = self.cleanup._state_record_id(state_key)
        call = types.SimpleNamespace(
            id="callback-1",
            data=f"aec:rd:mr:{record_id}",
            from_user=types.SimpleNamespace(id=1),
            message=types.SimpleNamespace(chat=types.SimpleNamespace(id=10), message_id=20),
        )

        self.cleanup.handle_admin_expired_cleanup(call)

        state = self.read_json(self.cleanup.STATE_FILE)
        self.assertEqual(client.deleted, ["orphan"])
        self.assertEqual(state[state_key]["cleanup_status"], "deleted")
        self.assertEqual(state[state_key]["delete_result"], "deleted")
        self.assertEqual(self.cleanup._test_bot.answered_callbacks[-1][1], "User deleted.")

    def test_legacy_manual_review_callback_formats_still_work(self):
        self.write_default_files()
        state_key = "s1:orphan"
        self.write_json(self.cleanup.STATE_FILE, {
            state_key: {
                "username": "orphan",
                "server_id": "s1",
                "source": "server_user",
                "cleanup_status": "manual_review",
                "last_state": {"days_remaining": 0},
            },
        })
        record_id = self.cleanup._state_record_id(state_key)

        legacy_three_part = types.SimpleNamespace(
            id="callback-1",
            data=f"admin_expired_cleanup:review_keep:{record_id}",
            from_user=types.SimpleNamespace(id=1),
            message=types.SimpleNamespace(chat=types.SimpleNamespace(id=10), message_id=20),
        )
        self.cleanup.handle_admin_expired_cleanup(legacy_three_part)

        state = self.read_json(self.cleanup.STATE_FILE)
        self.assertEqual(state[state_key]["review_status"], "kept")
        self.assertEqual(self.cleanup._test_bot.answered_callbacks[-1][1], "Kept for later review.")

        legacy_four_part = types.SimpleNamespace(
            id="callback-2",
            data=f"admin_expired_cleanup:review_keep:manual_review:{record_id}",
            from_user=types.SimpleNamespace(id=1),
            message=types.SimpleNamespace(chat=types.SimpleNamespace(id=10), message_id=21),
        )
        self.cleanup.handle_admin_expired_cleanup(legacy_four_part)

        state = self.read_json(self.cleanup.STATE_FILE)
        self.assertEqual(state[state_key]["review_status"], "kept")
        self.assertEqual(self.cleanup._test_bot.answered_callbacks[-1][1], "Kept for later review.")

    def test_admin_cleanup_pagination_and_callback_route(self):
        self.write_default_files()
        state = {}
        for index in range(9):
            state[f"s1:user{index}"] = {
                "username": f"user{index}",
                "server_id": "s1",
                "source": "customer",
                "cleanup_status": "notified",
                "delete_after": "2026-06-09 10:00:00",
                "last_state": {"days_remaining": 0},
            }
        self.write_json(self.cleanup.STATE_FILE, state)

        markup = self.cleanup._build_admin_cleanup_markup(filter_key="due", page=0, now=self.now)
        self.assertIn("admin_expired_cleanup:list:due:1", self.callback_data_from_markup(markup))

        call = types.SimpleNamespace(
            id="callback-1",
            data="admin_expired_cleanup:list:due:1",
            from_user=types.SimpleNamespace(id=1),
            message=types.SimpleNamespace(chat=types.SimpleNamespace(id=10), message_id=20),
        )
        self.cleanup.handle_admin_expired_cleanup(call)

        self.assertEqual(self.cleanup._test_bot.answered_callbacks[-1][0], "callback-1")
        self.assertEqual(self.cleanup._test_bot.edited_messages[-1][1]["chat_id"], 10)
        self.assertIn("Page *2/2*", self.cleanup._test_bot.edited_messages[-1][0])

    def test_admin_cleanup_refresh_starts_scan_without_blocking_render(self):
        self.write_default_files()
        self.write_json(self.cleanup.STATE_FILE, {})
        started = []
        original_start = self.cleanup._start_cleanup_refresh_for_dashboard
        self.cleanup._start_cleanup_refresh_for_dashboard = lambda: started.append(True) or True
        self.addCleanup(setattr, self.cleanup, "_start_cleanup_refresh_for_dashboard", original_start)

        call = types.SimpleNamespace(
            id="callback-1",
            data="admin_expired_cleanup:refresh:queue:0",
            from_user=types.SimpleNamespace(id=1),
            message=types.SimpleNamespace(chat=types.SimpleNamespace(id=10), message_id=20),
        )
        self.cleanup.handle_admin_expired_cleanup(call)

        self.assertEqual(started, [True])
        self.assertEqual(self.cleanup._test_bot.edited_messages[-1][1]["chat_id"], 10)
        self.assertIn("View: *Pending*", self.cleanup._test_bot.edited_messages[-1][0])
        self.assertEqual(self.cleanup._test_bot.answered_callbacks[-1][1], "Scan started.")

    def test_admin_cleanup_text_shows_running_scan_state(self):
        self.write_default_files()
        self.write_json(self.cleanup.STATE_FILE, {})
        with self.cleanup._cleanup_refresh_lock:
            self.cleanup._cleanup_refresh_state.update({
                "running": True,
                "started_at": "2026-06-09 12:00:00",
                "finished_at": None,
                "error": None,
            })

        text = self.cleanup._build_admin_cleanup_text("en", filter_key="queue", page=0, now=self.now)

        self.assertIn("Scan: *running*", text)

    def test_admin_cleanup_export_current_filter_and_all_records(self):
        self.write_default_files()
        self.write_json(self.cleanup.STATE_FILE, {
            "s1:pending": {
                "username": "pending",
                "server_id": "s1",
                "source": "customer",
                "cleanup_status": "notified",
                "delete_after": "2099-06-09 14:00:00",
                "last_state": {"days_remaining": 0},
            },
            "s1:deleted": {
                "username": "deleted",
                "server_id": "s1",
                "source": "test",
                "cleanup_status": "deleted",
                "delete_result": "deleted",
                "deleted_at": "2026-06-09 12:00:00",
                "last_state": {"days_remaining": 0},
            },
            "s1:duplicate": {
                "username": "duplicate",
                "server_id": "s1",
                "source": "server_user",
                "cleanup_status": "manual_review",
                "manual_review_reason": "duplicate_payment",
                "last_state": {"days_remaining": 30},
            },
        })

        self.cleanup._send_cleanup_export(10, filter_key="queue")
        pending_payload = json.loads(self.cleanup._test_bot.sent_documents[-1][1].getvalue().decode("utf-8"))
        self.cleanup._send_cleanup_export(10, filter_key="duplicate_payment")
        duplicate_payload = json.loads(self.cleanup._test_bot.sent_documents[-1][1].getvalue().decode("utf-8"))
        self.cleanup._send_cleanup_export(10, filter_key="all")
        all_payload = json.loads(self.cleanup._test_bot.sent_documents[-1][1].getvalue().decode("utf-8"))

        self.assertEqual([record["username"] for record in pending_payload], ["pending"])
        self.assertEqual([record["username"] for record in duplicate_payload], ["duplicate"])
        self.assertEqual({record["username"] for record in all_payload}, {"pending", "deleted", "duplicate"})
        self.assertIn("reason_code", pending_payload[0])

    def test_expired_cleanup_notices_do_not_offer_renewal(self):
        spec = importlib.util.spec_from_file_location("translations_under_test", TRANSLATIONS_PATH)
        translations = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(translations)

        renewal_terms = ("renew", "продл", "تمدید", "uzald")
        notice_keys = ("expired_cleanup_customer_notice", "expired_cleanup_reseller_notice")
        for language, messages in translations.MESSAGE_TRANSLATIONS.items():
            for key in notice_keys:
                notice = messages[key].lower()
                for term in renewal_terms:
                    self.assertNotIn(term, notice, f"{language}.{key} mentions renewal")


if __name__ == "__main__":
    unittest.main()
