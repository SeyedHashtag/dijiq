import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
PURCHASE_PLAN_PATH = ROOT / "core" / "scripts" / "telegrambot" / "utils" / "purchase_plan.py"
RESELLER_HANDLERS_PATH = ROOT / "core" / "scripts" / "telegrambot" / "utils" / "reseller_handlers.py"


class DummyMarkup:
    def __init__(self, *args, **kwargs):
        self.buttons = []

    def add(self, *args, **kwargs):
        self.buttons.extend(args)
        return self


class DummyButton:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs


class DummyQR:
    def save(self, bio, *_args, **_kwargs):
        bio.write(b"qr")


class DummyBot:
    def __init__(self):
        self.sent_photos = []
        self.sent_messages = []
        self.edited_messages = []
        self.deleted_messages = []
        self.callback_answers = []
        self.replies = []

    def message_handler(self, *args, **kwargs):
        return lambda func: func

    def callback_query_handler(self, *args, **kwargs):
        return lambda func: func

    def answer_callback_query(self, *args, **kwargs):
        self.callback_answers.append((args, kwargs))

    def edit_message_text(self, *args, **kwargs):
        self.edited_messages.append((args, kwargs))

    def delete_message(self, *args, **kwargs):
        self.deleted_messages.append((args, kwargs))

    def send_photo(self, *args, **kwargs):
        self.sent_photos.append((args, kwargs))
        return types.SimpleNamespace(
            chat=types.SimpleNamespace(id=args[0] if args else kwargs.get("chat_id")),
            message_id=321,
            photo=True,
        )

    def send_message(self, *args, **kwargs):
        self.sent_messages.append((args, kwargs))
        return types.SimpleNamespace(
            chat=types.SimpleNamespace(id=args[0] if args else kwargs.get("chat_id")),
            message_id=987,
        )

    def reply_to(self, *args, **kwargs):
        self.replies.append((args, kwargs))
        return types.SimpleNamespace(
            chat=types.SimpleNamespace(id=getattr(args[0], "chat", types.SimpleNamespace(id=None)).id if args else None),
            message_id=654,
        )


class FakeCryptoPayment:
    calls = []

    def create_payment(self, amount, plan_gb, user_id):
        self.calls.append({"amount": amount, "plan_gb": plan_gb, "user_id": user_id})
        return {
            "result": {
                "uuid": "payment-uuid",
                "url": "https://pay.example/checkout",
                "order_id": "gateway-order",
            }
        }


def clear_test_modules():
    for name in list(sys.modules):
        if name == "utils" or name.startswith("utils."):
            sys.modules.pop(name, None)
    sys.modules.pop("telebot", None)
    sys.modules.pop("qrcode", None)


def install_common_stubs(bot, payment_records):
    clear_test_modules()

    telebot_stub = types.ModuleType("telebot")
    telebot_stub.types = types.SimpleNamespace(
        InlineKeyboardMarkup=DummyMarkup,
        InlineKeyboardButton=DummyButton,
    )
    sys.modules["telebot"] = telebot_stub
    sys.modules["qrcode"] = types.SimpleNamespace(make=lambda *_args, **_kwargs: DummyQR())
    sys.modules["dotenv"] = types.SimpleNamespace(load_dotenv=lambda *args, **kwargs: None)

    utils_pkg = types.ModuleType("utils")
    utils_pkg.__path__ = []
    sys.modules["utils"] = utils_pkg

    command_stub = types.ModuleType("utils.command")
    command_stub.bot = bot
    command_stub.ADMIN_USER_IDS = []
    command_stub.is_admin = lambda user_id: False
    sys.modules["utils.command"] = command_stub

    common_stub = types.ModuleType("utils.common")
    common_stub.create_main_markup = lambda *args, **kwargs: DummyMarkup()
    sys.modules["utils.common"] = common_stub

    edit_plans_stub = types.ModuleType("utils.edit_plans")
    edit_plans_stub.load_plans = lambda: {"40": {"price": 100.0, "days": 30, "unlimited": False}}
    sys.modules["utils.edit_plans"] = edit_plans_stub

    payments_stub = types.ModuleType("utils.payments")
    payments_stub.CryptoPayment = FakeCryptoPayment
    sys.modules["utils.payments"] = payments_stub

    payment_records_stub = types.ModuleType("utils.payment_records")
    payment_records_stub.add_payment_record = lambda payment_id, record: payment_records.append((payment_id, record))
    payment_records_stub.update_payment_status = lambda *args, **kwargs: True
    payment_records_stub.get_payment_record = lambda *args, **kwargs: None
    payment_records_stub.load_payments = lambda: {}
    payment_records_stub.claim_payment_for_processing = lambda *args, **kwargs: True
    payment_records_stub.get_user_payments = lambda *args, **kwargs: {}
    payment_records_stub.update_payment_record_fields = lambda *args, **kwargs: True
    sys.modules["utils.payment_records"] = payment_records_stub

    api_client_stub = types.ModuleType("utils.api_client")
    api_client_stub.APIClient = object
    api_client_stub.MultiServerAPI = object
    sys.modules["utils.api_client"] = api_client_stub

    translations_stub = types.ModuleType("utils.translations")
    translations_stub.BUTTON_TRANSLATIONS = {"en": {}}
    translations_stub.get_button_text = lambda _language, key: key
    translations_stub.get_message_text = lambda _language, key: {
        "payment_instructions": "Complete ${price} at {payment_url} id {payment_id}",
        "crypto_discount_summary": "Crypto discount applied: {percent}% off\nOriginal price: ${original_price}\nDiscount: -${discount_amount}\nFinal crypto price: ${discounted_price}",
        "crypto_discount_button": "Crypto - {percent}% OFF",
        "plan_details": "Plan details\n",
        "data": "Data {plan_gb}\n",
        "duration": "Duration {days}\n",
        "unlimited": "Unlimited {unlimited_text}\n",
        "price": "Price ${price}\n",
        "exchange_rate": "Exchange {exchange_rate}\n",
        "toman_price": "Tomans {toman_price}\n",
        "select_payment_method": "Select payment method",
        "purchase_connection_warning": "",
        "reseller_purchase_details": (
            "Plan {plan_gb} GB for {days} days costs ${price}. "
            "Debt ${current_debt} -> ${projected_debt}. Limit ${trust_limit}."
        ),
        "reseller_trust_limit_exceeded": (
            "Trust limit exceeded: debt ${current_debt:.2f}, add ${purchase_adds:.2f}, "
            "projected ${projected_debt:.2f}, limit ${trust_limit:.2f}, credit ${available_credit:.2f}."
        ),
        "reseller_trust_limit_exceeded_short": "Trust limit ${trust_limit:.2f}; credit ${available_credit:.2f}.",
        "error_creating_payment": "error {error}",
        "invalid_payment_response": "invalid",
        "plan_not_found": "plan not found",
        "debt_cleared": "debt cleared",
        "card_to_card_payment": "Transfer {price} at {exchange_rate} to {card_number}",
        "reseller_suspended_due_debt": "Account suspended due to debt (${debt:.2f}); unlock ${unlock_amount:.2f}",
        "cancel": "cancel",
    }.get(key, key)
    sys.modules["utils.translations"] = translations_stub

    language_stub = types.ModuleType("utils.language")
    language_stub.get_user_language = lambda _user_id: "en"
    sys.modules["utils.language"] = language_stub

    referral_stub = types.ModuleType("utils.referral")
    referral_stub.add_referral_reward = lambda *args, **kwargs: None
    referral_stub.get_pending_withdrawal_requests = lambda: []
    sys.modules["utils.referral"] = referral_stub

    reseller_stub = types.ModuleType("utils.reseller")
    reseller_stub.evaluate_reseller_debt_policies = lambda: []
    reseller_stub.DEBT_WARNING_THRESHOLD = 20.0
    reseller_stub.DEBT_SUSPEND_THRESHOLD = 50.0
    reseller_stub.SUSPENDED_REASON_UNBAN_GRACE = "unban_grace"
    reseller_stub.get_reseller_data = lambda _user_id: {"status": "approved", "debt": 100.0}
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
    reseller_stub.update_reseller_status = lambda *args, **kwargs: True
    reseller_stub.add_reseller_debt = lambda *args, **kwargs: True
    reseller_stub.get_all_resellers = lambda: {}
    reseller_stub.set_reseller_debt = lambda *args, **kwargs: True
    reseller_stub.apply_reseller_payment = lambda user_id, amount: (True, max(0.0, 100.0 - float(amount or 0.0)))

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
    reseller_stub.get_banned_reseller_cleanup_candidates = lambda reseller_data: []
    reseller_stub.cleanup_banned_reseller_users = lambda user_id, multi_api: (True, {})
    sys.modules["utils.reseller"] = reseller_stub

    currency_stub = types.ModuleType("utils.currency_format")
    currency_stub.format_toman_amount = lambda value: str(int(round(float(value))))
    currency_stub.format_usd_amount = lambda value: f"{float(value):.2f}"
    sys.modules["utils.currency_format"] = currency_stub

    receipt_checker_stub = types.ModuleType("utils.receipt_checker")
    receipt_checker_stub.RECEIPT_TYPE_REGULAR = "regular"
    receipt_checker_stub.RECEIPT_TYPE_SETTLEMENT = "settlement"
    receipt_checker_stub.calculate_checker_share_amount = lambda amount, percent=None: round(float(amount) * float(percent or 10) / 100, 2)
    receipt_checker_stub.calculate_checker_share_amount_toman = lambda amount, percent=None: round(float(amount) * float(percent or 10) / 100)
    receipt_checker_stub.can_review_receipt = lambda *args, **kwargs: True
    receipt_checker_stub.get_card_number_for_receipt_type = lambda _receipt_type: "1234"
    receipt_checker_stub.get_receipt_checker_user_id = lambda: None
    receipt_checker_stub.get_receipt_checker_share_percent = lambda: 10.0
    receipt_checker_stub.get_receipt_type_label = lambda receipt_type: receipt_type
    receipt_checker_stub.is_receipt_checker = lambda _user_id: False
    receipt_checker_stub.should_route_to_receipt_checker = lambda _receipt_type: False
    sys.modules["utils.receipt_checker"] = receipt_checker_stub

    username_utils_stub = types.ModuleType("utils.username_utils")
    username_utils_stub.allocate_username = lambda prefix, user_id, _existing: f"{prefix}{user_id}"
    username_utils_stub.build_user_note = lambda **kwargs: kwargs.get("note_text", "")
    username_utils_stub.extract_existing_usernames = lambda _users: set()
    username_utils_stub.format_username_timestamp = lambda: "260603000000"
    sys.modules["utils.username_utils"] = username_utils_stub


def load_purchase_plan(bot=None, payment_records=None):
    bot = bot or DummyBot()
    payment_records = payment_records if payment_records is not None else []
    install_common_stubs(bot, payment_records)
    FakeCryptoPayment.calls = []
    spec = importlib.util.spec_from_file_location("purchase_plan_under_test", PURCHASE_PLAN_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    sys.modules["utils.purchase_plan"] = module
    return module


def load_reseller_handlers(purchase_plan):
    spec = importlib.util.spec_from_file_location("reseller_handlers_under_test", RESELLER_HANDLERS_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def make_call(data):
    return types.SimpleNamespace(
        data=data,
        id="callback-id",
        from_user=types.SimpleNamespace(id=1988, username="buyer"),
        message=types.SimpleNamespace(chat=types.SimpleNamespace(id=555), message_id=777),
    )


def make_admin_approval_call(action):
    return types.SimpleNamespace(
        data=f"admin_approval:{action}:settlement-payment",
        id="approval-callback-id",
        from_user=types.SimpleNamespace(id=1, first_name="Admin"),
        message=types.SimpleNamespace(
            chat=types.SimpleNamespace(id=555),
            message_id=777,
            caption="Pending settlement",
        ),
    )


class CryptoPaymentDiscountTests(unittest.TestCase):
    def test_crypto_discount_helper_rounds_to_two_decimals(self):
        purchase_plan = load_purchase_plan()

        self.assertEqual(purchase_plan.apply_crypto_discount(100), 95.0)
        self.assertEqual(purchase_plan.apply_crypto_discount("1.01"), 0.96)

    def test_customer_crypto_payment_uses_discounted_amount(self):
        bot = DummyBot()
        payment_records = []
        purchase_plan = load_purchase_plan(bot, payment_records)

        purchase_plan.handle_crypto_payment(make_call("payment_method:crypto:40"), "40")

        self.assertEqual(FakeCryptoPayment.calls[0]["amount"], 95.0)
        payment_id, record = payment_records[0]
        self.assertEqual(payment_id, "payment-uuid")
        self.assertEqual(record["price"], 95.0)
        self.assertEqual(record["original_price"], 100.0)
        self.assertEqual(record["discount_percent"], 5)
        self.assertEqual(record["discount_amount"], 5.0)
        caption = bot.sent_photos[0][1]["caption"]
        self.assertIn("$95.00", caption)
        self.assertIn("5% off", caption)
        self.assertIn("Original price: $100.00", caption)
        self.assertIn("Discount: -$5.00", caption)
        self.assertIn("Final crypto price: $95.00", caption)

    def test_customer_plan_screen_advertises_crypto_discount(self):
        bot = DummyBot()
        purchase_plan = load_purchase_plan(bot, [])

        with patch.dict("os.environ", {"CRYPTO_MERCHANT_ID": "merchant", "CRYPTO_API_KEY": "key"}):
            purchase_plan.handle_purchase_selection(make_call("purchase:40"))

        message = bot.edited_messages[0][0][0]
        markup = bot.edited_messages[0][1]["reply_markup"]
        button_texts = [button.args[0] for button in markup.buttons]

        self.assertNotIn("Crypto discount", message)
        self.assertNotIn("pay $95.00 instead of $100.00", message)
        self.assertIn("Crypto - 5% OFF", button_texts)

    def test_reseller_crypto_settlement_uses_discounted_amount(self):
        bot = DummyBot()
        payment_records = []
        purchase_plan = load_purchase_plan(bot, payment_records)
        reseller_handlers = load_reseller_handlers(purchase_plan)
        apply_calls = []
        sys.modules["utils.reseller"].apply_reseller_payment = lambda user_id, amount: apply_calls.append((user_id, amount))

        reseller_handlers.handle_reseller_payment(make_call("reseller:pay:crypto:100.00"))

        self.assertEqual(FakeCryptoPayment.calls[0]["amount"], 95.0)
        payment_id, record = payment_records[0]
        self.assertEqual(payment_id, "payment-uuid")
        self.assertEqual(record["plan_gb"], "Settlement")
        self.assertEqual(record["price"], 95.0)
        self.assertEqual(record["original_price"], 100.0)
        self.assertEqual(record["settlement_amount"], 100.0)
        self.assertEqual(record["discount_percent"], 5)
        self.assertEqual(record["discount_amount"], 5.0)
        self.assertEqual(purchase_plan._settlement_credit_amount(record), 100.0)
        caption = bot.sent_photos[0][1]["caption"]
        self.assertIn("$95.00", caption)
        self.assertIn("5% off", caption)
        self.assertIn("Original price: $100.00", caption)
        self.assertIn("Discount: -$5.00", caption)
        self.assertIn("Final crypto price: $95.00", caption)
        self.assertEqual(apply_calls, [])

    def test_approved_settlement_payment_applies_reseller_credit(self):
        bot = DummyBot()
        purchase_plan = load_purchase_plan(bot, [])
        payment_record = {
            "status": "pending_approval",
            "type": "settlement",
            "plan_gb": "Settlement",
            "user_id": 1988,
            "price": 95.0,
            "settlement_amount": 100.0,
            "payment_method": "Crypto",
        }
        apply_calls = []
        statuses = []
        sys.modules["utils.reseller"].apply_reseller_payment = lambda user_id, amount: apply_calls.append((user_id, amount))
        purchase_plan.is_admin = lambda _user_id: True
        purchase_plan.get_payment_record = lambda _payment_id: payment_record
        purchase_plan.update_payment_status = lambda payment_id, status: statuses.append((payment_id, status))
        purchase_plan.send_admin_payment_notification = lambda *args, **kwargs: None

        purchase_plan.handle_admin_approval(make_admin_approval_call("approve"))

        self.assertEqual(apply_calls, [(1988, 100.0)])
        self.assertEqual(statuses, [("settlement-payment", "completed")])

    def test_rejected_settlement_payment_does_not_apply_reseller_credit(self):
        bot = DummyBot()
        purchase_plan = load_purchase_plan(bot, [])
        payment_record = {
            "status": "pending_approval",
            "type": "settlement",
            "plan_gb": "Settlement",
            "user_id": 1988,
            "price": 95.0,
            "settlement_amount": 100.0,
            "payment_method": "Crypto",
        }
        apply_calls = []
        statuses = []
        sys.modules["utils.reseller"].apply_reseller_payment = lambda user_id, amount: apply_calls.append((user_id, amount))
        purchase_plan.is_admin = lambda _user_id: True
        purchase_plan.get_payment_record = lambda _payment_id: payment_record
        purchase_plan.update_payment_status = lambda payment_id, status: statuses.append((payment_id, status))

        purchase_plan.handle_admin_approval(make_admin_approval_call("reject"))

        self.assertEqual(apply_calls, [])
        self.assertEqual(statuses, [("settlement-payment", "rejected")])

    def test_reseller_settlement_screen_advertises_crypto_discount(self):
        bot = DummyBot()
        purchase_plan = load_purchase_plan(bot, [])
        reseller_handlers = load_reseller_handlers(purchase_plan)

        with patch.dict("os.environ", {"CRYPTO_MERCHANT_ID": "merchant", "CRYPTO_API_KEY": "key"}):
            reseller_handlers.handle_reseller_settle(make_call("reseller:settle:all"))

        message = bot.edited_messages[0][0][0]
        markup = bot.edited_messages[0][1]["reply_markup"]
        button_texts = [button.args[0] for button in markup.buttons]

        self.assertNotIn("Crypto discount", message)
        self.assertNotIn("pay $95.00 instead of $100.00", message)
        self.assertIn("Crypto - 5% OFF", button_texts)

    def test_reseller_card_settlement_keeps_full_amount(self):
        bot = DummyBot()
        purchase_plan = load_purchase_plan(bot, [])
        reseller_handlers = load_reseller_handlers(purchase_plan)
        reseller_handlers.get_exchange_rate = lambda: 2.0

        reseller_handlers.handle_reseller_payment(make_call("reseller:pay:card:100.00"))

        self.assertEqual(FakeCryptoPayment.calls, [])
        self.assertEqual(purchase_plan.user_data[1988]["price"], 100.0)
        self.assertEqual(purchase_plan.user_data[1988]["settlement_amount"], 100.0)
        self.assertEqual(purchase_plan.user_data[1988]["converted_amount"], 200.0)
        self.assertNotIn("Crypto discount", bot.edited_messages[0][0][0])
        self.assertNotIn("5% off", bot.edited_messages[0][0][0])

    def test_zero_paid_reseller_can_reach_five_dollar_trust_limit(self):
        bot = DummyBot()
        purchase_plan = load_purchase_plan(bot, [])
        reseller_handlers = load_reseller_handlers(purchase_plan)
        reseller_handlers.load_plans = lambda: {"5": {"price": 6.25, "days": 30, "unlimited": False}}
        reseller_handlers.get_exchange_rate = lambda: 1.0
        reseller_handlers.get_reseller_data = lambda _user_id: {
            "status": "approved",
            "debt": 0.0,
            "total_paid": 0.0,
            "configs": [],
        }

        reseller_handlers.handle_reseller_buy(make_call("reseller:buy:5"))

        message = bot.edited_messages[0][0][0]
        self.assertIn("Debt $0.00 -> $5.00", message)
        self.assertIn("Limit $5.00", message)
        self.assertNotIn("Trust limit exceeded", message)

    def test_zero_paid_reseller_purchase_over_five_dollars_is_blocked(self):
        bot = DummyBot()
        purchase_plan = load_purchase_plan(bot, [])
        reseller_handlers = load_reseller_handlers(purchase_plan)
        reseller_handlers.load_plans = lambda: {"5": {"price": 2.5, "days": 30, "unlimited": False}}
        reseller_handlers.get_reseller_data = lambda _user_id: {
            "status": "approved",
            "debt": 4.0,
            "total_paid": 0.0,
            "configs": [],
        }

        reseller_handlers.handle_reseller_buy(make_call("reseller:buy:5"))

        message = bot.edited_messages[0][0][0]
        self.assertIn("Trust limit exceeded", message)
        self.assertIn("projected $6.00", message)
        self.assertIn("limit $5.00", message)

    def test_ten_paid_reseller_can_reach_ten_dollar_trust_limit(self):
        bot = DummyBot()
        purchase_plan = load_purchase_plan(bot, [])
        reseller_handlers = load_reseller_handlers(purchase_plan)
        reseller_handlers.load_plans = lambda: {"5": {"price": 2.5, "days": 30, "unlimited": False}}
        reseller_handlers.get_exchange_rate = lambda: 1.0
        reseller_handlers.get_reseller_data = lambda _user_id: {
            "status": "approved",
            "debt": 8.0,
            "total_paid": 10.0,
            "configs": [],
        }

        reseller_handlers.handle_reseller_buy(make_call("reseller:buy:5"))

        message = bot.edited_messages[0][0][0]
        self.assertIn("Debt $8.00 -> $10.00", message)
        self.assertIn("Limit $10.00", message)
        self.assertNotIn("Trust limit exceeded", message)

    def test_fifty_paid_reseller_is_capped_at_thirty_dollar_trust_limit(self):
        bot = DummyBot()
        purchase_plan = load_purchase_plan(bot, [])
        reseller_handlers = load_reseller_handlers(purchase_plan)
        reseller_handlers.load_plans = lambda: {"5": {"price": 2.5, "days": 30, "unlimited": False}}
        reseller_handlers.get_reseller_data = lambda _user_id: {
            "status": "approved",
            "debt": 29.0,
            "total_paid": 50.0,
            "configs": [],
        }

        reseller_handlers.handle_reseller_buy(make_call("reseller:buy:5"))

        message = bot.edited_messages[0][0][0]
        self.assertIn("Trust limit exceeded", message)
        self.assertIn("limit $30.00", message)
        self.assertIn("credit $1.00", message)

    def test_old_crypto_settlement_record_credits_original_amount(self):
        purchase_plan = load_purchase_plan()
        record = {
            "type": "settlement",
            "price": 95.0,
            "original_price": 100.0,
        }

        self.assertEqual(purchase_plan._settlement_credit_amount(record), 100.0)

    def test_suspended_reseller_can_open_settlement_but_not_generate(self):
        bot = DummyBot()
        purchase_plan = load_purchase_plan(bot, [])
        reseller_handlers = load_reseller_handlers(purchase_plan)
        reseller_handlers.get_reseller_data = lambda _user_id: {
            "status": "suspended",
            "debt": 100.0,
            "debt_state": "suspended",
        }

        with patch.dict("os.environ", {"CRYPTO_MERCHANT_ID": "merchant", "CRYPTO_API_KEY": "key"}):
            reseller_handlers.handle_reseller_settle(make_call("reseller:settle:100.00"))

        self.assertEqual(bot.edited_messages[0][0][0], "Select payment method")
        reseller_handlers.handle_reseller_generate(make_call("reseller:generate"))
        self.assertIn("Account suspended due to debt", bot.callback_answers[-1][0][1])

    def test_suspended_low_debt_reseller_generate_message_shows_full_debt_to_unlock(self):
        bot = DummyBot()
        purchase_plan = load_purchase_plan(bot, [])
        reseller_handlers = load_reseller_handlers(purchase_plan)
        reseller_handlers.get_reseller_data = lambda _user_id: {
            "status": "suspended",
            "debt": 14.36,
            "debt_state": "suspended",
        }

        reseller_handlers.handle_reseller_generate(make_call("reseller:generate"))

        self.assertIn("unlock $14.36", bot.callback_answers[-1][0][1])
        self.assertNotIn("unlock $0.00", bot.callback_answers[-1][0][1])

    def test_checker_no_pending_confirmations_shows_my_stats_button(self):
        bot = DummyBot()
        purchase_plan = load_purchase_plan(bot, [])
        purchase_plan.is_receipt_checker = lambda _user_id: True

        message = types.SimpleNamespace(
            text="✅ Confirmations",
            from_user=types.SimpleNamespace(id=1988),
            chat=types.SimpleNamespace(id=555),
        )
        purchase_plan.show_pending_confirmations(message)

        reply_args, reply_kwargs = bot.replies[0]
        self.assertEqual(reply_args[1], "No pending receipt confirmations.")
        markup = reply_kwargs["reply_markup"]
        self.assertEqual(markup.buttons[0].args[0], "📊 My Stats")
        self.assertEqual(markup.buttons[0].kwargs["callback_data"], "checker_stats:my")

    def test_admin_pending_confirmations_include_referral_withdrawals(self):
        bot = DummyBot()
        purchase_plan = load_purchase_plan(bot, [])
        purchase_plan.is_admin = lambda _user_id: True
        purchase_plan.get_pending_withdrawal_requests = lambda: [{
            "id": "req-1",
            "user_id": "20",
            "telegram_username": "alice",
            "amount": 4.5,
            "wallet": "ltc20",
            "requested_at": "2026-06-01 10:00:00",
            "available_balance_after": 0,
            "total_earnings": 9.25,
            "invited_count": 4,
        }]

        message = types.SimpleNamespace(
            text="✅ Confirmations",
            from_user=types.SimpleNamespace(id=1),
            chat=types.SimpleNamespace(id=555),
        )
        purchase_plan.show_pending_confirmations(message)

        self.assertEqual(bot.replies[0][0][1], "Pending confirmations: 1")
        self.assertIn("Pending Referral Withdrawal", bot.sent_messages[0][0][1])
        self.assertIn("Request ID: `req-1`", bot.sent_messages[0][0][1])
        markup = bot.sent_messages[0][1]["reply_markup"]
        self.assertEqual(markup.buttons[0].kwargs["callback_data"], "admin_pay_ref:req-1")

    def test_reseller_purchase_details_includes_connection_warning(self):
        purchase_plan = load_purchase_plan()
        reseller_handlers = load_reseller_handlers(purchase_plan)
        reseller_handlers.get_message_text = lambda _language, key: {
            "reseller_purchase_details": "Plan {plan_gb} costs ${price}.",
            "purchase_connection_warning": "\n\nVPN warning",
        }.get(key, key)

        details = reseller_handlers._build_reseller_purchase_details("en", "40", 30, 80.0, 10.0, 30.0)

        self.assertIn("Plan 40 costs $80.00.", details)
        self.assertIn("VPN warning", details)


if __name__ == "__main__":
    unittest.main()
