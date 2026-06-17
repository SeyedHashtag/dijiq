import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REFERRAL_PATH = ROOT / "core" / "scripts" / "telegrambot" / "utils" / "referral.py"
REFERRAL_HANDLERS_PATH = ROOT / "core" / "scripts" / "telegrambot" / "utils" / "referral_handlers.py"


def load_referral_module():
    spec = importlib.util.spec_from_file_location("referral_admin_under_test", REFERRAL_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


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
        self.messages = []
        self.documents = []
        self.get_me_calls = 0

    def message_handler(self, *args, **kwargs):
        return lambda func: func

    def callback_query_handler(self, *args, **kwargs):
        return lambda func: func

    def reply_to(self, *args, **kwargs):
        self.replies.append((args, kwargs))

    def edit_message_text(self, *args, **kwargs):
        self.edits.append((args, kwargs))

    def answer_callback_query(self, *args, **kwargs):
        self.answers.append((args, kwargs))

    def send_message(self, *args, **kwargs):
        self.messages.append((args, kwargs))

    def send_document(self, *args, **kwargs):
        self.documents.append((args, kwargs))

    def get_me(self):
        self.get_me_calls += 1
        return types.SimpleNamespace(username="DijiqBot")


class HoldingExecutor:
    def __init__(self):
        self.jobs = []

    def submit(self, fn, *args, **kwargs):
        self.jobs.append((fn, args, kwargs))
        return types.SimpleNamespace(done=lambda: False)

    def run_next(self):
        fn, args, kwargs = self.jobs.pop(0)
        return fn(*args, **kwargs)


def load_referral_handlers_module():
    for name in list(sys.modules):
        if name == "utils" or name.startswith("utils."):
            sys.modules.pop(name, None)

    bot = DummyBot()
    telebot_stub = types.ModuleType("telebot")
    telebot_stub.types = types.SimpleNamespace(
        InlineKeyboardMarkup=DummyMarkup,
        InlineKeyboardButton=DummyButton,
    )
    sys.modules["telebot"] = telebot_stub

    utils_pkg = types.ModuleType("utils")
    utils_pkg.__path__ = []
    sys.modules["utils"] = utils_pkg

    command_stub = types.ModuleType("utils.command")
    command_stub.bot = bot
    command_stub.ADMIN_USER_IDS = [1]
    command_stub.is_admin = lambda user_id: user_id == 1
    sys.modules["utils.command"] = command_stub

    referral_stub = types.ModuleType("utils.referral")
    referral_stub.get_or_create_referral_code = lambda user_id: "CODE"
    referral_stub.get_referral_stats = lambda user_id: {"count": 0, "total_earnings": 0.0, "available_balance": 0.0}
    referral_stub.get_wallet_address = lambda user_id: None
    referral_stub.set_wallet_address = lambda user_id, address: True
    referral_stub.process_withdrawal_request = lambda user_id: (False, "not used")
    referral_stub.build_withdrawal_audit_payload = lambda *args, **kwargs: {}
    referral_stub.get_eligible_referral_users = lambda: []
    referral_stub.mark_referral_payout_paid = lambda user_id, admin_id: (False, "not used")
    referral_stub.mark_withdrawal_request_paid = lambda request_id, admin_id: (False, "not used")
    sys.modules["utils.referral"] = referral_stub

    translations_stub = types.ModuleType("utils.translations")
    translations_stub.BUTTON_TRANSLATIONS = {"en": {"referral": "💰 Earn Crypto"}}
    translations_stub.get_message_text = lambda language, key: key
    translations_stub.get_button_text = lambda language, key: translations_stub.BUTTON_TRANSLATIONS.get(language, {}).get(key, key)
    sys.modules["utils.translations"] = translations_stub

    language_stub = types.ModuleType("utils.language")
    language_stub.get_user_language = lambda user_id: "en"
    sys.modules["utils.language"] = language_stub

    telegram_safe_stub = types.ModuleType("utils.telegram_safe")
    telegram_safe_stub.safe_answer_callback_query = lambda bot_obj, *args, **kwargs: bot_obj.answer_callback_query(*args, **kwargs)
    telegram_safe_stub.safe_edit_message_text = lambda bot_obj, *args, **kwargs: bot_obj.edit_message_text(*args, **kwargs)
    telegram_safe_stub.safe_send_message = lambda bot_obj, *args, **kwargs: bot_obj.send_message(*args, **kwargs)
    sys.modules["utils.telegram_safe"] = telegram_safe_stub

    spec = importlib.util.spec_from_file_location("referral_handlers_admin_under_test", REFERRAL_HANDLERS_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module, bot


class ReferralAdminHelperTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.referrals_file = Path(self.tmpdir.name) / "referrals.json"
        self.referral = load_referral_module()
        self.referral.REFERRALS_FILE = str(self.referrals_file)

    def write_referrals(self, data):
        self.referrals_file.write_text(json.dumps(data), encoding="utf-8")

    def read_referrals(self):
        return json.loads(self.referrals_file.read_text(encoding="utf-8"))

    def test_eligible_users_include_exact_threshold_and_sort_by_balance(self):
        self.write_referrals({
            "stats": {
                "10": {"count": 1, "total_earnings": 2.0, "available_balance": 2.0},
                "20": {"count": 3, "total_earnings": 7.5, "available_balance": 7.5},
                "30": {"count": 2, "total_earnings": 1.99, "available_balance": 1.99},
            },
            "wallets": {"10": "ltc10", "20": "ltc20"},
        })

        eligible = self.referral.get_eligible_referral_users()

        self.assertEqual([user["user_id"] for user in eligible], ["20", "10"])
        self.assertEqual(eligible[1]["available_balance"], 2.0)
        self.assertTrue(eligible[0]["has_wallet"])

    def test_load_referrals_migrates_missing_pending_withdrawals(self):
        self.write_referrals({
            "stats": {},
            "wallets": {},
        })

        data = self.referral.load_referrals()

        self.assertEqual(data["pending_withdrawals"], [])

    def test_mark_paid_clears_balance_and_appends_audit_record(self):
        self.write_referrals({
            "stats": {
                "10": {"count": 4, "total_earnings": 9.25, "available_balance": 4.5},
            },
            "wallets": {"10": "ltc10"},
        })

        success, payout = self.referral.mark_referral_payout_paid("10", 1)
        saved = self.read_referrals()

        self.assertTrue(success)
        self.assertEqual(payout["amount"], 4.5)
        self.assertEqual(saved["stats"]["10"]["available_balance"], 0)
        self.assertEqual(len(saved["payouts"]), 1)
        self.assertEqual(saved["payouts"][0]["user_id"], "10")
        self.assertEqual(saved["payouts"][0]["admin_user_id"], "1")
        self.assertEqual(saved["payouts"][0]["wallet"], "ltc10")
        self.assertEqual(saved["payouts"][0]["total_earnings_snapshot"], 9.25)
        self.assertEqual(saved["payouts"][0]["invited_count_snapshot"], 4)

    def test_mark_paid_fails_when_balance_is_below_threshold(self):
        self.write_referrals({
            "stats": {"10": {"count": 1, "total_earnings": 1.99, "available_balance": 1.99}},
            "wallets": {"10": "ltc10"},
        })

        success, reason = self.referral.mark_referral_payout_paid("10", 1)
        saved = self.read_referrals()

        self.assertFalse(success)
        self.assertEqual(reason, "Insufficient balance (Minimum $2.00)")
        self.assertEqual(saved["stats"]["10"]["available_balance"], 1.99)
        self.assertEqual(saved.get("payouts"), None)

    def test_mark_paid_fails_when_wallet_is_missing(self):
        self.write_referrals({
            "stats": {"10": {"count": 1, "total_earnings": 2.0, "available_balance": 2.0}},
            "wallets": {},
        })

        success, reason = self.referral.mark_referral_payout_paid("10", 1)
        saved = self.read_referrals()

        self.assertFalse(success)
        self.assertEqual(reason, "Wallet address not set")
        self.assertEqual(saved["stats"]["10"]["available_balance"], 2.0)

    def test_process_withdrawal_request_reserves_balance_and_persists_pending_request(self):
        self.write_referrals({
            "stats": {"10": {"count": 4, "total_earnings": 9.25, "available_balance": 4.5}},
            "wallets": {"10": "ltc10"},
        })

        success, request_data = self.referral.process_withdrawal_request("10", telegram_username="alice")
        saved = self.read_referrals()

        self.assertTrue(success)
        self.assertEqual(saved["stats"]["10"]["available_balance"], 0)
        self.assertEqual(len(saved["pending_withdrawals"]), 1)
        pending = saved["pending_withdrawals"][0]
        self.assertEqual(pending["id"], request_data["id"])
        self.assertEqual(pending["status"], "pending")
        self.assertEqual(pending["user_id"], "10")
        self.assertEqual(pending["telegram_username"], "alice")
        self.assertEqual(pending["amount"], 4.5)
        self.assertEqual(pending["wallet"], "ltc10")
        self.assertEqual(pending["available_balance_before"], 4.5)
        self.assertEqual(pending["available_balance_after"], 0)
        self.assertEqual(pending["total_earnings"], 9.25)
        self.assertEqual(pending["invited_count"], 4)

    def test_process_withdrawal_request_blocks_duplicate_pending_request(self):
        self.write_referrals({
            "stats": {"10": {"count": 1, "total_earnings": 4.0, "available_balance": 4.0}},
            "wallets": {"10": "ltc10"},
            "pending_withdrawals": [{
                "id": "req-1",
                "status": "pending",
                "user_id": "10",
                "amount": 3.0,
                "wallet": "ltc10",
            }],
        })

        success, reason = self.referral.process_withdrawal_request("10", telegram_username="alice")
        saved = self.read_referrals()

        self.assertFalse(success)
        self.assertEqual(reason, "Withdrawal request already pending")
        self.assertEqual(saved["stats"]["10"]["available_balance"], 4.0)
        self.assertEqual(len(saved["pending_withdrawals"]), 1)

    def test_mark_withdrawal_request_paid_records_audit_and_updates_status(self):
        self.write_referrals({
            "stats": {"10": {"count": 4, "total_earnings": 9.25, "available_balance": 0}},
            "wallets": {"10": "ltc10"},
            "pending_withdrawals": [{
                "id": "req-1",
                "status": "pending",
                "user_id": "10",
                "telegram_username": "alice",
                "amount": 4.5,
                "wallet": "ltc10",
                "requested_at": "2026-06-01 10:00:00",
                "available_balance_before": 4.5,
                "available_balance_after": 0,
                "total_earnings": 9.25,
                "invited_count": 4,
            }],
        })

        success, payout = self.referral.mark_withdrawal_request_paid("req-1", 1)
        saved = self.read_referrals()

        self.assertTrue(success)
        self.assertEqual(payout["withdrawal_request_id"], "req-1")
        self.assertEqual(payout["amount"], 4.5)
        self.assertEqual(payout["user_id"], "10")
        self.assertEqual(saved["pending_withdrawals"][0]["status"], "paid")
        self.assertEqual(saved["pending_withdrawals"][0]["admin_user_id"], "1")
        self.assertEqual(len(saved["payouts"]), 1)
        self.assertEqual(saved["payouts"][0]["withdrawal_request_id"], "req-1")
        self.assertEqual(saved["payouts"][0]["wallet"], "ltc10")


class ReferralAdminHandlerTests(unittest.TestCase):
    def test_referral_menu_queues_render_and_dedupes_duplicate_taps(self):
        module, bot = load_referral_handlers_module()
        executor = HoldingExecutor()
        module.REFERRAL_MENU_EXECUTOR = executor
        module.get_message_text = lambda language, key: {
            "wallet_not_set": "No wallet",
            "referral_stats": "Count {count} Link {referral_link} {wallet_info}",
        }.get(key, key)
        message = types.SimpleNamespace(
            from_user=types.SimpleNamespace(id=10),
            chat=types.SimpleNamespace(id=20),
            text="💰 Earn Crypto",
        )

        module.referral_menu(message)
        module.referral_menu(message)

        self.assertEqual(len(executor.jobs), 1)
        self.assertEqual(bot.messages, [])

        executor.run_next()

        self.assertEqual(module.REFERRAL_MENU_INFLIGHT, set())
        self.assertEqual(bot.get_me_calls, 1)
        self.assertIn("https://t.me/DijiqBot?start=CODE", bot.messages[0][0][1])

    def test_admin_menu_renders_eligible_users(self):
        module, bot = load_referral_handlers_module()
        module.get_eligible_referral_users = lambda: [{
            "user_id": "20",
            "available_balance": 7.5,
            "total_earnings": 7.5,
            "invited_count": 3,
            "wallet": "ltc20",
            "has_wallet": True,
        }]
        message = types.SimpleNamespace(from_user=types.SimpleNamespace(id=1), text="💰 Referral Payouts")

        module.admin_referral_payouts_menu(message)

        self.assertIn("Eligible Users: *1*", bot.replies[0][0][1])
        markup = bot.replies[0][1]["reply_markup"]
        self.assertEqual(markup.buttons[0].callback_data, "admin_referral:detail:20:0")

    def test_unauthorized_callback_is_blocked(self):
        module, bot = load_referral_handlers_module()
        call = types.SimpleNamespace(
            id="bad",
            data="admin_referral:list:0",
            from_user=types.SimpleNamespace(id=2),
            message=types.SimpleNamespace(chat=types.SimpleNamespace(id=10), message_id=77),
        )

        module.handle_admin_referral_payouts(call)

        self.assertEqual(bot.answers[0][0][1], "⛔ Unauthorized")
        self.assertEqual(bot.edits, [])

    def test_mark_paid_refreshes_list_after_success(self):
        module, bot = load_referral_handlers_module()
        users = [{
            "user_id": "20",
            "available_balance": 7.5,
            "total_earnings": 7.5,
            "invited_count": 3,
            "wallet": "ltc20",
            "has_wallet": True,
        }]

        def mark_paid(user_id, admin_id):
            users.clear()
            return True, {"amount": 7.5}

        module.get_eligible_referral_users = lambda: list(users)
        module.mark_referral_payout_paid = mark_paid
        call = types.SimpleNamespace(
            id="ok",
            data="admin_referral:pay:20:0",
            from_user=types.SimpleNamespace(id=1),
            message=types.SimpleNamespace(chat=types.SimpleNamespace(id=10), message_id=77),
        )

        module.handle_admin_referral_payouts(call)

        self.assertEqual(bot.answers[0][0][1], "Marked paid: $7.50")
        self.assertIn("Eligible Users: *0*", bot.edits[0][0][0])

    def test_admin_withdrawal_mark_paid_uses_request_id(self):
        module, bot = load_referral_handlers_module()

        def mark_request_paid(request_id, admin_id):
            return True, {"amount": 4.5, "withdrawal_request_id": request_id, "admin_user_id": str(admin_id)}

        module.mark_withdrawal_request_paid = mark_request_paid
        call = types.SimpleNamespace(
            id="ok",
            data="admin_pay_ref:req-1",
            from_user=types.SimpleNamespace(id=1),
            message=types.SimpleNamespace(
                chat=types.SimpleNamespace(id=10),
                message_id=77,
                text="Withdrawal request",
            ),
        )

        module.handle_admin_mark_paid(call)

        self.assertEqual(bot.answers[0][0][1], "Marked as paid.")
        self.assertIn("Paid by Admin 1", bot.edits[0][1]["text"])
        self.assertIn("Audit recorded: `$4.50`", bot.edits[0][1]["text"])

    def test_admin_withdrawal_mark_paid_blocks_non_admin(self):
        module, bot = load_referral_handlers_module()
        call = types.SimpleNamespace(
            id="bad",
            data="admin_pay_ref:req-1",
            from_user=types.SimpleNamespace(id=2),
            message=types.SimpleNamespace(
                chat=types.SimpleNamespace(id=10),
                message_id=77,
                text="Withdrawal request",
            ),
        )

        module.handle_admin_mark_paid(call)

        self.assertEqual(bot.answers[0][0][1], "⛔ Unauthorized")
        self.assertEqual(bot.edits, [])


if __name__ == "__main__":
    unittest.main()
