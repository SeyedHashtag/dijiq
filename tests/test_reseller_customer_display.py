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
    def __init__(self):
        self.edits = []
        self.answers = []

    def message_handler(self, *args, **kwargs):
        return lambda func: func

    def callback_query_handler(self, *args, **kwargs):
        return lambda func: func

    def edit_message_text(self, *args, **kwargs):
        self.edits.append((args, kwargs))

    def answer_callback_query(self, *args, **kwargs):
        self.answers.append((args, kwargs))


class DummyMarkup:
    def __init__(self, *args, **kwargs):
        self.buttons = []
        self.rows = []

    def add(self, *args, **kwargs):
        self.buttons.extend(args)
        self.rows.append(args)

    def row(self, *args, **kwargs):
        self.buttons.extend(args)
        self.rows.append(args)


class DummyButton:
    def __init__(self, text, **kwargs):
        self.text = text
        self.callback_data = kwargs.get("callback_data")


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
        "admin_reseller_section_button": "{status_icon} {status_label} ({count})",
        "admin_reseller_row_compact": "{status_icon} {user_id} ({username_display}) - Debt: ${debt:.2f} | Paid: ${total_paid:.2f} | Limit: ${trust_limit:.2f}",
        "admin_status_approved": "Approved",
        "admin_status_pending": "Pending",
        "admin_status_suspended": "Suspended",
        "admin_status_banned": "Banned",
        "admin_status_rejected": "Rejected",
        "admin_action_suspend": "Suspend",
        "admin_action_unban": "Unban",
        "admin_action_ban": "Ban",
        "admin_action_reject": "Reject",
        "admin_action_approve": "Approve",
        "admin_action_adjust_debt": "Adjust Debt",
        "admin_action_refresh": "Refresh",
        "admin_action_back_to_list": "Back to List",
        "admin_action_back_to_detail": "Back",
        "admin_action_cleanup_unpaid": "Remove Unpaid Users",
        "admin_debt_cancel": "Cancel",
        "admin_cleanup_preview_title": "Remove Unpaid Users",
        "admin_cleanup_no_payment": "No successful payment",
        "admin_cleanup_no_candidates": "No unpaid reseller-created users were found for this banned reseller.",
        "admin_cleanup_confirm_warning": "Confirming deletes live VPN users and removes their reseller records.",
        "admin_cleanup_confirm_delete": "Confirm Delete",
        "admin_cleanup_result_title": "Cleanup Result",
        "admin_cleanup_banned_only": "Cleanup is only available for banned resellers.",
        "admin_invalid_action": "Invalid action.",
        "cancel": "Cancel",
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
    reseller_stub.get_banned_reseller_cleanup_candidates = lambda reseller_data: []
    reseller_stub.cleanup_banned_reseller_users = lambda user_id, multi_api: (True, {})
    reseller_stub.get_reseller_unlock_amount = lambda debt: max(0.0, float(debt or 0.0))
    reseller_stub.get_reseller_total_paid = lambda data: max(
        0.0,
        float(data.get("total_paid", sum(float(config.get("price", 0.0)) for config in data.get("configs", [])) - float(data.get("debt", 0.0))) or 0.0),
    )
    reseller_stub.get_reseller_trust_limit = lambda total_paid: min(30.0, 5.0 + int(float(total_paid or 0.0) // 10.0) * 5.0)
    reseller_stub.can_reseller_add_debt = lambda data, amount: (
        float(data.get("debt", 0.0)) + float(amount or 0.0) <= reseller_stub.get_reseller_trust_limit(reseller_stub.get_reseller_total_paid(data)),
        reseller_stub.get_reseller_trust_limit(reseller_stub.get_reseller_total_paid(data)),
        max(0.0, reseller_stub.get_reseller_trust_limit(reseller_stub.get_reseller_total_paid(data)) - float(data.get("debt", 0.0))),
    )
    reseller_stub.DEBT_WARNING_THRESHOLD = 20.0
    reseller_stub.SUSPENDED_REASON_UNBAN_GRACE = "unban_grace"
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
    purchase_plan_stub.build_crypto_discount_display = lambda language, metadata: {
        "summary": "",
        "button_text": "Crypto",
    }
    purchase_plan_stub.get_crypto_discount_button_text = lambda language: "Crypto"
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

    def test_admin_reseller_row_shows_debt_and_total_paid(self):
        grouped = {
            status: []
            for status in reseller_handlers.ADMIN_RESELLER_STATUS_ORDER
        }
        grouped["approved"] = [
            (
                "1988",
                {
                    "status": "approved",
                    "telegram_username": "buyer",
                    "debt": 35.50,
                    "configs": [
                        {"price": 40.00},
                        {"price": 60.00},
                    ],
                },
            )
        ]

        markup = reseller_handlers._build_admin_reseller_list_markup(
            "en",
            grouped,
            active_status="approved",
            active_page=0,
        )

        row_texts = [button.text for button in markup.buttons]
        self.assertIn(
            "✅ 1988 (@buyer) - Debt: $35.50 | Paid: $64.50 | Limit: $30.00",
            row_texts,
        )

    def test_approved_reseller_detail_has_suspend_and_ban_actions(self):
        markup = reseller_handlers._build_admin_reseller_detail_markup(
            "en",
            "1988",
            {"status": "approved", "telegram_username": "buyer", "debt": 0.0, "configs": []},
            "approved",
            0,
        )

        actions = {button.callback_data: button.text for button in markup.buttons}
        self.assertEqual(actions["admin_reseller_ui:action:1988:suspend"], "Suspend")
        self.assertIn("admin_reseller_ui:action:1988:ban", actions)

    def test_banned_reseller_detail_has_cleanup_action(self):
        markup = reseller_handlers._build_admin_reseller_detail_markup(
            "en",
            "1988",
            {"status": "banned", "telegram_username": "buyer", "debt": 7.0, "configs": []},
            "banned",
            0,
        )

        actions = {button.callback_data: button.text for button in markup.buttons}
        self.assertEqual(actions["admin_reseller_ui:cleanup:1988:banned:0"], "Remove Unpaid Users")

    def test_non_banned_reseller_detail_does_not_have_cleanup_action(self):
        for status in ("approved", "suspended", "rejected", "pending"):
            markup = reseller_handlers._build_admin_reseller_detail_markup(
                "en",
                "1988",
                {"status": status, "telegram_username": "buyer", "debt": 7.0, "configs": []},
                status,
                0,
            )

            self.assertFalse(
                any(
                    str(button.callback_data).startswith("admin_reseller_ui:cleanup:")
                    for button in markup.buttons
                )
            )

    def test_cleanup_preview_text_lists_users_timestamps_prices_and_totals(self):
        candidates = [
            {
                "username": "r1988a",
                "customer_name": "ali",
                "timestamp": "2026-06-02 10:00:00",
                "price": 5.5,
            },
            {
                "username": "r1988b",
                "timestamp": "2026-06-03 10:00:00",
                "price": 2.25,
            },
        ]

        text = reseller_handlers._build_admin_cleanup_preview_text(
            "en",
            "1988",
            {"last_payment_at": "2026-06-01 09:00:00"},
            candidates,
        )

        self.assertIn("Last successful payment: `2026-06-01 09:00:00`", text)
        self.assertIn("Matched users: *2*", text)
        self.assertIn("Total matched value: *$7.75*", text)
        self.assertIn("`r1988a` (ali) | 2026-06-02 10:00:00 | $5.50", text)
        self.assertIn("`r1988b` | 2026-06-03 10:00:00 | $2.25", text)

    def test_cleanup_result_text_lists_deleted_missing_and_failed_users(self):
        text = reseller_handlers._build_admin_cleanup_result_text(
            "en",
            "1988",
            {
                "deleted": [{"username": "deleted", "timestamp": "2026-06-02", "price": 5}],
                "already_missing": [{"username": "missing", "timestamp": "2026-06-03", "price": 3}],
                "failed": [{"username": "failed", "timestamp": "2026-06-04", "price": 2}],
                "removed_count": 2,
                "removed_value": 8,
                "remaining_configs": 1,
                "remaining_debt": 2,
            },
        )

        self.assertIn("Deleted from VPN", text)
        self.assertIn("`deleted`", text)
        self.assertIn("Already missing, record removed", text)
        self.assertIn("`missing`", text)
        self.assertIn("Failed, record kept", text)
        self.assertIn("`failed`", text)
        self.assertIn("Remaining debt: *$2.00*", text)

    def test_cleanup_confirm_calls_cleanup_helper_at_confirmation_time(self):
        calls = []
        original_is_admin = reseller_handlers.is_admin
        original_multi_api = reseller_handlers.MultiServerAPI
        original_cleanup = reseller_handlers.cleanup_banned_reseller_users
        try:
            reseller_handlers.is_admin = lambda user_id: True
            reseller_handlers.MultiServerAPI = lambda: object()

            def cleanup(user_id, multi_api):
                calls.append((user_id, multi_api))
                return True, {
                    "deleted": [],
                    "already_missing": [{"username": "fresh", "timestamp": "2026-06-05", "price": 1}],
                    "failed": [],
                    "removed_count": 1,
                    "removed_value": 1,
                    "remaining_configs": 0,
                    "remaining_debt": 0,
                }

            reseller_handlers.cleanup_banned_reseller_users = cleanup
            call = types.SimpleNamespace(
                id="call-1",
                data="admin_reseller_ui:cleanupconfirm:1988:banned:0",
                from_user=types.SimpleNamespace(id=1),
                message=types.SimpleNamespace(
                    chat=types.SimpleNamespace(id=100),
                    message_id=200,
                ),
            )

            reseller_handlers.handle_admin_reseller_ui(call)

            self.assertEqual(calls[0][0], "1988")
            edit_text = reseller_handlers.bot.edits[-1][0][0]
            self.assertIn("`fresh`", edit_text)
        finally:
            reseller_handlers.is_admin = original_is_admin
            reseller_handlers.MultiServerAPI = original_multi_api
            reseller_handlers.cleanup_banned_reseller_users = original_cleanup


if __name__ == "__main__":
    unittest.main()
