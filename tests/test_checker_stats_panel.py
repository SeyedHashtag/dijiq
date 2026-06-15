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
    / "payment_setup.py"
)


class DummyBot:
    def __init__(self):
        self.replies = []
        self.sent_messages = []
        self.edited_messages = []
        self.callback_answers = []

    def message_handler(self, *args, **kwargs):
        return lambda func: func

    def callback_query_handler(self, *args, **kwargs):
        return lambda func: func

    def reply_to(self, message, text, **kwargs):
        self.replies.append({"message": message, "text": text, "kwargs": kwargs})
        return types.SimpleNamespace(message_id=len(self.replies))

    def send_message(self, chat_id, text, **kwargs):
        self.sent_messages.append({"chat_id": chat_id, "text": text, "kwargs": kwargs})

    def edit_message_text(self, text, **kwargs):
        self.edited_messages.append({"text": text, "kwargs": kwargs})

    def edit_message_reply_markup(self, **kwargs):
        self.edited_messages.append({"text": None, "kwargs": kwargs})

    def answer_callback_query(self, callback_id, **kwargs):
        self.callback_answers.append({"callback_id": callback_id, "kwargs": kwargs})


class DummyMarkup:
    def __init__(self, *args, **kwargs):
        self.buttons = []

    def add(self, *args, **kwargs):
        self.buttons.extend(args)
        return self

    def row(self, *args, **kwargs):
        self.buttons.extend(args)
        return self


class DummyButton:
    def __init__(self, text, **kwargs):
        self.text = text
        self.callback_data = kwargs.get("callback_data")


def load_payment_setup():
    for name in list(sys.modules):
        if name == "utils" or name.startswith("utils."):
            sys.modules.pop(name, None)

    telebot_stub = types.ModuleType("telebot")
    telebot_stub.types = types.SimpleNamespace(
        InlineKeyboardMarkup=DummyMarkup,
        InlineKeyboardButton=DummyButton,
        ReplyKeyboardMarkup=DummyMarkup,
        KeyboardButton=DummyButton,
    )
    sys.modules["telebot"] = telebot_stub
    sys.modules["dotenv"] = types.SimpleNamespace(
        load_dotenv=lambda *args, **kwargs: None,
        set_key=lambda *args, **kwargs: True,
    )

    utils_pkg = types.ModuleType("utils")
    utils_pkg.__path__ = []
    sys.modules["utils"] = utils_pkg

    command_stub = types.ModuleType("utils.command")
    command_stub.bot = DummyBot()
    command_stub.is_admin = lambda _user_id: False
    sys.modules["utils.command"] = command_stub

    common_stub = types.ModuleType("utils.common")
    common_stub.create_main_markup = lambda *args, **kwargs: DummyMarkup()
    sys.modules["utils.common"] = common_stub

    payment_records_stub = types.ModuleType("utils.payment_records")
    payment_records_stub.load_payments = lambda: {}
    sys.modules["utils.payment_records"] = payment_records_stub

    currency_stub = types.ModuleType("utils.currency_format")
    currency_stub.format_toman_amount = lambda value: f"{int(round(float(value))):,}"
    sys.modules["utils.currency_format"] = currency_stub

    receipt_checker_stub = types.ModuleType("utils.receipt_checker")
    receipt_checker_stub.RECEIPT_TYPE_REGULAR = "regular"
    receipt_checker_stub.RECEIPT_TYPE_SETTLEMENT = "settlement"
    receipt_checker_stub.add_checker_settlement = lambda *args, **kwargs: {}
    receipt_checker_stub.build_receipt_checker_stats = lambda *args, **kwargs: {}
    receipt_checker_stub.calculate_checker_share_amount_toman = lambda amount, percent=None: round(float(amount) * float(percent or 10) / 100)
    receipt_checker_stub.get_checker_settlements = lambda *args, **kwargs: []
    receipt_checker_stub.get_receipt_checker_types = lambda: ["regular", "settlement"]
    receipt_checker_stub.get_receipt_checker_user_id = lambda: 42
    receipt_checker_stub.get_receipt_checker_share_percent = lambda: 10.0
    receipt_checker_stub.get_receipt_type_label = lambda receipt_type: {
        "regular": "Regular Customer",
        "settlement": "Reseller Settlement",
    }.get(receipt_type, receipt_type)
    receipt_checker_stub.normalize_toman_amount = lambda amount: round(float(amount or 0))
    receipt_checker_stub.normalize_receipt_types = lambda value: [value]
    receipt_checker_stub.parse_receipt_checker_share_percent = lambda value: float(value)
    sys.modules["utils.receipt_checker"] = receipt_checker_stub

    spec = importlib.util.spec_from_file_location("payment_setup_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class CheckerStatsPanelTests(unittest.TestCase):
    def sample_stats(self, **overrides):
        stats = {
            "checker_id": 42,
            "checker_types": ["regular", "settlement"],
            "share_percent": 10.0,
            "types": {
                "regular": {
                    "pending": 0,
                    "approved": 4,
                    "rejected": 1,
                    "approved_total": 1200000.0,
                    "checker_owed_total": 120000.0,
                },
                "settlement": {
                    "pending": 0,
                    "approved": 2,
                    "rejected": 0,
                    "approved_total": 800000.0,
                    "checker_owed_total": 80000.0,
                },
            },
            "approved_total": 2000000.0,
            "owed_total": 200000.0,
            "paid_total": 50000.0,
            "paid_last_30_days": 30000.0,
            "unpaid_total": 150000.0,
            "open_account_total": 1500000.0,
            "approved_total_usd": 50.0,
            "owed_total_usd": 5.0,
            "paid_total_usd": 2.0,
            "legacy_estimated_count": 1,
            "latest_review": None,
        }
        stats.update(overrides)
        return stats

    def test_checker_my_stats_hides_admin_breakdown(self):
        payment_setup = load_payment_setup()
        stats = self.sample_stats()

        checker_text = payment_setup._format_checker_stats_text(
            stats,
            title="📊 My Stats",
            include_checker_details=False,
        )
        admin_text = payment_setup._format_checker_stats_text(stats)

        self.assertNotIn("Checker User ID:", checker_text)
        self.assertNotIn("Enabled Types:", checker_text)
        self.assertNotIn("Paid to Checker:", checker_text)
        self.assertNotIn("Financial Summary", checker_text)
        self.assertNotIn("Your Share:", checker_text)
        self.assertNotIn("Paid to You:", checker_text)
        self.assertNotIn("Remaining Balance:", checker_text)
        self.assertNotIn("Regular Customer\nPending:", checker_text)
        self.assertNotIn("Reseller Settlement\nPending:", checker_text)
        self.assertNotIn("Legacy USD Approved:", checker_text)
        self.assertNotIn("Legacy Estimated Receipts:", checker_text)
        self.assertIn("Paid (30 days): 30,000 T", checker_text)
        self.assertIn("Open Account: 1,500,000 T", checker_text)
        self.assertIn("Balance (10%): 150,000 T", checker_text)

        self.assertIn("Checker User ID: 42", admin_text)
        self.assertIn("Financial Summary", admin_text)
        self.assertIn("Open Account Base: 1,500,000 Tomans", admin_text)
        self.assertIn("Checker Balance (10%): 150,000 Tomans", admin_text)
        self.assertIn("Paid to Checker: 50,000 Tomans", admin_text)
        self.assertIn("Paid Last 30 Days: 30,000 Tomans", admin_text)
        self.assertIn("Approved Total: 2,000,000 Tomans", admin_text)
        self.assertIn("Receipt Types", admin_text)
        self.assertLess(admin_text.index("Financial Summary"), admin_text.index("Receipt Types"))
        self.assertIn("Legacy USD Approved: $50.00", admin_text)
        self.assertIn("Legacy Estimated Receipts: 1", admin_text)
        self.assertIn("Regular Customer\nPending: 0", admin_text)
        self.assertIn("Reseller Settlement\nPending: 0", admin_text)
        self.assertNotIn("Settlement\nApproved Total:", admin_text)

    def test_checker_settlement_process_uses_open_account_base(self):
        payment_setup = load_payment_setup()
        stats = self.sample_stats()
        captured = {}

        def add_settlement(amount, admin_user_id, stats_snapshot, checker_id=None, open_account_amount=None):
            captured.update({
                "amount": amount,
                "admin_user_id": admin_user_id,
                "checker_id": checker_id,
                "open_account_amount": open_account_amount,
            })
            return {
                "id": "checkpoint-1",
                "amount_toman": amount,
                "open_account_amount_toman": open_account_amount,
                "unpaid_before_toman": stats_snapshot["unpaid_total"],
                "unpaid_after_toman": stats_snapshot["unpaid_total"] - amount,
            }

        payment_setup.is_admin = lambda _user_id: True
        payment_setup.load_payments = lambda: {}
        payment_setup.build_receipt_checker_stats = lambda *args, **kwargs: stats
        payment_setup.add_checker_settlement = add_settlement

        message = types.SimpleNamespace(
            text="1,500,000",
            from_user=types.SimpleNamespace(id=7),
            chat=types.SimpleNamespace(id=99),
        )
        payment_setup.process_checker_settlement_amount(message)

        reply = payment_setup.bot.replies[-1]
        self.assertIn("Open Account Base: 1,500,000 Tomans", reply["text"])
        self.assertIn("Checker Payout (10%): 150,000 Tomans", reply["text"])
        self.assertEqual(reply["kwargs"]["reply_markup"].buttons[0].callback_data, "checker_settlement:confirm:1500000")

        call = types.SimpleNamespace(
            id="cb-1",
            data="checker_settlement:confirm:1500000",
            from_user=types.SimpleNamespace(id=7),
            message=types.SimpleNamespace(chat=types.SimpleNamespace(id=99), message_id=55),
        )
        payment_setup.handle_checker_settlement_callback(call)

        self.assertEqual(captured["amount"], 150000)
        self.assertEqual(captured["open_account_amount"], 1500000.0)
        self.assertEqual(captured["checker_id"], 42)
        edited_text = payment_setup.bot.edited_messages[-1]["text"]
        self.assertIn("Open Account Base: 1,500,000 Tomans", edited_text)
        self.assertIn("Checker Payout: 150,000 Tomans", edited_text)
        self.assertIn("Unpaid After: 0 Tomans", edited_text)

    def test_checker_settlement_rejects_open_account_base_over_available_total(self):
        payment_setup = load_payment_setup()
        payment_setup.load_payments = lambda: {}
        payment_setup.build_receipt_checker_stats = lambda *args, **kwargs: self.sample_stats()

        message = types.SimpleNamespace(
            text="1,500,001",
            from_user=types.SimpleNamespace(id=7),
            chat=types.SimpleNamespace(id=99),
        )
        payment_setup.process_checker_settlement_amount(message)

        self.assertIn("Open Account base must be greater than 0", payment_setup.bot.replies[-1]["text"])
        self.assertIn("1,500,000 Tomans", payment_setup.bot.replies[-1]["text"])

    def test_checker_settlement_rejects_base_when_calculated_payout_rounds_to_zero(self):
        payment_setup = load_payment_setup()
        stats = self.sample_stats(share_percent=0.01, unpaid_total=100.0, open_account_total=1000.0)
        payment_setup.load_payments = lambda: {}
        payment_setup.build_receipt_checker_stats = lambda *args, **kwargs: stats

        message = types.SimpleNamespace(
            text="1",
            from_user=types.SimpleNamespace(id=7),
            chat=types.SimpleNamespace(id=99),
        )
        payment_setup.process_checker_settlement_amount(message)

        self.assertIn("Calculated checker payout must be greater than 0", payment_setup.bot.replies[-1]["text"])

    def test_checker_settlement_history_shows_new_base_and_legacy_payout_records(self):
        payment_setup = load_payment_setup()
        payment_setup.is_admin = lambda _user_id: True
        payment_setup.load_payments = lambda: {}
        payment_setup.build_receipt_checker_stats = lambda *args, **kwargs: self.sample_stats()
        payment_setup.get_checker_settlements = lambda _checker_id: [
            {
                "id": "legacy",
                "amount_toman": 50000,
                "admin_user_id": 1,
                "created_at": "2026-06-01 10:00:00",
                "unpaid_after_toman": 100000,
            },
            {
                "id": "new",
                "open_account_amount_toman": 1000000,
                "amount_toman": 100000,
                "admin_user_id": 2,
                "created_at": "2026-06-02 10:00:00",
                "unpaid_after_toman": 0,
            },
        ]

        call = types.SimpleNamespace(
            id="cb-2",
            data="checker_settlement:history",
            from_user=types.SimpleNamespace(id=7),
            message=types.SimpleNamespace(chat=types.SimpleNamespace(id=99), message_id=55),
        )
        payment_setup.handle_checker_settlement_callback(call)

        history_text = payment_setup.bot.sent_messages[-1]["text"]
        self.assertIn("ID: new", history_text)
        self.assertIn("Open Account Base: 1,000,000 Tomans", history_text)
        self.assertIn("Checker Payout: 100,000 Tomans", history_text)
        self.assertIn("ID: legacy", history_text)
        self.assertIn("Checker Payout: 50,000 Tomans", history_text)


if __name__ == "__main__":
    unittest.main()
