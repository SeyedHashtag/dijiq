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
    / "reseller_handlers.py"
)


class DummyBot:
    def __init__(self):
        self.edits = []
        self.answers = []
        self.sent_messages = []

    def message_handler(self, *args, **kwargs):
        return lambda func: func

    def callback_query_handler(self, *args, **kwargs):
        return lambda func: func

    def edit_message_text(self, *args, **kwargs):
        self.edits.append((args, kwargs))

    def answer_callback_query(self, *args, **kwargs):
        self.answers.append((args, kwargs))

    def send_message(self, *args, **kwargs):
        self.sent_messages.append((args, kwargs))


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


class HoldingExecutor:
    def __init__(self):
        self.jobs = []

    def submit(self, fn, *args, **kwargs):
        self.jobs.append((fn, args, kwargs))
        return types.SimpleNamespace(done=lambda: False)

    def run_next(self):
        fn, args, kwargs = self.jobs.pop(0)
        return fn(*args, **kwargs)


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
        "reseller_customer_category_low_days": "Low Days",
        "reseller_customer_category_low_gb": "Low GB",
        "reseller_customer_category_expired": "Expired",
        "reseller_customer_category_deleted": "Deleted",
        "reseller_customer_status_unavailable": "Status unavailable",
        "reseller_customers_overview": "Customers {total}\n{categories}",
        "reseller_customer_category_count": "{icon} {label}: {count}",
        "reseller_customers_category_header": "{category} Customers\n{entries}",
        "reseller_customers_empty_category": "No customers in {category}",
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
        "admin_reseller_details_extended": (
            "User ID: `{user_id}`\nStatus: {status}\nDebt: ${debt}\n"
            "Debt State: {debt_state}\nTrust Limit: ${trust_limit}\nConfigs: {configs_count}\n"
            "Total Turnover: ${total_turnover}\nTotal Paid: ${total_paid}\n"
            "Average Config Value: ${average_config_value}\nLast Config: {last_config_at}\n"
            "Joined: {created_at}\nLast Payment: {last_payment_at}\nOldest Unpaid: {debt_since}"
        ),
        "admin_username_unknown": "N/A",
        "admin_debt_cancel": "Cancel",
        "admin_reseller_action_confirm": "Confirm {action} for {user_id}",
        "admin_reseller_action_confirm_notify": "Apply + Notify User",
        "admin_reseller_action_confirm_silent": "Apply Silently",
        "reseller_suspended_notification": "Suspended notice",
        "reseller_banned_notification": "Banned notice",
        "reseller_unbanned_notification": "Unbanned notice",
        "reseller_approved_notification": "Approved notice",
        "reseller_rejected_notification": "Rejected notice",
        "debt_state_active": "Active",
        "admin_cleanup_preview_title": "Remove Unpaid Users",
        "admin_cleanup_no_payment": "No successful payment",
        "admin_cleanup_no_candidates": "No unpaid reseller-created users were found for this banned reseller.",
        "admin_cleanup_confirm_warning": "Confirming deletes live VPN users and removes their reseller records.",
        "admin_cleanup_confirm_delete": "Confirm Delete",
        "admin_cleanup_result_title": "Cleanup Result",
        "admin_cleanup_banned_only": "Cleanup is only available for banned resellers.",
        "admin_invalid_action": "Invalid action.",
        "reseller_requires_active_paid_config": "Requires active paid config",
        "reseller_request_sent": "Reseller request sent",
        "reseller_request_notification": "Request from {user_id} @{username}",
        "reseller_status_pending": "Pending",
        "reseller_access_banned": "Banned",
        "reseller_requires_telegram_username": "Username required",
        "not_authorized": "Not authorized",
        "cancel": "Cancel",
        "renewal_unavailable": "Renewal is not available for this config: {reason}.",
        "renewal_ineligible_no_record": "no matching paid record was found",
        "reseller_suspended_due_debt": "Account suspended due to debt (${debt:.2f}). Pay ${unlock_amount:.2f} to unlock config generation.",
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
    reseller_stub.reseller_config_is_recorded = lambda *args, **kwargs: True
    reseller_stub.get_all_resellers = lambda: {}
    reseller_stub.set_reseller_debt = lambda *args, **kwargs: True
    reseller_stub.get_banned_reseller_cleanup_candidates = lambda reseller_data: []
    reseller_stub.cleanup_banned_reseller_users = lambda user_id, multi_api: (True, {})
    reseller_stub.get_reseller_unlock_amount = lambda debt: max(0.0, float(debt or 0.0))
    reseller_stub.get_reseller_total_paid = lambda data: max(
        0.0,
        float(data.get(
            "total_paid",
            sum(
                float(config.get("price", 0.0))
                for config in data.get("configs", [])
                if not config.get("removed_from_vpn")
            ) - float(data.get("debt", 0.0)),
        ) or 0.0),
    )
    reseller_stub.get_reseller_trust_limit = lambda total_paid: min(30.0, 5.0 + int(float(total_paid or 0.0) // 10.0) * 5.0)
    reseller_stub.can_reseller_add_debt = lambda data, amount: (
        float(data.get("debt", 0.0)) + float(amount or 0.0) <= reseller_stub.get_reseller_trust_limit(reseller_stub.get_reseller_total_paid(data)),
        reseller_stub.get_reseller_trust_limit(reseller_stub.get_reseller_total_paid(data)),
        max(0.0, reseller_stub.get_reseller_trust_limit(reseller_stub.get_reseller_total_paid(data)) - float(data.get("debt", 0.0))),
    )
    reseller_stub.apply_reseller_payment = lambda user_id, amount: (True, 0.0)

    def validate_reseller_manual_payment_amount(amount, current_debt):
        try:
            amount_value = round(float(amount), 2)
        except (TypeError, ValueError):
            return False, 0.0, "invalid"
        debt_value = round(max(0.0, float(current_debt or 0.0)), 2)
        if amount_value <= 0:
            return False, amount_value, "invalid"
        if amount_value > debt_value:
            return False, amount_value, "over_debt"
        return True, amount_value, None

    reseller_stub.validate_reseller_manual_payment_amount = validate_reseller_manual_payment_amount
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

    telegram_safe_stub = types.ModuleType("utils.telegram_safe")
    telegram_safe_stub.safe_answer_callback_query = lambda bot, *args, **kwargs: bot.answer_callback_query(*args, **kwargs)
    telegram_safe_stub.safe_delete_message = lambda bot, *args, **kwargs: None
    telegram_safe_stub.safe_edit_message_text = lambda bot, *args, **kwargs: bot.edit_message_text(*args, **kwargs)
    telegram_safe_stub.safe_send_message = lambda bot, *args, **kwargs: bot.send_message(*args, **kwargs)
    telegram_safe_stub.safe_send_photo = lambda bot, *args, **kwargs: None
    telegram_safe_stub.safe_reply_to = lambda bot, *args, **kwargs: None
    sys.modules["utils.telegram_safe"] = telegram_safe_stub

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
    def setUp(self):
        reseller_handlers.bot.edits.clear()
        reseller_handlers.bot.answers.clear()
        reseller_handlers.bot.sent_messages.clear()
        reseller_handlers.RESELLER_CUSTOMERS_INFLIGHT.clear()
        reseller_handlers.RESELLER_CUSTOMER_CONFIG_INFLIGHT.clear()
        reseller_handlers.RESELLER_REQUEST_INFLIGHT.clear()

    def install_renewal_stub(self, offer, unavailable="Renewal is not available"):
        original = sys.modules.get("utils.renewal")
        renewal_stub = types.ModuleType("utils.renewal")
        renewal_stub.find_reseller_renewal_offer = lambda *args, **kwargs: offer
        renewal_stub.format_renewal_unavailable = lambda *args, **kwargs: unavailable
        sys.modules["utils.renewal"] = renewal_stub
        return original

    def restore_renewal_stub(self, original):
        if original is None:
            sys.modules.pop("utils.renewal", None)
        else:
            sys.modules["utils.renewal"] = original

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

    def test_removed_cleanup_customer_entry_shows_reason(self):
        entry = reseller_handlers._format_reseller_customer_entry(
            4,
            {
                "username": "r1988033051c",
                "customer_name": "reza",
                "gb": 50,
                "days": 30,
                "price": 3,
                "timestamp": "2026-06-01 12:00:00",
                "removed_from_vpn": True,
                "removal_reason": "banned_reseller_cleanup",
                "removal_note": "Removed during banned reseller unpaid user cleanup",
                "removed_at": "2026-06-02 13:00:00",
                "_status_category": "deleted",
            },
            "deleted",
            "en",
        )

        self.assertIn("4. 🗑 `reza`", entry)
        self.assertIn("   Deleted", entry)
        self.assertIn("Removed during banned reseller unpaid user cleanup (2026-06-02 13:00:00)", entry)

    def test_reseller_live_users_uses_cached_snapshot_ttl_by_default(self):
        original_multi_api = reseller_handlers.MultiServerAPI
        original_ttl = os.environ.get("RESELLER_CUSTOMERS_CACHE_TTL_SECONDS")

        class FakeMultiServerAPI:
            calls = []

            def get_user_snapshot_entries(self, **kwargs):
                self.__class__.calls.append(kwargs)
                return [
                    {
                        "server": {"id": "s1"},
                        "client": types.SimpleNamespace(server_id="fallback"),
                        "users": {"r1988a": {"expiration_days": 20}},
                    },
                    {
                        "server": {"id": "s2"},
                        "client": types.SimpleNamespace(server_id="s2"),
                        "users": None,
                    },
                ]

        try:
            os.environ.pop("RESELLER_CUSTOMERS_CACHE_TTL_SECONDS", None)
            reseller_handlers.MultiServerAPI = FakeMultiServerAPI

            live_users, unavailable_server_ids = reseller_handlers._load_reseller_live_users()

            self.assertEqual(live_users, {"r1988a": {"expiration_days": 20}})
            self.assertEqual(unavailable_server_ids, {"s2"})
            self.assertEqual(FakeMultiServerAPI.calls[0]["include_disabled"], True)
            self.assertEqual(FakeMultiServerAPI.calls[0]["force_refresh"], False)
            self.assertEqual(FakeMultiServerAPI.calls[0]["cache_ttl_seconds"], 60)
        finally:
            reseller_handlers.MultiServerAPI = original_multi_api
            if original_ttl is None:
                os.environ.pop("RESELLER_CUSTOMERS_CACHE_TTL_SECONDS", None)
            else:
                os.environ["RESELLER_CUSTOMERS_CACHE_TTL_SECONDS"] = original_ttl

    def test_reseller_live_users_refresh_bypasses_cache(self):
        original_multi_api = reseller_handlers.MultiServerAPI
        original_ttl = os.environ.get("RESELLER_CUSTOMERS_CACHE_TTL_SECONDS")

        class FakeMultiServerAPI:
            calls = []

            def get_user_snapshot_entries(self, **kwargs):
                self.__class__.calls.append(kwargs)
                return []

        try:
            os.environ["RESELLER_CUSTOMERS_CACHE_TTL_SECONDS"] = "12"
            reseller_handlers.MultiServerAPI = FakeMultiServerAPI

            reseller_handlers._load_reseller_live_users(force_refresh=True)

            self.assertEqual(FakeMultiServerAPI.calls[0]["force_refresh"], True)
            self.assertEqual(FakeMultiServerAPI.calls[0]["cache_ttl_seconds"], 12)
        finally:
            reseller_handlers.MultiServerAPI = original_multi_api
            if original_ttl is None:
                os.environ.pop("RESELLER_CUSTOMERS_CACHE_TTL_SECONDS", None)
            else:
                os.environ["RESELLER_CUSTOMERS_CACHE_TTL_SECONDS"] = original_ttl

    def test_reseller_request_eligibility_uses_fresh_cached_snapshot(self):
        original_multi_api = reseller_handlers.MultiServerAPI
        original_ttl = os.environ.get("RESELLER_CUSTOMERS_CACHE_TTL_SECONDS")

        class FakeMultiServerAPI:
            calls = []

            def get_cached_user_snapshot_entries(self, **kwargs):
                self.__class__.calls.append(("cached", kwargs))
                return [
                    {
                        "client": types.SimpleNamespace(server_id="s1"),
                        "users": {"s1988a": {"expiration_days": 10, "blocked": False}},
                    }
                ]

            def get_user_snapshot_entries(self, **_kwargs):
                raise AssertionError("fresh cache should avoid live snapshot")

            def iter_all_users(self):
                raise AssertionError("fresh cache should avoid live iteration")

        try:
            os.environ.pop("RESELLER_CUSTOMERS_CACHE_TTL_SECONDS", None)
            reseller_handlers.MultiServerAPI = FakeMultiServerAPI

            self.assertTrue(reseller_handlers._has_active_purchased_config(1988))
            self.assertEqual(FakeMultiServerAPI.calls[0][0], "cached")
            self.assertEqual(FakeMultiServerAPI.calls[0][1]["include_disabled"], False)
            self.assertEqual(FakeMultiServerAPI.calls[0][1]["allow_expired"], False)
            self.assertEqual(FakeMultiServerAPI.calls[0][1]["cache_ttl_seconds"], 60)
        finally:
            reseller_handlers.MultiServerAPI = original_multi_api
            if original_ttl is None:
                os.environ.pop("RESELLER_CUSTOMERS_CACHE_TTL_SECONDS", None)
            else:
                os.environ["RESELLER_CUSTOMERS_CACHE_TTL_SECONDS"] = original_ttl

    def test_reseller_request_queues_active_config_check_and_dedupes(self):
        original_executor = reseller_handlers.RESELLER_REQUEST_EXECUTOR
        original_get_reseller_data = reseller_handlers.get_reseller_data
        original_has_active = reseller_handlers._has_active_purchased_config
        original_update_status = reseller_handlers.update_reseller_status
        original_admin_ids = reseller_handlers.ADMIN_USER_IDS
        try:
            executor = HoldingExecutor()
            active_checks = []
            updates = []
            reseller_handlers.RESELLER_REQUEST_EXECUTOR = executor
            reseller_handlers.ADMIN_USER_IDS = [99]
            reseller_handlers.get_reseller_data = lambda _user_id: None
            reseller_handlers._has_active_purchased_config = lambda user_id: active_checks.append(user_id) or True
            reseller_handlers.update_reseller_status = (
                lambda user_id, status, **kwargs:
                updates.append((user_id, status, kwargs)) or True
            )
            call = types.SimpleNamespace(
                id="call-1",
                data="reseller:request",
                from_user=types.SimpleNamespace(id=1988, username="buyer"),
                message=types.SimpleNamespace(chat=types.SimpleNamespace(id=100), message_id=200),
            )

            reseller_handlers.handle_reseller_request(call)
            reseller_handlers.handle_reseller_request(call)

            self.assertEqual(len(executor.jobs), 1)
            self.assertEqual(active_checks, [])
            self.assertEqual(updates, [])

            executor.run_next()

            self.assertEqual(active_checks, [1988])
            self.assertEqual(updates, [(1988, "pending", {"telegram_username": "buyer"})])
            self.assertEqual(reseller_handlers.bot.edits[-1][0][0], "Reseller request sent")
            self.assertEqual(reseller_handlers.bot.sent_messages[-1][0][0], 99)
            self.assertIn("Request from 1988 @buyer", reseller_handlers.bot.sent_messages[-1][0][1])
            self.assertEqual(reseller_handlers.RESELLER_REQUEST_INFLIGHT, set())
        finally:
            reseller_handlers.RESELLER_REQUEST_EXECUTOR = original_executor
            reseller_handlers.get_reseller_data = original_get_reseller_data
            reseller_handlers._has_active_purchased_config = original_has_active
            reseller_handlers.update_reseller_status = original_update_status
            reseller_handlers.ADMIN_USER_IDS = original_admin_ids

    def test_reseller_my_customers_queues_live_status_render(self):
        original_multi_api = reseller_handlers.MultiServerAPI
        original_get_reseller_data = reseller_handlers.get_reseller_data
        original_executor = reseller_handlers.RESELLER_CUSTOMERS_EXECUTOR

        class FakeMultiServerAPI:
            calls = []

            def get_user_snapshot_entries(self, **kwargs):
                self.__class__.calls.append(kwargs)
                return [
                    {
                        "server": {"id": "s1"},
                        "client": types.SimpleNamespace(server_id="s1"),
                        "users": {"r1988a": {"expiration_days": 20}},
                    }
                ]

        try:
            executor = HoldingExecutor()
            reseller_handlers.RESELLER_CUSTOMERS_EXECUTOR = executor
            reseller_handlers.MultiServerAPI = FakeMultiServerAPI
            reseller_handlers.get_reseller_data = lambda _user_id: {
                "status": "approved",
                "configs": [
                    {
                        "username": "r1988a",
                        "customer_name": "ali",
                        "gb": 20,
                        "days": 30,
                        "price": 1.0,
                        "timestamp": "2026-06-01 12:00:00",
                    }
                ],
            }
            call = types.SimpleNamespace(
                id="call-1",
                data="reseller:my_customers:active:0",
                from_user=types.SimpleNamespace(id=1988),
                message=types.SimpleNamespace(
                    photo=None,
                    document=None,
                    sticker=None,
                    chat=types.SimpleNamespace(id=100),
                    message_id=200,
                ),
            )

            reseller_handlers.handle_reseller_my_customers(call)

            self.assertEqual(len(executor.jobs), 1)
            self.assertEqual(FakeMultiServerAPI.calls, [])

            reseller_handlers.handle_reseller_my_customers(call)
            self.assertEqual(len(executor.jobs), 1)

            executor.run_next()

            self.assertEqual(FakeMultiServerAPI.calls[0]["include_disabled"], True)
            self.assertEqual(FakeMultiServerAPI.calls[0]["cache_ttl_seconds"], 60)
            self.assertIn("ali", reseller_handlers.bot.edits[-1][0][0])
        finally:
            reseller_handlers.MultiServerAPI = original_multi_api
            reseller_handlers.get_reseller_data = original_get_reseller_data
            reseller_handlers.RESELLER_CUSTOMERS_EXECUTOR = original_executor

    def test_reseller_customer_config_queues_live_lookup(self):
        original_multi_api = reseller_handlers.MultiServerAPI
        original_get_reseller_data = reseller_handlers.get_reseller_data
        original_executor = reseller_handlers.RESELLER_CUSTOMER_CONFIG_EXECUTOR

        class FakeClient:
            server_id = "s1"

            def get_user_uri(self, username):
                return {"normal_sub": f"https://sub.example/{username}", "ipv4": ""}

        class FakeMultiServerAPI:
            calls = []

            def find_user(self, username, preferred_server_id=None):
                self.__class__.calls.append((username, preferred_server_id))
                return FakeClient(), {
                    "blocked": False,
                    "upload_bytes": 0,
                    "download_bytes": 0,
                    "max_download_bytes": 20 * 1024 ** 3,
                    "expiration_days": 20,
                    "account_creation_date": "2026-06-01",
                    "status": "active",
                }

        try:
            executor = HoldingExecutor()
            reseller_handlers.RESELLER_CUSTOMER_CONFIG_EXECUTOR = executor
            reseller_handlers.MultiServerAPI = FakeMultiServerAPI
            reseller_handlers.get_reseller_data = lambda _user_id: {
                "status": "approved",
                "configs": [{"username": "r1988a", "server_id": "s1"}],
            }
            call = types.SimpleNamespace(
                id="call-1",
                data="reseller:cfg:r1988a:active:0",
                from_user=types.SimpleNamespace(id=1988),
                message=types.SimpleNamespace(chat=types.SimpleNamespace(id=100), message_id=200),
            )

            reseller_handlers.handle_reseller_customer_config(call)
            reseller_handlers.handle_reseller_customer_config(call)

            self.assertEqual(len(executor.jobs), 1)
            self.assertEqual(FakeMultiServerAPI.calls, [])

            executor.run_next()

            self.assertEqual(FakeMultiServerAPI.calls, [("r1988a", "s1")])
            self.assertEqual(reseller_handlers.RESELLER_CUSTOMER_CONFIG_INFLIGHT, set())
        finally:
            reseller_handlers.MultiServerAPI = original_multi_api
            reseller_handlers.get_reseller_data = original_get_reseller_data
            reseller_handlers.RESELLER_CUSTOMER_CONFIG_EXECUTOR = original_executor

    def test_reseller_customer_config_rejects_unrecorded_username_without_live_lookup(self):
        original_multi_api = reseller_handlers.MultiServerAPI

        class FakeMultiServerAPI:
            calls = []

            def find_user(self, username, preferred_server_id=None):
                self.__class__.calls.append((username, preferred_server_id))
                return object(), {"blocked": False}

        try:
            reseller_handlers.MultiServerAPI = FakeMultiServerAPI
            call = types.SimpleNamespace(
                id="call-1",
                data="reseller:cfg:r9999a:active:0",
                from_user=types.SimpleNamespace(id=1988),
                message=types.SimpleNamespace(chat=types.SimpleNamespace(id=100), message_id=200),
            )
            reseller_data = {
                "status": "approved",
                "configs": [{"username": "r1988a", "server_id": "s1"}],
            }

            reseller_handlers._render_reseller_customer_config_job(
                call,
                1988,
                "en",
                reseller_data,
                "r9999a",
                "active",
                0,
            )

            self.assertEqual(FakeMultiServerAPI.calls, [])
            self.assertEqual(reseller_handlers.bot.edits[-1][0][0], "Not authorized")
        finally:
            reseller_handlers.MultiServerAPI = original_multi_api

    def test_expired_reseller_customer_config_shows_renew_button_when_eligible(self):
        original_multi_api = reseller_handlers.MultiServerAPI
        original_renewal = self.install_renewal_stub({
            "eligible": True,
            "token": "renew-token",
            "source": "reseller_customer",
        })

        class FakeClient:
            server_id = "s1"

        class FakeMultiServerAPI:
            def find_user(self, username, preferred_server_id=None):
                return FakeClient(), {
                    "blocked": True,
                    "upload_bytes": 2 * 1024 ** 3,
                    "download_bytes": 0,
                    "max_download_bytes": 1 * 1024 ** 3,
                    "expiration_days": 7,
                    "account_creation_date": "2026-06-24",
                    "status": "offline",
                }

        try:
            reseller_handlers.MultiServerAPI = FakeMultiServerAPI
            call = types.SimpleNamespace(
                id="call-1",
                data="reseller:cfg:r1988a:expired:0",
                from_user=types.SimpleNamespace(id=1988),
                message=types.SimpleNamespace(chat=types.SimpleNamespace(id=100), message_id=200),
            )
            reseller_data = {
                "status": "approved",
                "configs": [{
                    "username": "r1988a",
                    "server_id": "s1",
                    "gb": "1",
                    "days": 7,
                    "unlimited": True,
                }],
            }

            reseller_handlers._render_reseller_customer_config_job(
                call,
                1988,
                "en",
                reseller_data,
                "r1988a",
                "expired",
                0,
            )
        finally:
            reseller_handlers.MultiServerAPI = original_multi_api
            self.restore_renewal_stub(original_renewal)

        callbacks = [
            button.callback_data
            for button in reseller_handlers.bot.edits[-1][1]["reply_markup"].buttons
        ]
        self.assertIn("reseller:renew:renew-token", callbacks)

    def test_expired_reseller_customer_config_shows_renewal_unavailable_reason(self):
        original_multi_api = reseller_handlers.MultiServerAPI
        original_renewal = self.install_renewal_stub(
            {
                "eligible": False,
                "reason": "renewal_ineligible_no_record",
                "source": "reseller_customer",
                "username": "r1988a",
                "server_id": "s1",
            },
            unavailable="Renewal is not available for this config: no matching paid record was found.",
        )

        class FakeClient:
            server_id = "s1"

        class FakeMultiServerAPI:
            def find_user(self, username, preferred_server_id=None):
                return FakeClient(), {
                    "blocked": True,
                    "upload_bytes": 2 * 1024 ** 3,
                    "download_bytes": 0,
                    "max_download_bytes": 1 * 1024 ** 3,
                    "expiration_days": 7,
                    "account_creation_date": "2026-06-24",
                    "status": "offline",
                }

        try:
            reseller_handlers.MultiServerAPI = FakeMultiServerAPI
            call = types.SimpleNamespace(
                id="call-1",
                data="reseller:cfg:r1988a:expired:0",
                from_user=types.SimpleNamespace(id=1988),
                message=types.SimpleNamespace(chat=types.SimpleNamespace(id=100), message_id=200),
            )
            reseller_handlers._render_reseller_customer_config_job(
                call,
                1988,
                "en",
                {"status": "approved", "configs": [{"username": "r1988a", "server_id": "s1"}]},
                "r1988a",
                "expired",
                0,
            )
        finally:
            reseller_handlers.MultiServerAPI = original_multi_api
            self.restore_renewal_stub(original_renewal)

        edit_args, edit_kwargs = reseller_handlers.bot.edits[-1]
        self.assertIn("Renewal is not available for this config", edit_args[0])
        callbacks = [button.callback_data for button in edit_kwargs["reply_markup"].buttons]
        self.assertNotIn("reseller:renew:renew-token", callbacks)

    def test_reseller_customer_creation_persists_unlimited_flag(self):
        original_api_client = reseller_handlers.APIClient
        original_create = reseller_handlers._create_reseller_user_with_note
        original_add_debt = reseller_handlers.add_reseller_debt
        original_is_recorded = reseller_handlers.reseller_config_is_recorded
        captured_configs = []

        class FakeClient:
            server_id = "s1"

            def get_user_uri(self, username):
                return None

        try:
            reseller_handlers.APIClient = FakeClient
            reseller_handlers._create_reseller_user_with_note = (
                lambda *args, **kwargs: ("r1988a", {"ok": True}, FakeClient())
            )
            reseller_handlers.add_reseller_debt = (
                lambda _user_id, _amount, config_data: captured_configs.append(config_data) or True
            )
            reseller_handlers.reseller_config_is_recorded = lambda *args, **kwargs: True

            reseller_handlers._run_reseller_customer_creation(
                types.SimpleNamespace(chat=types.SimpleNamespace(id=100)),
                1988,
                "en",
                {"gb": "1", "days": 7, "price": 1.6, "unlimited": True},
                "ali",
            )
        finally:
            reseller_handlers.APIClient = original_api_client
            reseller_handlers._create_reseller_user_with_note = original_create
            reseller_handlers.add_reseller_debt = original_add_debt
            reseller_handlers.reseller_config_is_recorded = original_is_recorded

        self.assertTrue(captured_configs[0]["unlimited"])

    def test_reseller_customer_overview_and_empty_category_include_refresh(self):
        call = types.SimpleNamespace(
            message=types.SimpleNamespace(
                photo=None,
                document=None,
                sticker=None,
                chat=types.SimpleNamespace(id=100),
                message_id=200,
            )
        )
        categorized = {category: [] for category in reseller_handlers.RESELLER_CUSTOMER_CATEGORY_ORDER}

        reseller_handlers._render_reseller_customer_overview(call, "en", categorized, 0)
        overview_callbacks = [
            button.callback_data
            for button in reseller_handlers.bot.edits[-1][1]["reply_markup"].buttons
        ]
        self.assertIn("reseller:my_customers_refresh:overview:0", overview_callbacks)

        reseller_handlers._render_reseller_customer_category(call, "en", categorized, "active", 0)
        category_callbacks = [
            button.callback_data
            for button in reseller_handlers.bot.edits[-1][1]["reply_markup"].buttons
        ]
        self.assertIn("reseller:my_customers_refresh:active:0", category_callbacks)

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

    def test_status_action_opens_notify_or_silent_confirmation(self):
        original_is_admin = reseller_handlers.is_admin
        original_get_reseller_data = reseller_handlers.get_reseller_data
        try:
            reseller_handlers.bot.edits.clear()
            reseller_handlers.is_admin = lambda user_id: True
            reseller_handlers.get_reseller_data = lambda _user_id: {
                "status": "approved",
                "telegram_username": "buyer",
                "debt": 0.0,
                "configs": [],
            }
            call = types.SimpleNamespace(
                id="call-1",
                data="admin_reseller_ui:action:1988:suspend",
                from_user=types.SimpleNamespace(id=1),
                message=types.SimpleNamespace(chat=types.SimpleNamespace(id=100), message_id=200),
            )

            reseller_handlers.handle_admin_reseller_ui(call)

            edit_args, edit_kwargs = reseller_handlers.bot.edits[-1]
            self.assertIn("Confirm Suspend for 1988", edit_args[0])
            callbacks = [button.callback_data for button in edit_kwargs["reply_markup"].buttons]
            self.assertIn("admin_reseller_ui:actionconfirm:1988:suspend:notify", callbacks)
            self.assertIn("admin_reseller_ui:actionconfirm:1988:suspend:silent", callbacks)
        finally:
            reseller_handlers.is_admin = original_is_admin
            reseller_handlers.get_reseller_data = original_get_reseller_data

    def test_status_action_notify_updates_status_and_messages_reseller(self):
        original_is_admin = reseller_handlers.is_admin
        original_get_reseller_data = reseller_handlers.get_reseller_data
        original_update_status = reseller_handlers.update_reseller_status
        try:
            reseller_handlers.bot.sent_messages.clear()
            updates = []
            reseller_handlers.is_admin = lambda user_id: True
            reseller_handlers.get_reseller_data = lambda _user_id: {
                "status": "approved",
                "telegram_username": "buyer",
                "debt": 0.0,
                "configs": [],
            }
            reseller_handlers.update_reseller_status = lambda *args, **kwargs: updates.append((args, kwargs)) or True
            call = types.SimpleNamespace(
                id="call-1",
                data="admin_reseller_ui:actionconfirm:1988:ban:notify",
                from_user=types.SimpleNamespace(id=1),
                message=types.SimpleNamespace(chat=types.SimpleNamespace(id=100), message_id=200),
            )

            reseller_handlers.handle_admin_reseller_ui(call)

            self.assertEqual(updates[0], (("1988", "banned"), {}))
            self.assertEqual(reseller_handlers.bot.sent_messages[-1][0], (1988, "Banned notice"))
        finally:
            reseller_handlers.is_admin = original_is_admin
            reseller_handlers.get_reseller_data = original_get_reseller_data
            reseller_handlers.update_reseller_status = original_update_status

    def test_status_action_silent_updates_status_without_reseller_message(self):
        original_is_admin = reseller_handlers.is_admin
        original_get_reseller_data = reseller_handlers.get_reseller_data
        original_update_status = reseller_handlers.update_reseller_status
        try:
            reseller_handlers.bot.sent_messages.clear()
            updates = []
            reseller_handlers.is_admin = lambda user_id: True
            reseller_handlers.get_reseller_data = lambda _user_id: {
                "status": "banned",
                "telegram_username": "buyer",
                "debt": 0.0,
                "configs": [],
            }
            reseller_handlers.update_reseller_status = lambda *args, **kwargs: updates.append((args, kwargs)) or True
            call = types.SimpleNamespace(
                id="call-1",
                data="admin_reseller_ui:actionconfirm:1988:unban:silent",
                from_user=types.SimpleNamespace(id=1),
                message=types.SimpleNamespace(chat=types.SimpleNamespace(id=100), message_id=200),
            )

            reseller_handlers.handle_admin_reseller_ui(call)

            self.assertEqual(updates[0], (("1988", "suspended"), {"suspended_reason": "unban_grace"}))
            self.assertEqual(reseller_handlers.bot.sent_messages, [])
        finally:
            reseller_handlers.is_admin = original_is_admin
            reseller_handlers.get_reseller_data = original_get_reseller_data
            reseller_handlers.update_reseller_status = original_update_status

    def test_approve_remains_immediate_and_notifies_reseller(self):
        original_is_admin = reseller_handlers.is_admin
        original_get_reseller_data = reseller_handlers.get_reseller_data
        original_update_status = reseller_handlers.update_reseller_status
        try:
            reseller_handlers.bot.sent_messages.clear()
            updates = []
            reseller_handlers.is_admin = lambda user_id: True
            reseller_handlers.get_reseller_data = lambda _user_id: {
                "status": "pending",
                "telegram_username": "buyer",
                "debt": 0.0,
                "configs": [],
            }
            reseller_handlers.update_reseller_status = lambda *args, **kwargs: updates.append((args, kwargs)) or True
            call = types.SimpleNamespace(
                id="call-1",
                data="admin_reseller_ui:action:1988:approve",
                from_user=types.SimpleNamespace(id=1),
                message=types.SimpleNamespace(chat=types.SimpleNamespace(id=100), message_id=200),
            )

            reseller_handlers.handle_admin_reseller_ui(call)

            self.assertEqual(updates[0], (("1988", "approved"), {}))
            self.assertEqual(reseller_handlers.bot.sent_messages[-1][0], (1988, "Approved notice"))
            self.assertFalse(
                any(
                    "actionconfirm" in str(button.callback_data)
                    for _args, kwargs in reseller_handlers.bot.edits
                    for button in getattr(kwargs.get("reply_markup"), "buttons", [])
                )
            )
        finally:
            reseller_handlers.is_admin = original_is_admin
            reseller_handlers.get_reseller_data = original_get_reseller_data
            reseller_handlers.update_reseller_status = original_update_status

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
        self.assertIn("History records tagged: *2*", text)
        self.assertIn("Already missing, record tagged", text)
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
