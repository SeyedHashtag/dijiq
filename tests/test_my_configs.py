import importlib.util
import sys
import types
import unittest
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "core"
    / "scripts"
    / "telegrambot"
    / "utils"
    / "my_configs.py"
)


class DummyBot:
    def __init__(self):
        self.chat_actions = []
        self.replies = []
        self.sent_messages = []

    def message_handler(self, *args, **kwargs):
        return lambda func: func

    def callback_query_handler(self, *args, **kwargs):
        return lambda func: func

    def send_chat_action(self, *args, **kwargs):
        self.chat_actions.append((args, kwargs))

    def reply_to(self, *args, **kwargs):
        self.replies.append((args, kwargs))

    def send_message(self, *args, **kwargs):
        self.sent_messages.append((args, kwargs))

    def edit_message_text(self, *args, **kwargs):
        return None

    def answer_callback_query(self, *args, **kwargs):
        return None

    def delete_message(self, *args, **kwargs):
        return None

    def send_photo(self, *args, **kwargs):
        return None


class DummyMarkup:
    def __init__(self, *args, **kwargs):
        self.buttons = []

    def add(self, *buttons, **kwargs):
        self.buttons.extend(buttons)


class DummyButton:
    def __init__(self, text, **kwargs):
        self.text = text
        self.callback_data = kwargs.get("callback_data")


class FakeClient:
    def __init__(self, server_id):
        self.server_id = server_id


class FakeMultiServerAPI:
    servers = [
        {"id": "enabled", "enabled": True},
        {"id": "disabled", "enabled": False},
    ]
    users_by_include_disabled = {True: [], False: []}
    iter_calls = []
    instances = []

    def __init__(self):
        self.servers = list(self.__class__.servers)
        self.last_user_snapshot_cache_hit = True
        self.__class__.instances.append(self)

    def iter_all_users(self, include_disabled=True, force_refresh=False):
        self.__class__.iter_calls.append({
            "include_disabled": include_disabled,
            "force_refresh": force_refresh,
        })
        yield from self.__class__.users_by_include_disabled[bool(include_disabled)]

    def find_user(self, username, preferred_server_id=None):
        return None, None


def install_stubs():
    telebot_stub = types.ModuleType("telebot")
    telebot_stub.types = types.SimpleNamespace(
        InlineKeyboardMarkup=DummyMarkup,
        InlineKeyboardButton=DummyButton,
    )
    sys.modules["telebot"] = telebot_stub
    sys.modules["dotenv"] = types.SimpleNamespace(load_dotenv=lambda *args, **kwargs: None)

    utils_pkg = types.ModuleType("utils")
    utils_pkg.__path__ = []
    sys.modules["utils"] = utils_pkg

    command_stub = types.ModuleType("utils.command")
    command_stub.bot = DummyBot()
    sys.modules["utils.command"] = command_stub

    api_client_stub = types.ModuleType("utils.api_client")
    api_client_stub.APIClient = object
    api_client_stub.MultiServerAPI = FakeMultiServerAPI
    sys.modules["utils.api_client"] = api_client_stub

    edit_plans_stub = types.ModuleType("utils.edit_plans")
    edit_plans_stub.load_plans = lambda: {}
    sys.modules["utils.edit_plans"] = edit_plans_stub

    translations_stub = types.ModuleType("utils.translations")
    translations_stub.BUTTON_TRANSLATIONS = {"en": {"my_configs": "📱 My Configs"}}
    translations_stub.get_message_text = lambda language, key: {
        "no_active_configs": "No active configs",
    }.get(key, key)
    translations_stub.get_button_text = lambda language, key: key
    sys.modules["utils.translations"] = translations_stub

    language_stub = types.ModuleType("utils.language")
    language_stub.get_user_language = lambda user_id: "en"
    sys.modules["utils.language"] = language_stub

    sys.modules["qrcode"] = types.SimpleNamespace(make=lambda *args, **kwargs: None)


install_stubs()
spec = importlib.util.spec_from_file_location("my_configs_under_test", MODULE_PATH)
my_configs_module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = my_configs_module
spec.loader.exec_module(my_configs_module)


class MyConfigsTests(unittest.TestCase):
    def setUp(self):
        FakeMultiServerAPI.users_by_include_disabled = {True: [], False: []}
        FakeMultiServerAPI.iter_calls = []
        FakeMultiServerAPI.instances = []
        my_configs_module.bot.replies = []
        my_configs_module.bot.chat_actions = []
        self.displayed_configs = []
        my_configs_module.display_config = lambda *args, **kwargs: self.displayed_configs.append((args, kwargs))

    def make_message(self, user_id=123):
        return types.SimpleNamespace(
            text="📱 My Configs",
            from_user=types.SimpleNamespace(id=user_id),
            chat=types.SimpleNamespace(id=456),
        )

    def test_my_configs_scans_once_and_prefers_paid_configs_over_test_configs(self):
        enabled_client = FakeClient("enabled")
        FakeMultiServerAPI.users_by_include_disabled[False] = [
            (enabled_client, "t123a", {"max_download_bytes": 10}),
            (enabled_client, "s123a", {"max_download_bytes": 20}),
        ]

        my_configs_module.my_configs(self.make_message())

        self.assertEqual(FakeMultiServerAPI.iter_calls, [{"include_disabled": False, "force_refresh": False}])
        self.assertEqual(len(self.displayed_configs), 1)
        self.assertEqual(self.displayed_configs[0][0][1], "s123a")
        self.assertEqual(my_configs_module.bot.replies, [])

    def test_my_configs_excludes_disabled_servers_for_customer_lookup(self):
        disabled_client = FakeClient("disabled")
        FakeMultiServerAPI.users_by_include_disabled[True] = [
            (disabled_client, "s123a", {"max_download_bytes": 20}),
        ]

        my_configs_module.my_configs(self.make_message())

        self.assertEqual(FakeMultiServerAPI.iter_calls, [{"include_disabled": False, "force_refresh": False}])
        self.assertEqual(self.displayed_configs, [])
        self.assertEqual(my_configs_module.bot.replies[0][0][1], "No active configs")


if __name__ == "__main__":
    unittest.main()
