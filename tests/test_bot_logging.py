import importlib.util
import logging
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path


BOT_LOGGING_PATH = (
    Path(__file__).resolve().parents[1]
    / "core"
    / "scripts"
    / "telegrambot"
    / "utils"
    / "bot_logging.py"
)
COMMON_PATH = (
    Path(__file__).resolve().parents[1]
    / "core"
    / "scripts"
    / "telegrambot"
    / "utils"
    / "common.py"
)
BOT_LOGS_PATH = (
    Path(__file__).resolve().parents[1]
    / "core"
    / "scripts"
    / "telegrambot"
    / "utils"
    / "bot_logs.py"
)
TELEGRAM_SAFE_PATH = (
    Path(__file__).resolve().parents[1]
    / "core"
    / "scripts"
    / "telegrambot"
    / "utils"
    / "telegram_safe.py"
)


def load_bot_logging():
    spec = importlib.util.spec_from_file_location("bot_logging_under_test", BOT_LOGGING_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_telegram_safe():
    spec = importlib.util.spec_from_file_location("telegram_safe_under_test", TELEGRAM_SAFE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class DummyUser:
    id = 123


class DummyChat:
    id = 456


class DummyMessage:
    from_user = DummyUser()
    chat = DummyChat()
    text = "hello from a button"
    content_type = "text"


class DummyCallback:
    from_user = DummyUser()
    message = DummyMessage()
    data = "purchase:30"


class DummyBot:
    def __init__(self):
        self.message_handlers = []
        self.callback_handlers = []

    def message_handler(self, *args, **kwargs):
        def decorator(func):
            self.message_handlers.append(func)
            return func

        return decorator

    def callback_query_handler(self, *args, **kwargs):
        def decorator(func):
            self.callback_handlers.append(func)
            return func

        return decorator


class BotLoggingTests(unittest.TestCase):
    def setUp(self):
        self.original_env = {
            name: os.environ.get(name)
            for name in (
                "DIJIQ_BOT_LOG_FILE",
                "DIJIQ_BOT_LOG_LEVEL",
                "DIJQ_SLOW_HANDLER_MS",
                "DIJIQ_SLOW_HANDLER_MS",
                "TELEGRAM_BOT_WORKERS",
            )
        }

    def tearDown(self):
        for name, value in self.original_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    def test_logging_path_and_env_defaults(self):
        bot_logging = load_bot_logging()
        self.assertEqual(
            bot_logging.get_bot_log_file(),
            "/etc/dijiq/core/scripts/telegrambot/logs/bot.log",
        )
        self.assertEqual(bot_logging.get_slow_handler_ms(), 1000)
        self.assertEqual(bot_logging.get_telegram_worker_count(), 8)

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "bot.log")
            os.environ["DIJIQ_BOT_LOG_FILE"] = log_file
            os.environ["DIJIQ_BOT_LOG_LEVEL"] = "DEBUG"

            before_handlers = list(logging.getLogger().handlers)
            configured_path = bot_logging.configure_logging()
            logging.getLogger("dijiq.bot.test").debug("debug test line")

            self.assertEqual(configured_path, os.path.abspath(log_file))
            self.assertTrue(os.path.exists(log_file))
            with open(log_file, "r", encoding="utf-8") as f:
                self.assertIn("debug test line", f.read())

            for handler in list(logging.getLogger().handlers):
                if handler not in before_handlers:
                    logging.getLogger().removeHandler(handler)
                    handler.close()

    def test_handler_wrapper_logs_message_and_callback_timing(self):
        bot_logging = load_bot_logging()
        bot = DummyBot()
        bot_logging.instrument_bot(bot)

        @bot.message_handler(func=lambda message: True)
        def handle_message(message):
            return "ok"

        @bot.callback_query_handler(func=lambda call: True)
        def handle_callback(call):
            return "done"

        with self.assertLogs("dijiq.bot.handlers", level="INFO") as captured:
            self.assertEqual(bot.message_handlers[0](DummyMessage()), "ok")
            self.assertEqual(bot.callback_handlers[0](DummyCallback()), "done")

        output = "\n".join(captured.output)
        self.assertIn("handler_start kind=message handler=handle_message", output)
        self.assertIn("handler_end kind=message handler=handle_message", output)
        self.assertIn("text='hello from a button'", output)
        self.assertIn("handler_start kind=callback handler=handle_callback", output)
        self.assertIn("data='purchase:30'", output)

    def test_handler_wrapper_logs_exceptions(self):
        bot_logging = load_bot_logging()
        bot = DummyBot()
        bot_logging.instrument_bot(bot)

        @bot.callback_query_handler(func=lambda call: True)
        def broken_callback(call):
            raise RuntimeError("boom")

        with self.assertLogs("dijiq.bot.handlers", level="ERROR") as captured:
            with self.assertRaises(RuntimeError):
                bot.callback_handlers[0](DummyCallback())

        self.assertIn("handler_error kind=callback handler=broken_callback", "\n".join(captured.output))


class TelegramSafeTests(unittest.TestCase):
    def setUp(self):
        self.original_env = {
            "DIJIQ_TELEGRAM_TIMEOUT_SECONDS": os.environ.get("DIJIQ_TELEGRAM_TIMEOUT_SECONDS"),
            "DIJIQ_CALLBACK_TIMEOUT_SECONDS": os.environ.get("DIJIQ_CALLBACK_TIMEOUT_SECONDS"),
        }

    def tearDown(self):
        for name, value in self.original_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    def test_safe_answer_callback_uses_short_timeout_and_ignores_old_callback(self):
        telegram_safe = load_telegram_safe()
        os.environ["DIJIQ_CALLBACK_TIMEOUT_SECONDS"] = "4"

        class Bot:
            def __init__(self):
                self.calls = []

            def answer_callback_query(self, *args, **kwargs):
                self.calls.append((args, kwargs))
                raise RuntimeError("Bad Request: query is too old and response timeout expired")

        bot = Bot()

        self.assertIsNone(telegram_safe.safe_answer_callback_query(bot, "callback-1"))
        self.assertEqual(bot.calls[0][0], ("callback-1",))
        self.assertEqual(bot.calls[0][1]["timeout"], 4)

    def test_safe_edit_retries_without_timeout_for_test_doubles(self):
        telegram_safe = load_telegram_safe()

        class Bot:
            def __init__(self):
                self.calls = []

            def edit_message_text(self, *args, **kwargs):
                self.calls.append((args, kwargs))
                if "timeout" in kwargs:
                    raise TypeError("unexpected keyword argument 'timeout'")
                return "ok"

        bot = Bot()

        self.assertEqual(telegram_safe.safe_edit_message_text(bot, "hello", chat_id=1, message_id=2), "ok")
        self.assertIn("timeout", bot.calls[0][1])
        self.assertNotIn("timeout", bot.calls[1][1])

    def test_safe_send_raises_unexpected_errors(self):
        telegram_safe = load_telegram_safe()

        class Bot:
            def send_message(self, *args, **kwargs):
                raise RuntimeError("network exploded")

        with self.assertRaises(RuntimeError):
            telegram_safe.safe_send_message(Bot(), 123, "hello")

    def test_install_safe_telegram_methods_wraps_direct_bot_calls(self):
        telegram_safe = load_telegram_safe()
        os.environ["DIJIQ_TELEGRAM_TIMEOUT_SECONDS"] = "6"

        class Bot:
            def __init__(self):
                self.calls = []

            def edit_message_text(self, *args, **kwargs):
                self.calls.append((args, kwargs))
                raise RuntimeError("Bad Request: message is not modified")

        bot = telegram_safe.install_safe_telegram_methods(Bot())

        self.assertIsNone(bot.edit_message_text("same", chat_id=1, message_id=2))
        self.assertEqual(bot.calls[0][1]["timeout"], 6)
        self.assertIs(telegram_safe.install_safe_telegram_methods(bot), bot)
        self.assertTrue(getattr(bot, "_dijiq_safe_telegram_installed"))

    def test_wrapped_reply_to_can_call_wrapped_send_message_with_timeout_kwarg(self):
        telegram_safe = load_telegram_safe()

        class Bot:
            def __init__(self):
                self.send_calls = []

            def send_message(self, *args, **kwargs):
                self.send_calls.append((args, kwargs))
                return "sent"

            def reply_to(self, message, text, **kwargs):
                return self.send_message(message.chat.id, text, **kwargs)

        bot = telegram_safe.install_safe_telegram_methods(Bot())
        message = types.SimpleNamespace(chat=types.SimpleNamespace(id=123))

        self.assertEqual(bot.reply_to(message, "hello"), "sent")
        self.assertEqual(bot.send_calls[0][0], (123, "hello"))
        self.assertIn("timeout", bot.send_calls[0][1])


class AdminLogButtonTests(unittest.TestCase):
    def test_admin_main_menu_contains_bot_logs_button(self):
        telebot_stub = types.ModuleType("telebot")
        telebot_stub.types = types.SimpleNamespace(
            ReplyKeyboardMarkup=lambda *args, **kwargs: None,
            InlineKeyboardMarkup=lambda *args, **kwargs: None,
            InlineKeyboardButton=lambda *args, **kwargs: None,
        )
        sys.modules["telebot"] = telebot_stub

        spec = importlib.util.spec_from_file_location("common_under_test", COMMON_PATH)
        common = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = common
        spec.loader.exec_module(common)

        self.assertIn("📄 Bot Logs", common.ADMIN_MAIN_MENU_BUTTONS)

    def load_bot_logs_module(self, log_file):
        for name in ("utils", "utils.command", "utils.bot_logging", "bot_logs_under_test"):
            sys.modules.pop(name, None)

        utils_pkg = types.ModuleType("utils")
        utils_pkg.__path__ = []
        sys.modules["utils"] = utils_pkg

        bot = types.SimpleNamespace(
            replies=[],
            documents=[],
            message_handler=lambda *args, **kwargs: (lambda func: func),
        )
        bot.reply_to = lambda message, text, **kwargs: bot.replies.append({"message": message, "text": text, "kwargs": kwargs})

        def send_document(chat_id, document, **kwargs):
            bot.documents.append({
                "chat_id": chat_id,
                "content": document.read(),
                "kwargs": kwargs,
            })

        bot.send_document = send_document

        command_stub = types.ModuleType("utils.command")
        command_stub.bot = bot
        command_stub.is_admin = lambda user_id: user_id == 123
        sys.modules["utils.command"] = command_stub

        bot_logging_stub = types.ModuleType("utils.bot_logging")
        bot_logging_stub.get_bot_log_file = lambda: log_file
        sys.modules["utils.bot_logging"] = bot_logging_stub

        spec = importlib.util.spec_from_file_location("bot_logs_under_test", BOT_LOGS_PATH)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module, bot

    def make_message(self):
        return types.SimpleNamespace(
            from_user=types.SimpleNamespace(id=123),
            chat=types.SimpleNamespace(id=456),
            text="📄 Bot Logs",
        )

    def test_admin_log_handler_reports_missing_or_empty_log_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "missing.log")
            module, bot = self.load_bot_logs_module(log_file)

            module.send_bot_logs(self.make_message())
            self.assertEqual(bot.replies[-1]["text"], "Bot log file is missing or empty.")

            open(log_file, "w", encoding="utf-8").close()
            module.send_bot_logs(self.make_message())
            self.assertEqual(bot.replies[-1]["text"], "Bot log file is missing or empty.")

    def test_admin_log_handler_sends_existing_log_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "bot.log")
            with open(log_file, "w", encoding="utf-8") as f:
                f.write("line one\n")

            module, bot = self.load_bot_logs_module(log_file)
            module.send_bot_logs(self.make_message())

            self.assertEqual(bot.documents[-1]["chat_id"], 456)
            self.assertEqual(bot.documents[-1]["content"], b"line one\n")
            self.assertEqual(bot.documents[-1]["kwargs"]["visible_file_name"], "bot.log")


if __name__ == "__main__":
    unittest.main()
