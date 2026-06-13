import importlib.util
import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMMON_PATH = ROOT / "core" / "scripts" / "telegrambot" / "utils" / "common.py"
DELETEUSER_PATH = ROOT / "core" / "scripts" / "telegrambot" / "utils" / "deleteuser.py"
EDITUSER_PATH = ROOT / "core" / "scripts" / "telegrambot" / "utils" / "edituser.py"


class DummyMarkup:
    def __init__(self, *args, **kwargs):
        self.rows = []
        self.buttons = []

    def row(self, *buttons):
        self.rows.append(buttons)
        return self

    def add(self, *buttons):
        self.buttons.extend(buttons)
        return self


class DummyButton:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs


class DummyBot:
    def __init__(self):
        self.callback_answers = []
        self.cleared_chat_ids = []
        self.edited_messages = []
        self.replies = []
        self.chat_actions = []

    def callback_query_handler(self, *args, **kwargs):
        return lambda func: func

    def message_handler(self, *args, **kwargs):
        return lambda func: func

    def answer_callback_query(self, callback_id, *args, **kwargs):
        self.callback_answers.append((callback_id, args, kwargs))

    def clear_step_handler_by_chat_id(self, chat_id):
        self.cleared_chat_ids.append(chat_id)

    def edit_message_text(self, *args, **kwargs):
        self.edited_messages.append((args, kwargs))

    def reply_to(self, *args, **kwargs):
        self.replies.append((args, kwargs))
        return types.SimpleNamespace(chat=types.SimpleNamespace(id=kwargs.get("chat_id")), message_id=123)

    def send_chat_action(self, *args, **kwargs):
        self.chat_actions.append((args, kwargs))


class ForbiddenMultiServerAPI:
    def __init__(self):
        raise AssertionError("MultiServerAPI should not be used for admin menu buttons")


def clear_test_modules():
    for name in list(sys.modules):
        if name == "utils" or name.startswith("utils."):
            sys.modules.pop(name, None)
    sys.modules.pop("telebot", None)
    sys.modules.pop("qrcode", None)


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def install_stubs():
    clear_test_modules()
    bot = DummyBot()

    telebot_stub = types.ModuleType("telebot")
    telebot_stub.types = types.SimpleNamespace(
        InlineKeyboardMarkup=DummyMarkup,
        InlineKeyboardButton=DummyButton,
        ReplyKeyboardMarkup=DummyMarkup,
    )
    sys.modules["telebot"] = telebot_stub
    sys.modules["qrcode"] = types.SimpleNamespace(make=lambda *_args, **_kwargs: None)

    utils_pkg = types.ModuleType("utils")
    utils_pkg.__path__ = []
    sys.modules["utils"] = utils_pkg

    command_stub = types.ModuleType("utils.command")
    command_stub.bot = bot
    command_stub.is_admin = lambda _user_id: True
    sys.modules["utils.command"] = command_stub

    api_client_stub = types.ModuleType("utils.api_client")
    api_client_stub.APIClient = object
    api_client_stub.MultiServerAPI = ForbiddenMultiServerAPI
    sys.modules["utils.api_client"] = api_client_stub

    common = load_module(COMMON_PATH, "utils.common")
    return bot, common


def load_deleteuser():
    bot, _common = install_stubs()
    return load_module(DELETEUSER_PATH, "deleteuser_under_test"), bot


def load_edituser():
    bot, _common = install_stubs()
    return load_module(EDITUSER_PATH, "edituser_under_test"), bot


def make_call():
    return types.SimpleNamespace(
        id="callback-id",
        message=types.SimpleNamespace(chat=types.SimpleNamespace(id=555), message_id=777),
    )


def make_message(text):
    return types.SimpleNamespace(
        text=text,
        chat=types.SimpleNamespace(id=555),
        from_user=types.SimpleNamespace(id=1),
    )


class AdminPromptCancellationTests(unittest.TestCase):
    def test_cancel_delete_clears_next_step_handler(self):
        deleteuser, bot = load_deleteuser()

        deleteuser.handle_cancel_delete(make_call())

        self.assertEqual(bot.callback_answers[0][0], "callback-id")
        self.assertEqual(bot.cleared_chat_ids, [555])
        self.assertEqual(bot.edited_messages[0][1]["chat_id"], 555)
        self.assertEqual(bot.edited_messages[0][1]["message_id"], 777)

    def test_cancel_show_user_clears_next_step_handler(self):
        edituser, bot = load_edituser()

        edituser.handle_cancel_show_user(make_call())

        self.assertEqual(bot.callback_answers[0][0], "callback-id")
        self.assertEqual(bot.cleared_chat_ids, [555])
        self.assertEqual(bot.edited_messages[0][1]["chat_id"], 555)
        self.assertEqual(bot.edited_messages[0][1]["message_id"], 777)

    def test_delete_user_prompt_treats_admin_menu_button_as_cancel(self):
        deleteuser, bot = load_deleteuser()

        deleteuser.process_delete_user(make_message("💼 Manage Resellers"))

        self.assertEqual(len(bot.replies), 1)
        self.assertIn("Operation canceled.", bot.replies[0][0][1])
        self.assertEqual(bot.chat_actions, [])

    def test_show_user_prompt_treats_admin_menu_button_as_cancel(self):
        edituser, bot = load_edituser()

        edituser.process_show_user(make_message("💼 Manage Resellers"))

        self.assertEqual(len(bot.replies), 1)
        self.assertIn("Operation canceled.", bot.replies[0][0][1])
        self.assertEqual(bot.chat_actions, [])


if __name__ == "__main__":
    unittest.main()
