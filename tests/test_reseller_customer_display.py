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
    / "reseller_handlers.py"
)


class DummyBot:
    def message_handler(self, *args, **kwargs):
        return lambda func: func

    def callback_query_handler(self, *args, **kwargs):
        return lambda func: func


class DummyMarkup:
    def __init__(self, *args, **kwargs):
        pass

    def add(self, *args, **kwargs):
        pass

    def row(self, *args, **kwargs):
        pass


class DummyButton:
    def __init__(self, *args, **kwargs):
        pass


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
    command_stub.ADMIN_USER_IDS = []
    command_stub.is_admin = lambda user_id: False
    sys.modules["utils.command"] = command_stub

    language_stub = types.ModuleType("utils.language")
    language_stub.get_user_language = lambda user_id: "en"
    sys.modules["utils.language"] = language_stub

    translations = {
        "reseller_customer_category_active": "Active",
        "reseller_customer_status_unavailable": "Status unavailable",
    }
    translations_stub = types.ModuleType("utils.translations")
    translations_stub.get_message_text = lambda language, key: translations.get(key, key)
    translations_stub.get_button_text = lambda language, key: key
    translations_stub.BUTTON_TRANSLATIONS = {"en": {}}
    sys.modules["utils.translations"] = translations_stub

    reseller_stub = types.ModuleType("utils.reseller")
    reseller_stub.get_reseller_data = lambda user_id: None
    reseller_stub.update_reseller_status = lambda *args, **kwargs: True
    reseller_stub.add_reseller_debt = lambda *args, **kwargs: True
    reseller_stub.get_all_resellers = lambda: {}
    reseller_stub.set_reseller_debt = lambda *args, **kwargs: True
    reseller_stub.DEBT_WARNING_THRESHOLD = 20.0
    sys.modules["utils.reseller"] = reseller_stub

    edit_plans_stub = types.ModuleType("utils.edit_plans")
    edit_plans_stub.load_plans = lambda: {}
    sys.modules["utils.edit_plans"] = edit_plans_stub

    api_client_stub = types.ModuleType("utils.api_client")
    api_client_stub.APIClient = object
    api_client_stub.MultiServerAPI = object
    sys.modules["utils.api_client"] = api_client_stub

    payments_stub = types.ModuleType("utils.payments")
    payments_stub.CryptoPayment = object
    sys.modules["utils.payments"] = payments_stub

    payment_records_stub = types.ModuleType("utils.payment_records")
    payment_records_stub.add_payment_record = lambda *args, **kwargs: None
    sys.modules["utils.payment_records"] = payment_records_stub

    currency_stub = types.ModuleType("utils.currency_format")
    currency_stub.format_toman_amount = lambda value: str(value)
    currency_stub.format_usd_amount = lambda value: f"{float(value):.2f}"
    sys.modules["utils.currency_format"] = currency_stub

    purchase_plan_stub = types.ModuleType("utils.purchase_plan")
    purchase_plan_stub.build_crypto_discount_metadata = lambda amount: {
        "price": float(amount) * 0.95,
        "original_price": float(amount),
        "discount_percent": 5,
        "discount_amount": float(amount) * 0.05,
    }
    purchase_plan_stub.get_exchange_rate = lambda: 1
    purchase_plan_stub.user_data = {}
    sys.modules["utils.purchase_plan"] = purchase_plan_stub

    receipt_checker_stub = types.ModuleType("utils.receipt_checker")
    receipt_checker_stub.RECEIPT_TYPE_SETTLEMENT = "settlement"
    receipt_checker_stub.get_card_number_for_receipt_type = lambda receipt_type: None
    sys.modules["utils.receipt_checker"] = receipt_checker_stub

    username_utils_stub = types.ModuleType("utils.username_utils")
    username_utils_stub.allocate_username = lambda prefix, user_id, existing: f"{prefix}{user_id}"
    username_utils_stub.build_user_note = lambda **kwargs: kwargs.get("note_text", "")
    username_utils_stub.extract_existing_usernames = lambda users: set()
    username_utils_stub.format_username_timestamp = lambda: "260531000000"
    sys.modules["utils.username_utils"] = username_utils_stub

    sys.modules["qrcode"] = types.SimpleNamespace(make=lambda *args, **kwargs: None)


install_stubs()
spec = importlib.util.spec_from_file_location("reseller_handlers_under_test", MODULE_PATH)
reseller_handlers = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = reseller_handlers
spec.loader.exec_module(reseller_handlers)


class ResellerCustomerDisplayTests(unittest.TestCase):
    def test_customer_name_displays_above_generated_username(self):
        entry = reseller_handlers._format_reseller_customer_entry(
            1,
            {
                "username": "r1988033051a",
                "customer_name": "ali123",
                "gb": 40,
                "days": 20,
                "price": 1.12,
                "timestamp": "2026-05-30 19:05:40",
                "_status_category": "active",
            },
            "active",
            "en",
        )

        self.assertIn("1. ✅ `ali123`", entry)
        self.assertIn("   🆔 `r1988033051a`", entry)
        self.assertIn("   Active", entry)

    def test_legacy_customer_name_is_recovered_from_note(self):
        entry = reseller_handlers._format_reseller_customer_entry(
            2,
            {
                "username": "r1988033051b",
                "gb": 60,
                "days": 40,
                "price": 1.6,
                "timestamp": "2026-05-30 07:01:43",
                "_status_category": "active",
                "_user_config": {"note": "📅 2026-05-30 07:01 | 📝 sara88 | ✏️ "},
            },
            "active",
            "en",
        )

        self.assertIn("2. ✅ `sara88`", entry)
        self.assertIn("   🆔 `r1988033051b`", entry)

    def test_legacy_without_customer_name_keeps_generated_username_only(self):
        entry = reseller_handlers._format_reseller_customer_entry(
            3,
            {
                "username": "r1988033051",
                "gb": 100,
                "days": 60,
                "price": 2,
                "timestamp": "2026-02-23 15:52:12",
                "_status_category": "active",
                "_user_config": {"note": "created before notes"},
            },
            "active",
            "en",
        )

        self.assertIn("3. ✅ `r1988033051`", entry)
        self.assertNotIn("🆔", entry)


if __name__ == "__main__":
    unittest.main()
