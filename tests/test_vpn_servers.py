import importlib.util
import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "core" / "scripts" / "telegrambot" / "utils" / "vpn_servers.py"


class DummyMarkup:
    def __init__(self, *args, **kwargs):
        self.buttons = []

    def add(self, *args, **kwargs):
        self.buttons.extend(args)
        return self


class DummyButton:
    def __init__(self, text, **kwargs):
        self.text = text
        self.callback_data = kwargs.get("callback_data")


class DummyBot:
    def __init__(self):
        self.replies = []
        self.edits = []
        self.answers = []
        self.sent_messages = []

    def message_handler(self, *args, **kwargs):
        return lambda func: func

    def callback_query_handler(self, *args, **kwargs):
        return lambda func: func

    def reply_to(self, *args, **kwargs):
        self.replies.append((args, kwargs))
        message = args[0]
        return types.SimpleNamespace(chat=message.chat, message_id=100 + len(self.replies))

    def edit_message_text(self, *args, **kwargs):
        self.edits.append((args, kwargs))

    def answer_callback_query(self, *args, **kwargs):
        self.answers.append((args, kwargs))

    def send_message(self, *args, **kwargs):
        self.sent_messages.append((args, kwargs))


class HoldingExecutor:
    def __init__(self):
        self.jobs = []

    def submit(self, fn, *args, **kwargs):
        self.jobs.append((fn, args, kwargs))
        return types.SimpleNamespace(done=lambda: False)

    def run_next(self):
        fn, args, kwargs = self.jobs.pop(0)
        return fn(*args, **kwargs)


class FakeMultiServerAPI:
    calls = []

    def get_server_statuses(self):
        self.__class__.calls.append("statuses")
        return [
            {
                "id": "s1",
                "name": "Server 1",
                "enabled": True,
                "healthy": True,
                "active_count": 3,
                "weight": 1,
                "load_ratio": 3.0,
            }
        ]


def load_vpn_servers_module():
    for name in list(sys.modules):
        if name == "utils" or name.startswith("utils."):
            sys.modules.pop(name, None)
    sys.modules.pop("telebot", None)

    telebot_stub = types.ModuleType("telebot")
    telebot_stub.types = types.SimpleNamespace(
        InlineKeyboardMarkup=DummyMarkup,
        InlineKeyboardButton=DummyButton,
    )
    sys.modules["telebot"] = telebot_stub

    utils_pkg = types.ModuleType("utils")
    utils_pkg.__path__ = []
    sys.modules["utils"] = utils_pkg

    bot = DummyBot()
    command_stub = types.ModuleType("utils.command")
    command_stub.bot = bot
    command_stub.is_admin = lambda user_id: user_id == 1
    sys.modules["utils.command"] = command_stub

    api_client_stub = types.ModuleType("utils.api_client")
    api_client_stub.MultiServerAPI = FakeMultiServerAPI
    api_client_stub.get_server_configs = lambda: [{"id": "s1", "name": "Server 1", "enabled": True}]
    api_client_stub.save_server_configs = lambda _servers: True
    sys.modules["utils.api_client"] = api_client_stub

    telegram_safe_stub = types.ModuleType("utils.telegram_safe")
    telegram_safe_stub.safe_answer_callback_query = lambda bot_obj, *args, **kwargs: bot_obj.answer_callback_query(*args, **kwargs)
    telegram_safe_stub.safe_edit_message_text = lambda bot_obj, *args, **kwargs: bot_obj.edit_message_text(*args, **kwargs)
    telegram_safe_stub.safe_reply_to = lambda bot_obj, *args, **kwargs: bot_obj.reply_to(*args, **kwargs)
    telegram_safe_stub.safe_send_message = lambda bot_obj, *args, **kwargs: bot_obj.send_message(*args, **kwargs)
    sys.modules["utils.telegram_safe"] = telegram_safe_stub

    FakeMultiServerAPI.calls = []
    spec = importlib.util.spec_from_file_location("vpn_servers_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module, bot


class VpnServersTests(unittest.TestCase):
    def test_show_vpn_servers_queues_status_snapshot(self):
        module, bot = load_vpn_servers_module()
        executor = HoldingExecutor()
        module.VPN_SERVER_MENU_EXECUTOR = executor
        message = types.SimpleNamespace(
            from_user=types.SimpleNamespace(id=1),
            chat=types.SimpleNamespace(id=10),
            message_id=20,
            text="VPN Servers",
        )

        module.show_vpn_servers(message)

        self.assertEqual(bot.replies, [])
        self.assertEqual(FakeMultiServerAPI.calls, [])
        self.assertEqual(len(executor.jobs), 1)

        executor.run_next()

        self.assertEqual(bot.replies[0][0][1], "Loading VPN servers...")
        self.assertIn("Server 1", bot.edits[0][0][0])
        self.assertEqual(FakeMultiServerAPI.calls, ["statuses"])


if __name__ == "__main__":
    unittest.main()
