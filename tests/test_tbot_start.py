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
    / "tbot.py"
)


class DummyBot:
    def __init__(self, events):
        self.events = events
        self.replies = []
        self.sent_messages = []
        self.message_handlers = []

    def message_handler(self, *args, **kwargs):
        def decorator(func):
            self.message_handlers.append((func, args, kwargs))
            return func

        return decorator

    def reply_to(self, *args, **kwargs):
        self.events.append("reply")
        self.replies.append((args, kwargs))

    def send_message(self, *args, **kwargs):
        self.events.append("send")
        self.sent_messages.append((args, kwargs))

    def polling(self, *args, **kwargs):
        return None


def load_tbot_module():
    for name in ("telebot", "utils", "utils.telegram_safe", "tbot_under_test"):
        sys.modules.pop(name, None)

    events = []
    bot = DummyBot(events)

    telebot_stub = types.ModuleType("telebot")
    telebot_stub.types = types.SimpleNamespace()
    sys.modules["telebot"] = telebot_stub

    utils_stub = types.ModuleType("utils")
    utils_stub.__path__ = []
    utils_stub.bot = bot
    utils_stub.process_referral = lambda *args, **kwargs: (False, None)
    utils_stub.get_user_language = lambda user_id: "en"
    utils_stub.get_message_text = lambda language, key: "{referrer_id}" if key == "referral_registered" else key
    utils_stub.is_admin = lambda user_id: False
    utils_stub.create_main_markup = lambda *args, **kwargs: {"markup": kwargs}
    utils_stub.has_used_test_config = lambda user_id: False
    utils_stub.is_test_creation_disabled = lambda: False
    utils_stub.add_to_waiting_list = lambda *args, **kwargs: events.append("waitlist")
    utils_stub.create_test_config = lambda *args, **kwargs: events.append("create_test_config")
    sys.modules["utils"] = utils_stub

    telegram_safe_stub = types.ModuleType("utils.telegram_safe")
    telegram_safe_stub.safe_reply_to = lambda bot_obj, *args, **kwargs: bot_obj.reply_to(*args, **kwargs)
    telegram_safe_stub.safe_send_message = lambda bot_obj, *args, **kwargs: bot_obj.send_message(*args, **kwargs)
    sys.modules["utils.telegram_safe"] = telegram_safe_stub

    spec = importlib.util.spec_from_file_location("tbot_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module, bot, events


class TBotStartTests(unittest.TestCase):
    def tearDown(self):
        module = sys.modules.get("tbot_under_test")
        executor = getattr(module, "START_TEST_CONFIG_EXECUTOR", None)
        if executor is not None and hasattr(executor, "shutdown"):
            executor.shutdown(wait=False, cancel_futures=True)

    def make_message(self, user_id=123, text="/start"):
        return types.SimpleNamespace(
            text=text,
            from_user=types.SimpleNamespace(
                id=user_id,
                username="buyer",
                first_name="Buyer",
                last_name="Example",
            ),
            chat=types.SimpleNamespace(id=456),
        )

    def test_start_replies_before_enqueueing_automatic_test_config(self):
        module, bot, events = load_tbot_module()

        def enqueue(*args, **kwargs):
            events.append("enqueue")
            return True

        module.enqueue_automatic_test_config = enqueue

        module.send_welcome(self.make_message())

        self.assertEqual(events, ["reply", "enqueue"])
        self.assertEqual(bot.replies[0][0][1], "Welcome!")

    def test_orphaned_admin_cancel_restores_admin_main_keyboard(self):
        module, bot, events = load_tbot_module()
        module.is_admin = lambda user_id: user_id == 123
        message = self.make_message(text="❌ Cancel")

        module.handle_admin_cancel_fallback(message)

        self.assertEqual(events, ["reply"])
        self.assertEqual(bot.replies[0][0][1], "Operation canceled.")
        self.assertEqual(
            bot.replies[0][1]["reply_markup"],
            {"markup": {"is_admin": True}},
        )

    def test_admin_cancel_fallback_filter_is_admin_and_exact_text_only(self):
        module, bot, _events = load_tbot_module()
        module.is_admin = lambda user_id: user_id == 123
        handler = next(
            item for item in bot.message_handlers
            if item[0] is module.handle_admin_cancel_fallback
        )
        predicate = handler[2]["func"]

        self.assertTrue(predicate(self.make_message(text="❌ Cancel")))
        self.assertFalse(predicate(self.make_message(user_id=999, text="❌ Cancel")))
        self.assertFalse(predicate(self.make_message(text="Cancel")))

    def test_start_job_enqueue_dedupes_per_user(self):
        module, _bot, _events = load_tbot_module()

        class FakeExecutor:
            def __init__(self):
                self.submissions = []

            def submit(self, *args, **kwargs):
                self.submissions.append((args, kwargs))

            def shutdown(self, *args, **kwargs):
                return None

        fake_executor = FakeExecutor()
        module.START_TEST_CONFIG_EXECUTOR.shutdown(wait=False, cancel_futures=True)
        module.START_TEST_CONFIG_EXECUTOR = fake_executor
        module.START_TEST_CONFIG_INFLIGHT.clear()

        self.assertTrue(module.enqueue_automatic_test_config(123, 456, telegram_username="buyer", language="en"))
        self.assertFalse(module.enqueue_automatic_test_config(123, 456, telegram_username="buyer", language="en"))
        self.assertEqual(len(fake_executor.submissions), 1)
        self.assertIn(123, module.START_TEST_CONFIG_INFLIGHT)

    def test_start_job_clears_inflight_after_completion(self):
        module, _bot, events = load_tbot_module()
        module.START_TEST_CONFIG_INFLIGHT.add(123)

        module._create_automatic_test_config_job(123, 456, "buyer", "en")

        self.assertIn("create_test_config", events)
        self.assertNotIn(123, module.START_TEST_CONFIG_INFLIGHT)


if __name__ == "__main__":
    unittest.main()
