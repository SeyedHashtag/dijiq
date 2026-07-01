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
    / "broadcast.py"
)


class DummyMarkup:
    def __init__(self, *args, **kwargs):
        pass

    def add(self, *args, **kwargs):
        return self

    def row(self, *args, **kwargs):
        return self


class DummyButton:
    def __init__(self, *args, **kwargs):
        pass


class DummyChat:
    id = 999


class DummyStatusMessage:
    chat = DummyChat()
    message_id = 123


class DummyBot:
    def __init__(self):
        self.next_steps = []

    def message_handler(self, *args, **kwargs):
        return lambda func: func

    def reply_to(self, *args, **kwargs):
        return DummyStatusMessage()

    def register_next_step_handler(self, *args):
        self.next_steps.append(args)

    def send_message(self, *args, **kwargs):
        pass

    def edit_message_text(self, *args, **kwargs):
        pass

    def send_document(self, *args, **kwargs):
        pass


def install_stubs():
    telebot_stub = types.ModuleType("telebot")
    telebot_stub.types = types.SimpleNamespace(
        ReplyKeyboardMarkup=DummyMarkup,
        KeyboardButton=DummyButton,
    )
    sys.modules["telebot"] = telebot_stub

    utils_pkg = types.ModuleType("utils")
    utils_pkg.__path__ = []
    sys.modules["utils"] = utils_pkg

    command_stub = types.ModuleType("utils.command")
    command_stub.bot = DummyBot()
    command_stub.ADMIN_USER_IDS = [1]
    command_stub.is_admin = lambda user_id: user_id == 1
    sys.modules["utils.command"] = command_stub

    common_stub = types.ModuleType("utils.common")
    common_stub.create_main_markup = lambda *args, **kwargs: DummyMarkup()
    sys.modules["utils.common"] = common_stub

    api_client_stub = types.ModuleType("utils.api_client")
    api_client_stub.MultiServerAPI = lambda: types.SimpleNamespace(iter_all_users=lambda: iter(()))
    sys.modules["utils.api_client"] = api_client_stub

    reseller_stub = types.ModuleType("utils.reseller")
    reseller_stub.get_all_resellers = lambda: {}
    sys.modules["utils.reseller"] = reseller_stub

    test_config_store_stub = types.ModuleType("utils.test_config_store")
    test_config_store_stub.load_test_configs = lambda path: {}
    sys.modules["utils.test_config_store"] = test_config_store_stub
    utils_pkg.test_config_store = test_config_store_stub


def load_broadcast_module():
    install_stubs()
    spec = importlib.util.spec_from_file_location("broadcast_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class BroadcastTargetingTests(unittest.TestCase):
    def test_paid_user_targets_are_collected_from_all_server_records(self):
        broadcast = load_broadcast_module()

        class FakeMultiServerAPI:
            def iter_all_users(self):
                yield object(), "s111abc", {"blocked": False}
                yield object(), "222t", {"blocked": True}
                yield object(), "sell333t", {"blocked": False}
                yield object(), "not-a-paid-user", {"blocked": False}

        broadcast.MultiServerAPI = FakeMultiServerAPI
        broadcast.load_failed_broadcast_users = lambda: set()

        all_ids, all_excluded = broadcast.get_user_ids("all")
        active_ids, active_excluded = broadcast.get_user_ids("active")
        expired_ids, expired_excluded = broadcast.get_user_ids("expired")

        self.assertEqual(set(all_ids), {"111", "222", "333"})
        self.assertEqual(all_excluded, {})
        self.assertEqual(set(active_ids), {"111", "333"})
        self.assertEqual(active_excluded, {})
        self.assertEqual(set(expired_ids), {"222"})
        self.assertEqual(expired_excluded, {})

    def test_paid_user_targeting_returns_unpackable_empty_result(self):
        broadcast = load_broadcast_module()

        class EmptyMultiServerAPI:
            def iter_all_users(self):
                return iter(())

        broadcast.MultiServerAPI = EmptyMultiServerAPI

        user_ids, excluded = broadcast.get_user_ids("all")

        self.assertEqual(user_ids, [])
        self.assertEqual(excluded, {})

    def test_recovered_historical_test_user_is_available_to_broadcasts(self):
        broadcast = load_broadcast_module()
        broadcast.test_config_store.load_test_configs = lambda path: {
            "12345": {
                "telegram_id": 12345,
                "used_at": "2020-01-01 12:00:00",
                "historical_configs": [{"username": "t12345", "server_id": "s1"}],
            }
        }
        broadcast.load_failed_broadcast_users = lambda: set()

        user_ids, excluded = broadcast.get_user_ids("all_test")

        self.assertEqual(user_ids, ["12345"])
        self.assertEqual(excluded, {})


class BroadcastSendTests(unittest.TestCase):
    def make_message(self, text):
        return types.SimpleNamespace(
            text=text,
            from_user=types.SimpleNamespace(id=1),
            chat=types.SimpleNamespace(id=999),
        )

    def test_empty_message_re_registers_broadcast_step(self):
        broadcast = load_broadcast_module()

        broadcast.send_broadcast(self.make_message("   "), "all", "All Paid Users")

        self.assertEqual(len(broadcast.bot.next_steps), 1)
        self.assertIs(broadcast.bot.next_steps[0][1], broadcast.send_broadcast)
        self.assertEqual(broadcast.bot.next_steps[0][2:], ("all", "All Paid Users", None))

    def test_only_permanent_failures_are_saved_to_failed_exclusions(self):
        broadcast = load_broadcast_module()
        saved_failed_users = []

        class SendingBot(DummyBot):
            def __init__(self):
                super().__init__()
                self.sent_documents = 0

            def send_message(self, user_id, text):
                if user_id == 1:
                    raise Exception("Too Many Requests: retry after 10")
                if user_id == 2:
                    raise Exception("Forbidden: bot was blocked by the user")

            def send_document(self, *args, **kwargs):
                self.sent_documents += 1

        broadcast.bot = SendingBot()
        broadcast.get_user_ids = lambda target: (["1", "2", "3"], {})
        broadcast.load_failed_broadcast_users = lambda: set()
        broadcast.save_failed_broadcast_users = lambda users: saved_failed_users.extend(sorted(users))

        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = os.path.join(tmpdir, "broadcast.log")
            with open(log_path, "w") as log_file:
                log_file.write("log")
            broadcast.generate_broadcast_log = lambda **kwargs: log_path

            broadcast.send_broadcast(self.make_message("hello"), "all", "All Paid Users")

        self.assertEqual(saved_failed_users, ["2"])
        self.assertEqual(broadcast.bot.sent_documents, 1)


if __name__ == "__main__":
    unittest.main()
