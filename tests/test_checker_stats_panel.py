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
    def message_handler(self, *args, **kwargs):
        return lambda func: func

    def callback_query_handler(self, *args, **kwargs):
        return lambda func: func


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
    receipt_checker_stub.get_checker_settlements = lambda *args, **kwargs: []
    receipt_checker_stub.get_receipt_checker_types = lambda: ["regular", "settlement"]
    receipt_checker_stub.get_receipt_checker_user_id = lambda: 42
    receipt_checker_stub.get_receipt_checker_share_percent = lambda: 10.0
    receipt_checker_stub.get_receipt_type_label = lambda receipt_type: {
        "regular": "Regular Customer",
        "settlement": "Reseller Settlement",
    }.get(receipt_type, receipt_type)
    receipt_checker_stub.normalize_receipt_types = lambda value: [value]
    receipt_checker_stub.parse_receipt_checker_share_percent = lambda value: float(value)
    sys.modules["utils.receipt_checker"] = receipt_checker_stub

    spec = importlib.util.spec_from_file_location("payment_setup_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class CheckerStatsPanelTests(unittest.TestCase):
    def test_checker_my_stats_hides_admin_breakdown(self):
        payment_setup = load_payment_setup()
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

        checker_text = payment_setup._format_checker_stats_text(
            stats,
            title="📊 My Stats",
            include_checker_details=False,
        )
        admin_text = payment_setup._format_checker_stats_text(stats)

        self.assertNotIn("Checker User ID:", checker_text)
        self.assertNotIn("Enabled Types:", checker_text)
        self.assertNotIn("Checker Owed:", checker_text)
        self.assertNotIn("Paid to Checker:", checker_text)
        self.assertNotIn("Settlement\nApproved Total:", checker_text)
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
        self.assertIn("Checker Owed: 200,000 Tomans", admin_text)
        self.assertIn("Paid to Checker: 50,000 Tomans", admin_text)
        self.assertIn("Legacy USD Approved: $50.00", admin_text)
        self.assertIn("Legacy Estimated Receipts: 1", admin_text)
        self.assertIn("Regular Customer\nPending: 0", admin_text)
        self.assertIn("Reseller Settlement\nPending: 0", admin_text)


if __name__ == "__main__":
    unittest.main()
