import importlib.util
import os
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
    / "command.py"
)


class FakeTeleBot:
    calls = []

    def __init__(self, *args, **kwargs):
        self.calls.append((args, kwargs))


def load_command_module(worker_threads):
    original_env = {
        key: os.environ.get(key)
        for key in ("API_TOKEN", "ADMIN_USER_IDS", "BOT_WORKER_THREADS")
    }
    os.environ["API_TOKEN"] = "bot-token"
    os.environ["ADMIN_USER_IDS"] = "[1,2]"
    if worker_threads is None:
        os.environ.pop("BOT_WORKER_THREADS", None)
    else:
        os.environ["BOT_WORKER_THREADS"] = worker_threads

    FakeTeleBot.calls = []
    telebot_stub = types.ModuleType("telebot")
    telebot_stub.TeleBot = FakeTeleBot
    telebot_stub.types = types.SimpleNamespace()
    sys.modules["telebot"] = telebot_stub
    sys.modules["dotenv"] = types.SimpleNamespace(load_dotenv=lambda *args, **kwargs: None)

    try:
        spec = importlib.util.spec_from_file_location("command_under_test", MODULE_PATH)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module, list(FakeTeleBot.calls)
    finally:
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        sys.modules.pop("command_under_test", None)


class BotWorkerThreadTests(unittest.TestCase):
    def tearDown(self):
        sys.modules.pop("telebot", None)

    def test_bot_uses_configured_worker_threads(self):
        module, calls = load_command_module("12")

        self.assertEqual(module.BOT_WORKER_THREADS, 12)
        self.assertEqual(calls[0][1]["threaded"], True)
        self.assertEqual(calls[0][1]["num_threads"], 12)

    def test_bot_worker_threads_falls_back_to_default(self):
        module, calls = load_command_module("not-a-number")

        self.assertEqual(module.BOT_WORKER_THREADS, 8)
        self.assertEqual(calls[0][1]["num_threads"], 8)


if __name__ == "__main__":
    unittest.main()
