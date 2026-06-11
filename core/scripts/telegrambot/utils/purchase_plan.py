import json
import datetime
from telebot import types
from utils.command import bot, ADMIN_USER_IDS, is_admin
from utils.common import create_main_markup
from utils.edit_plans import load_plans
from utils.payments import CryptoPayment
from utils.payment_records import (
    add_payment_record,
    update_payment_status,
    get_payment_record,
    load_payments,
    claim_payment_for_processing,
    get_user_payments,
    update_payment_record_fields,
)
from utils.api_client import APIClient, MultiServerAPI
from utils.translations import BUTTON_TRANSLATIONS, get_message_text, get_button_text
from utils.language import get_user_language
from utils.referral import add_referral_reward, get_pending_withdrawal_requests
from utils.reseller import evaluate_reseller_debt_policies, DEBT_WARNING_THRESHOLD, DEBT_SUSPEND_THRESHOLD
from utils.currency_format import format_toman_amount, format_usd_amount
from utils.receipt_checker import (
    RECEIPT_TYPE_REGULAR,
    RECEIPT_TYPE_SETTLEMENT,
    calculate_checker_share_amount,
    calculate_checker_share_amount_toman,
    can_review_receipt,
    get_card_number_for_receipt_type,
    get_receipt_checker_user_id,
    get_receipt_checker_share_percent,
    get_receipt_type_label,
    is_receipt_checker,
    should_route_to_receipt_checker,
)
import qrcode
import io
import os
from decimal import Decimal, ROUND_HALF_UP
from dotenv import load_dotenv
import uuid
import logging
from utils.username_utils import (
    allocate_username,
    build_user_note,
    extract_existing_usernames,
    format_username_timestamp,
)

# New: Global dictionary for user states
user_data = {}

TELEGRAM_ENV_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.env'))
CRYPTO_PAYMENT_DISCOUNT_PERCENT = 5


def apply_crypto_discount(amount):
    value = Decimal(str(amount))
    multiplier = Decimal('1') - (Decimal(str(CRYPTO_PAYMENT_DISCOUNT_PERCENT)) / Decimal('100'))
    return float((value * multiplier).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


def build_crypto_discount_metadata(original_amount):
    original_decimal = Decimal(str(original_amount))
    original_price = float(original_decimal)
    discounted_price = apply_crypto_discount(original_decimal)
    discount_amount = float(
        (original_decimal - Decimal(str(discounted_price))).quantize(
            Decimal('0.01'),
            rounding=ROUND_HALF_UP,
        )
    )
    return {
        'price': discounted_price,
        'original_price': original_price,
        'discount_percent': CRYPTO_PAYMENT_DISCOUNT_PERCENT,
        'discount_amount': discount_amount,
    }


def build_crypto_discount_display(language, discount_metadata):
    return {
        'summary': get_message_text(language, "crypto_discount_summary").format(
            percent=discount_metadata['discount_percent'],
            original_price=format_usd_amount(discount_metadata['original_price']),
            discounted_price=format_usd_amount(discount_metadata['price']),
            discount_amount=format_usd_amount(discount_metadata['discount_amount']),
        ),
        'button_text': get_crypto_discount_button_text(language),
    }


def get_crypto_discount_button_text(language):
    return get_message_text(language, "crypto_discount_button").format(
        percent=CRYPTO_PAYMENT_DISCOUNT_PERCENT
    )


def get_exchange_rate():
    load_dotenv(TELEGRAM_ENV_PATH, override=True)
    try:
        return float(os.getenv('EXCHANGE_RATE', '1'))
    except (TypeError, ValueError):
        return 1.0


def _debt_state_label_key(debt_state):
    if debt_state == 'suspended':
        return 'debt_state_suspended'
    if debt_state == 'warning':
        return 'debt_state_warning'
    return 'debt_state_active'


def _receipt_type_from_record(payment_record):
    receipt_type = payment_record.get('receipt_type')
    if receipt_type:
        return receipt_type
    if payment_record.get('type') == 'settlement' or payment_record.get('plan_gb') == 'Settlement':
        return RECEIPT_TYPE_SETTLEMENT
    return RECEIPT_TYPE_REGULAR


def _settlement_credit_amount(payment_record):
    return payment_record.get(
        'settlement_amount',
        payment_record.get('original_price', payment_record.get('price', 0))
    )


def _build_receipt_approval_markup(payment_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✅ Approve", callback_data=f"admin_approval:approve:{payment_id}"),
        types.InlineKeyboardButton("❌ Reject", callback_data=f"admin_approval:reject:{payment_id}")
    )
    return markup


def _format_pending_receipt_caption(payment_id, payment_record, telegram_username=None):
    receipt_type = _receipt_type_from_record(payment_record)
    user_id = payment_record.get('user_id')
    plan_label = "Settlement" if receipt_type == RECEIPT_TYPE_SETTLEMENT else f"{payment_record.get('plan_gb')} GB"
    caption = (
        f"⏳ New Pending Payment\n\n"
        f"A user has submitted a receipt for a 'Card to Card' payment.\n\n"
        f"🧾 <b>Receipt Type:</b> {get_receipt_type_label(receipt_type)}\n"
        f"👤 <b>User ID:</b> <code>{user_id}</code>\n"
    )
    if telegram_username:
        caption += f"📱 <b>Telegram Username:</b> @{telegram_username}\n"
    caption += (
        f"📊 <b>Plan:</b> {plan_label}\n"
        f"💵 <b>Amount:</b> ${format_usd_amount(payment_record.get('price', 0))}\n"
    )
    if payment_record.get('converted_amount') is not None:
        currency_label = payment_record.get('converted_currency') or "Tomans"
        caption += f"💱 <b>Converted Amount:</b> {format_toman_amount(payment_record.get('converted_amount'))} {currency_label}\n"
    if payment_record.get('created_at'):
        caption += f"📅 <b>Submitted:</b> {payment_record.get('created_at')}\n"
    caption += f"🔑 <b>Payment ID:</b> <code>{payment_id}</code>"
    return caption


def _send_receipt_confirmation(chat_id, payment_id, payment_record, caption=None):
    caption = caption or _format_pending_receipt_caption(payment_id, payment_record)
    markup = _build_receipt_approval_markup(payment_id)
    receipt_path = payment_record.get('receipt_path')
    if receipt_path and os.path.exists(receipt_path):
        with open(receipt_path, 'rb') as photo:
            sent_message = bot.send_photo(
                chat_id,
                photo,
                caption=caption,
                reply_markup=markup,
                parse_mode="HTML"
            )
    else:
        sent_message = bot.send_message(
            chat_id,
            caption + "\n\nReceipt image is not available on disk.",
            reply_markup=markup,
            parse_mode="HTML"
        )
    return sent_message


def _build_referral_withdrawal_markup(request_id):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("✅ Mark as Paid", callback_data=f"admin_pay_ref:{request_id}"))
    return markup


def _format_pending_referral_withdrawal(withdrawal_request):
    username = str(withdrawal_request.get("telegram_username") or "").strip().lstrip("@")
    telegram_line = f"Telegram: `@{username}`\n" if username else ""
    return (
        "💸 **Pending Referral Withdrawal**\n\n"
        f"Request ID: `{withdrawal_request.get('id')}`\n"
        f"User ID: `{withdrawal_request.get('user_id')}`\n"
        f"{telegram_line}"
        f"Amount: ${float(withdrawal_request.get('amount', 0) or 0):.2f}\n"
        f"Wallet: `{withdrawal_request.get('wallet')}`\n\n"
        "📊 **Referral Stats**\n"
        f"Invited Users: {withdrawal_request.get('invited_count', 0)}\n"
        f"Total Earnings: ${float(withdrawal_request.get('total_earnings', 0) or 0):.2f}\n"
        f"Remaining Balance: ${float(withdrawal_request.get('available_balance_after', 0) or 0):.2f}\n"
        f"Requested At: {withdrawal_request.get('requested_at', '')}"
    )


def _send_referral_withdrawal_confirmation(chat_id, withdrawal_request):
    return bot.send_message(
        chat_id,
        _format_pending_referral_withdrawal(withdrawal_request),
        reply_markup=_build_referral_withdrawal_markup(withdrawal_request.get("id")),
        parse_mode="Markdown"
    )


def _save_receipt_message_refs(payment_id, refs):
    if refs:
        update_payment_record_fields(payment_id, {"receipt_message_refs": refs})


def _update_receipt_message_refs(payment_id, payment_record, final_caption):
    refs = payment_record.get('receipt_message_refs') or []
    for ref in refs:
        try:
            chat_id = ref.get('chat_id')
            message_id = ref.get('message_id')
            content_type = ref.get('content_type')
            if content_type == 'photo':
                bot.edit_message_caption(
                    caption=final_caption,
                    chat_id=chat_id,
                    message_id=message_id,
                    reply_markup=None
                )
            else:
                bot.edit_message_text(
                    final_caption,
                    chat_id=chat_id,
                    message_id=message_id,
                    reply_markup=None,
                    parse_mode="HTML"
                )
        except Exception as e:
            print(f"Failed to update receipt message {payment_id}: {str(e)}")

    if not refs:
        try:
            bot.edit_message_reply_markup(
                chat_id=payment_record.get('last_receipt_chat_id'),
                message_id=payment_record.get('last_receipt_message_id'),
                reply_markup=None
            )
        except Exception:
            pass


def _is_confirmation_viewer(user_id):
    return is_admin(user_id) or is_receipt_checker(user_id)


def _record_review_audit(payment_id, call, action, reviewer_role):
    update_payment_record_fields(payment_id, {
        "reviewed_by_user_id": call.from_user.id,
        "reviewed_by_role": reviewer_role,
        "reviewed_action": action,
        "reviewed_at": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    })


def _record_checker_share_audit(payment_id, payment_record):
    if not payment_record.get('routed_to_checker'):
        return
    share_percent = get_receipt_checker_share_percent()
    fields = {
        "checker_share_percent": share_percent,
        "checker_share_amount": calculate_checker_share_amount(payment_record.get('price', 0), share_percent),
    }
    if payment_record.get('converted_amount') is not None:
        fields.update({
            "checker_accounting_amount_toman": payment_record.get('converted_amount'),
            "checker_share_amount_toman": calculate_checker_share_amount_toman(payment_record.get('converted_amount'), share_percent),
        })
    update_payment_record_fields(payment_id, fields)


def create_sale_username(api_client, user_id):
    if isinstance(api_client, set):
        return allocate_username("s", user_id, api_client)
    multi_api = MultiServerAPI()
    creation = multi_api.prepare_new_user_creation()
    usernames = creation.get("existing_usernames") or set()
    if not usernames and api_client is not None:
        users = api_client.get_users()
        usernames = extract_existing_usernames(users)
    return allocate_username("s", user_id, usernames)


def create_sale_user_with_note(api_client, user_id, plan_gb, days, unlimited):
    multi_api = MultiServerAPI()

    def allocate(existing_usernames):
        return allocate_username("s", user_id, existing_usernames)

    def create(target_client, username):
        note_payload = build_user_note(
            username=username,
            traffic_limit=plan_gb,
            expiration_days=days,
            unlimited=unlimited,
            note_text="sale",
        )
        result = target_client.add_user(
            username,
            int(plan_gb),
            int(days),
            unlimited=unlimited,
            note=note_payload,
        )
        if result is None:
            result = target_client.add_user(username, int(plan_gb), int(days), unlimited=unlimited)
            if result is not None:
                logging.getLogger("dijiq.usernames").warning(
                    "Created sale user without note fallback. user_id=%s username=%s",
                    user_id,
                    username,
                )
        return result

    return multi_api.create_user_with_retry(allocate, create, fallback_client=api_client)

def send_admin_payment_notification(
    user_id,
    username,
    plan_gb,
    price,
    payment_id,
    payment_method,
    telegram_username=None,
    converted_amount=None,
    converted_currency=None,
    exchange_rate=None,
):
    """Send a notification to all admins about a successful payment"""
    try:
        for admin_id in ADMIN_USER_IDS:
            admin_language = get_user_language(admin_id)
            notification_message = (
                f"💰 <b>{get_message_text(admin_language, 'payment_notification_title')}</b>\n\n"
                f"✅ <b>{get_message_text(admin_language, 'successful_payment_received')}</b>\n\n"
                f"👤 <b>{get_message_text(admin_language, 'user_id')}:</b> <code>{user_id}</code>\n"
            )
            
            if telegram_username:
                 notification_message += f"📱 <b>Telegram Username:</b> @{telegram_username}\n"
            
            notification_message += (
                f"📱 <b>{get_message_text(admin_language, 'username')}:</b> <code>{username}</code>\n"
                f"📊 <b>{get_message_text(admin_language, 'plan_size')}:</b> {plan_gb} GB\n"
                f"💵 <b>{get_message_text(admin_language, 'amount')}:</b> ${format_usd_amount(price)}\n"
            )
            if converted_amount is not None:
                currency_label = converted_currency or "Tomans"
                notification_message += f"💱 <b>Converted Amount:</b> {format_toman_amount(converted_amount)} {currency_label}\n"

            notification_message += (
                f"💳 <b>{get_message_text(admin_language, 'payment_method_label')}:</b> {payment_method}\n"
                f"🔑 <b>{get_message_text(admin_language, 'payment_id_label')}:</b> <code>{payment_id}</code>\n"
                f"📅 <b>{get_message_text(admin_language, 'timestamp')}:</b> {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            try:
                bot.send_message(
                    admin_id,
                    notification_message,
                    parse_mode="HTML"
                )
            except Exception as e:
                print(f"Failed to send notification to admin {admin_id}: {str(e)}")
    except Exception as e:
        print(f"Error in send_admin_payment_notification: {str(e)}")

def show_plans(chat_id, user_id, message_id=None):
    language = get_user_language(user_id)
    plans = load_plans()
    sorted_plans = sorted(plans.items(), key=lambda x: int(x[0]))
    markup = types.InlineKeyboardMarkup(row_width=1)
    for gb, details in sorted_plans:
        if details.get('target', 'both') == 'reseller':
            continue
        unlimited_text = get_message_text(language, "unlimited_users") if details.get("unlimited") else get_message_text(language, "single_user")
        button_text = f"{gb} GB - ${format_usd_amount(details['price'])} - {details['days']} " + get_message_text(language, "days") + f"{unlimited_text}"
        markup.add(types.InlineKeyboardButton(button_text, callback_data=f"purchase:{gb}"))
    
    text = get_message_text(language, "select_plan")
    
    if message_id:
        bot.edit_message_text(
            text,
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=markup
        )
    else:
        bot.send_message(
            chat_id,
            text,
            reply_markup=markup
        )

@bot.message_handler(func=lambda message: any(
    message.text == get_button_text(get_user_language(message.from_user.id), "purchase_plan") for lang in BUTTON_TRANSLATIONS
))
def purchase_plan(message):
    show_plans(message.chat.id, message.from_user.id)

@bot.callback_query_handler(func=lambda call: call.data == "back_to_plans")
def back_to_plans(call):
    try:
        bot.answer_callback_query(call.id)
        show_plans(call.message.chat.id, call.from_user.id, call.message.message_id)
    except Exception as e:
        print(f"Error in back_to_plans: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('purchase:'))
def handle_purchase_selection(call):
    try:
        bot.answer_callback_query(call.id)
        user_id = call.from_user.id
        language = get_user_language(user_id)
        plan_gb = call.data.split(':')[1]
        plans = load_plans()
        if plan_gb in plans:
            plan = plans[plan_gb]
            if plan.get('target', 'both') == 'reseller':
                bot.answer_callback_query(call.id, text='This plan is for resellers only.')
                return
            unlimited_text = get_button_text(language, "yes" if plan.get("unlimited") else "no")
            price = float(plan['price'])
            exchange_rate = get_exchange_rate()
            price_in_tomans = price * exchange_rate
            load_dotenv(TELEGRAM_ENV_PATH, override=True)
            crypto_configured = all(os.getenv(key) for key in ['CRYPTO_MERCHANT_ID', 'CRYPTO_API_KEY'])
            card_to_card_configured = get_card_number_for_receipt_type(RECEIPT_TYPE_REGULAR)
            message = get_message_text(language, "plan_details")
            message += get_message_text(language, "data").format(plan_gb=plan_gb)
            message += get_message_text(language, "duration").format(days=plan['days'])
            message += get_message_text(language, "unlimited").format(unlimited_text=unlimited_text)
            message += get_message_text(language, "price").format(price=format_usd_amount(price))
            message += get_message_text(language, "exchange_rate").format(exchange_rate=format_toman_amount(exchange_rate))
            message += get_message_text(language, "toman_price").format(toman_price=format_toman_amount(price_in_tomans))
            message += get_message_text(language, "purchase_connection_warning")
            message += get_message_text(language, "select_payment_method")

            # Check configured payment methods
            
            # Always show card-to-card if configured
            show_card_to_card = bool(card_to_card_configured)
            
            markup = types.InlineKeyboardMarkup(row_width=1)
            methods_count = 0
            if crypto_configured:
                markup.add(types.InlineKeyboardButton(get_crypto_discount_button_text(language), callback_data=f"payment_method:crypto:{plan_gb}"))
                methods_count += 1
            if show_card_to_card:
                markup.add(types.InlineKeyboardButton(get_button_text(language, "card_to_card"), callback_data=f"payment_method:card_to_card:{plan_gb}"))
                methods_count += 1
            
            if methods_count == 0:
                 bot.answer_callback_query(call.id, text=get_message_text(language, "no_payment_methods"))
                 return

            markup.add(types.InlineKeyboardButton(get_button_text(language, "back"), callback_data="back_to_plans")) 

            bot.edit_message_text(
                message,
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=markup
            )
        else:
            bot.answer_callback_query(call.id, text=get_message_text(language, "plan_not_found"))
    except Exception as e:
        user_id = call.from_user.id
        language = get_user_language(user_id)
        bot.answer_callback_query(call.id, text=get_message_text(language, "error_occurred").format(error=str(e)))

@bot.callback_query_handler(func=lambda call: call.data == "cancel_purchase")
def handle_cancel_purchase(call):
    user_id = call.from_user.id
    language = get_user_language(user_id)
    bot.answer_callback_query(call.id)
    bot.delete_message(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id
    )
    # New: Clear user state if it exists (prevents lingering receipt waiting mode)
    if user_id in user_data:
        del user_data[user_id]
    bot.send_message(
        chat_id=call.message.chat.id,
        text=get_message_text(language, "purchase_canceled")
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('payment_method:'))
def handle_payment_method_selection(call, data=None):
    try:
        user_id = call.from_user.id
        language = get_user_language(user_id)
        callback_data = data if data else call.data
        _, method, plan_gb = callback_data.split(':')
        if method == 'crypto':
            handle_crypto_payment(call, plan_gb)
        elif method == 'card_to_card':
            load_dotenv(TELEGRAM_ENV_PATH, override=True)
            card_to_card_mode = os.getenv('CARD_TO_CARD_MODE', 'on')
            if card_to_card_mode == 'previous_customers':
                try:
                    user_payments = get_user_payments(user_id)
                    has_completed = any(
                        p.get('status') == 'completed' for p in user_payments.values()
                    )
                    if not has_completed:
                        bot.answer_callback_query(call.id, text=get_message_text(language, "card_to_card_second_purchase"), show_alert=False)
                        return
                except Exception as e:
                    logging.getLogger('dijiq.payments').warning(
                        f"Failed to determine previous customer status for user {user_id}: {e}"
                    )
            handle_card_to_card_payment(call, plan_gb)
        else:
            bot.answer_callback_query(call.id, text=get_message_text(language, "invalid_payment_method"))
    except Exception as e:
        user_id = call.from_user.id
        language = get_user_language(user_id)
        bot.answer_callback_query(call.id, text=get_message_text(language, "error_occurred").format(error=str(e)))

def handle_crypto_payment(call, plan_gb):
    try:
        user_id = call.from_user.id
        language = get_user_language(user_id)
        plans = load_plans()
        if plan_gb in plans:
            plan = plans[plan_gb]
            if plan.get('target', 'both') == 'reseller':
                bot.answer_callback_query(call.id, text='This plan is for resellers only.')
                return
            discount_metadata = build_crypto_discount_metadata(plan['price'])
            discounted_price = discount_metadata['price']
            payment_handler = CryptoPayment()
            payment_response = payment_handler.create_payment(
                discounted_price, plan_gb, user_id
            )
            if "error" in payment_response:
                bot.edit_message_text(
                    get_message_text(language, "error_creating_payment").format(error=payment_response['error']),
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id
                )
                return
            payment_data = payment_response.get('result', {})
            payment_id = payment_data.get('uuid')
            payment_url = payment_data.get('url')
            gateway_order_id = payment_data.get('order_id')
            if not payment_id or not payment_url:
                bot.edit_message_text(
                    get_message_text(language, "invalid_payment_response"),
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id
                )
                return
            payment_record = {
                'user_id': user_id,
                'plan_gb': plan_gb,
                'days': plan['days'],
                'unlimited': plan.get('unlimited', False),
                'payment_id': payment_id,
                'order_id': gateway_order_id,
                'status': 'pending',
                'payment_method': 'Crypto',
                **discount_metadata,
            }
            add_payment_record(payment_id, payment_record)
            qr = qrcode.make(payment_url)
            bio = io.BytesIO()
            qr.save(bio, 'PNG')
            bio.seek(0)
            payment_message = get_message_text(language, "payment_instructions").format(price=format_usd_amount(discounted_price), payment_url=payment_url, payment_id=payment_id)
            payment_message += "\n\n" + build_crypto_discount_display(language, discount_metadata)['summary']
            payment_message += get_message_text(language, "purchase_connection_warning")
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton(get_button_text(language, "payment_link"), url=payment_url),
                types.InlineKeyboardButton(get_button_text(language, "check_status"), callback_data=f"check_payment:{payment_id}")
            )
            bot.delete_message(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id
            )
            bot.send_photo(
                call.message.chat.id,
                photo=bio,
                caption=payment_message,
                reply_markup=markup,
                parse_mode="Markdown"
            )
        else:
            bot.answer_callback_query(call.id, text=get_message_text(language, "plan_not_found"))
    except Exception as e:
        user_id = call.from_user.id
        language = get_user_language(user_id)
        bot.answer_callback_query(call.id, text=get_message_text(language, "error_processing_payment").format(error=str(e)))

def handle_card_to_card_payment(call, plan_gb):
    try:
        user_id = call.from_user.id
        language = get_user_language(user_id)
        load_dotenv(TELEGRAM_ENV_PATH, override=True)
        receipt_type = RECEIPT_TYPE_REGULAR
        card_number = get_card_number_for_receipt_type(receipt_type)
        exchange_rate = get_exchange_rate()
        if not card_number:
            bot.edit_message_text(
                get_message_text(language, "card_to_card_not_configured"),
                chat_id=call.message.chat.id,
                message_id=call.message.message_id
            )
            return
        plans = load_plans()
        plan = plans[plan_gb]
        price = plan['price']
        # Convert price to tomans using the exchange rate
        price_in_tomans = float(price) * exchange_rate
        message = get_message_text(language, "card_to_card_payment").format(
            price=format_toman_amount(price_in_tomans),
            exchange_rate=format_toman_amount(exchange_rate),
            card_number=card_number
        )
        message += get_message_text(language, "purchase_connection_warning")
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(get_button_text(language, "cancel"), callback_data="cancel_purchase"))
        bot.edit_message_text(
            message,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="Markdown",
            reply_markup=markup
        )
        # New: Set user state instead of registering next_step_handler
        user_data[user_id] = {
            'state': 'waiting_receipt',
            'plan_gb': plan_gb,
            'price': price,
            'converted_amount': price_in_tomans,
            'converted_currency': 'Tomans',
            'exchange_rate': exchange_rate,
            'receipt_type': receipt_type,
            'receipt_prompt_message_id': call.message.message_id,
        }
    except Exception as e:
        user_id = call.from_user.id
        language = get_user_language(user_id)
        bot.answer_callback_query(call.id, text=get_message_text(language, "error_occurred").format(error=str(e)))

# Modified: Remove photo check and re-registration; assume called only on photos
def process_receipt_photo(message, plan_gb, price):
    try:
        user_id = message.from_user.id
        language = get_user_language(user_id)
        receipt_prompt_message_id = None
        converted_amount = None
        converted_currency = None
        exchange_rate = None
        receipt_type = RECEIPT_TYPE_SETTLEMENT if plan_gb == 'Settlement' else RECEIPT_TYPE_REGULAR
        if user_id in user_data:
            receipt_prompt_message_id = user_data[user_id].get('receipt_prompt_message_id')
            converted_amount = user_data[user_id].get('converted_amount')
            converted_currency = user_data[user_id].get('converted_currency')
            exchange_rate = user_data[user_id].get('exchange_rate')
            receipt_type = user_data[user_id].get('receipt_type', receipt_type)
            settlement_amount = user_data[user_id].get('settlement_amount')
        else:
            settlement_amount = None
        file_id = message.photo[-1].file_id
        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        payment_id = str(uuid.uuid4())
        uploads_dir = 'uploads'
        if not os.path.exists(uploads_dir):
            os.makedirs(uploads_dir)
        photo_path = os.path.join(uploads_dir, f"{payment_id}.jpg")
        with open(photo_path, 'wb') as new_file:
            new_file.write(downloaded_file)
        
        if plan_gb == 'Settlement':
             routed_to_checker = should_route_to_receipt_checker(RECEIPT_TYPE_SETTLEMENT)
             checker_id = get_receipt_checker_user_id() if routed_to_checker else None
             payment_record = {
                'user_id': user_id,
                'plan_gb': plan_gb,
                'price': price,
                'days': 0,
                'payment_id': payment_id,
                'status': 'pending_approval',
                'receipt_path': photo_path,
                'type': 'settlement',
                'receipt_type': RECEIPT_TYPE_SETTLEMENT,
                'routed_to_checker': routed_to_checker,
                'receipt_checker_user_id': checker_id,
                'payment_method': 'Card to Card',
                'settlement_amount': settlement_amount if settlement_amount is not None else price,
            }
        else:
            plans = load_plans()
            plan = plans[plan_gb]
            routed_to_checker = should_route_to_receipt_checker(RECEIPT_TYPE_REGULAR)
            checker_id = get_receipt_checker_user_id() if routed_to_checker else None
            payment_record = {
                'user_id': user_id,
                'plan_gb': plan_gb,
                'price': price,
                'days': plan['days'],
                'unlimited': plan.get('unlimited', False),
                'payment_id': payment_id,
                'status': 'pending_approval',
                'receipt_path': photo_path,
                'receipt_type': RECEIPT_TYPE_REGULAR,
                'routed_to_checker': routed_to_checker,
                'receipt_checker_user_id': checker_id,
                'payment_method': 'Card to Card'
            }
        if converted_amount is not None:
            payment_record['converted_amount'] = converted_amount
            payment_record['converted_currency'] = converted_currency or 'Tomans'
            payment_record['exchange_rate'] = exchange_rate
            
        add_payment_record(payment_id, payment_record)
        notification_message = _format_pending_receipt_caption(payment_id, payment_record, message.from_user.username)
        receipt_message_refs = []
        for admin_id in ADMIN_USER_IDS:
            try:
                sent_message = _send_receipt_confirmation(admin_id, payment_id, payment_record, notification_message)
                receipt_message_refs.append({
                    "chat_id": sent_message.chat.id,
                    "message_id": sent_message.message_id,
                    "recipient_id": admin_id,
                    "recipient_role": "admin",
                    "content_type": "photo" if getattr(sent_message, "photo", None) else "text",
                })
            except Exception as e:
                print(f"Failed to send notification to admin {admin_id}: {str(e)}")
        if checker_id and checker_id not in ADMIN_USER_IDS:
            try:
                sent_message = _send_receipt_confirmation(checker_id, payment_id, payment_record, notification_message)
                receipt_message_refs.append({
                    "chat_id": sent_message.chat.id,
                    "message_id": sent_message.message_id,
                    "recipient_id": checker_id,
                    "recipient_role": "checker",
                    "content_type": "photo" if getattr(sent_message, "photo", None) else "text",
                })
            except Exception as e:
                print(f"Failed to send notification to receipt checker {checker_id}: {str(e)}")
        _save_receipt_message_refs(payment_id, receipt_message_refs)
        if receipt_prompt_message_id:
            try:
                bot.edit_message_reply_markup(
                    chat_id=message.chat.id,
                    message_id=receipt_prompt_message_id,
                    reply_markup=None
                )
            except Exception:
                pass
        bot.reply_to(message, get_message_text(language, "receipt_submitted"))
        # New: Clear state after processing
        if user_id in user_data:
            del user_data[user_id]
    except Exception as e:
        user_id = message.from_user.id
        language = get_user_language(user_id)
        bot.reply_to(message, get_message_text(language, "error_occurred").format(error=str(e)))

# New: State-aware handler for photos
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    user_id = message.from_user.id
    if user_id in user_data and user_data[user_id]['state'] == 'waiting_receipt':
        plan_gb = user_data[user_id]['plan_gb']
        price = user_data[user_id]['price']
        process_receipt_photo(message, plan_gb, price)
    # Optional: Handle non-state photos if needed (e.g., ignore or reply)

# New: Handler for text messages while waiting for receipt (reminds without looping)
@bot.message_handler(func=lambda message: message.from_user.id in user_data and user_data[message.from_user.id]['state'] == 'waiting_receipt')
def handle_text_while_waiting(message):
    language = get_user_language(message.from_user.id)
    cancel_callback = user_data[message.from_user.id].get('cancel_callback', 'cancel_purchase')
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(get_button_text(language, "cancel"), callback_data=cancel_callback))
    bot.reply_to(message, get_message_text(language, "upload_receipt"), reply_markup=markup)


@bot.message_handler(func=lambda message: message.text == '✅ Confirmations' and _is_confirmation_viewer(message.from_user.id))
def show_pending_confirmations(message):
    user_id = message.from_user.id
    payments = load_payments()
    pending_items = []
    user_is_admin = is_admin(user_id)
    for payment_id, record in payments.items():
        if record.get('status') != 'pending_approval':
            continue
        if not can_review_receipt(user_id, record, is_admin_user=user_is_admin):
            continue
        pending_items.append((payment_id, record))
    pending_withdrawals = get_pending_withdrawal_requests() if user_is_admin else []

    if not pending_items and not pending_withdrawals:
        if not user_is_admin and is_receipt_checker(user_id):
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(types.InlineKeyboardButton("📊 My Stats", callback_data="checker_stats:my"))
            bot.reply_to(message, "No pending receipt confirmations.", reply_markup=markup)
        else:
            bot.reply_to(message, "No pending confirmations.", reply_markup=create_main_markup(is_admin=user_is_admin, user_id=user_id))
        return

    total_pending = len(pending_items) + len(pending_withdrawals)
    bot.reply_to(message, f"Pending confirmations: {total_pending}")
    for payment_id, record in pending_items:
        try:
            sent_message = _send_receipt_confirmation(message.chat.id, payment_id, record)
            refs = list(record.get('receipt_message_refs') or [])
            refs.append({
                "chat_id": sent_message.chat.id,
                "message_id": sent_message.message_id,
                "recipient_id": user_id,
                "recipient_role": "admin" if user_is_admin else "checker",
                "content_type": "photo" if getattr(sent_message, "photo", None) else "text",
            })
            _save_receipt_message_refs(payment_id, refs)
        except Exception as e:
            bot.send_message(message.chat.id, f"Failed to show receipt {payment_id}: {str(e)}")
    for withdrawal_request in pending_withdrawals:
        try:
            _send_referral_withdrawal_confirmation(message.chat.id, withdrawal_request)
        except Exception as e:
            bot.send_message(message.chat.id, f"Failed to show withdrawal {withdrawal_request.get('id')}: {str(e)}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_approval:'))
def handle_admin_approval(call):
    try:
        user_id = call.from_user.id
        language = get_user_language(user_id)
        user_is_admin = is_admin(user_id)
        _, action, payment_id = call.data.split(':')
        payment_record = get_payment_record(payment_id)
        if not payment_record:
            bot.answer_callback_query(call.id, text=get_message_text(language, "payment_record_not_found"))
            return
        if not can_review_receipt(user_id, payment_record, is_admin_user=user_is_admin):
            bot.answer_callback_query(call.id, text=get_message_text(language, "not_authorized"))
            return
        reviewer_role = "admin" if user_is_admin else "checker"
        if payment_record['status'] != 'pending_approval':
            bot.answer_callback_query(call.id, text=get_message_text(language, "payment_already_processed").format(status=payment_record['status']))
            return
        if action == 'approve':
            _record_review_audit(payment_id, call, action, reviewer_role)
            _record_checker_share_audit(payment_id, payment_record)
            if payment_record.get('type') == 'settlement' or payment_record.get('plan_gb') == 'Settlement':
                 from utils.reseller import apply_reseller_payment
                 apply_reseller_payment(payment_record['user_id'], _settlement_credit_amount(payment_record))
                 update_payment_status(payment_id, 'completed')
                 
                 user_to_notify = payment_record['user_id']
                 user_language = get_user_language(user_to_notify)
                 
                 telegram_username = None
                 try:
                    chat = bot.get_chat(user_to_notify)
                    telegram_username = chat.username
                 except:
                    pass

                 send_admin_payment_notification(
                    user_to_notify, 
                    "Settlement", 
                    "Settlement", 
                    payment_record['price'], 
                    payment_id, 
                    payment_record.get('payment_method', 'Card to Card'), 
                    telegram_username=telegram_username,
                    converted_amount=payment_record.get('converted_amount'),
                    converted_currency=payment_record.get('converted_currency'),
                    exchange_rate=payment_record.get('exchange_rate')
                 )

                 bot.send_message(user_to_notify, get_message_text(user_language, "settlement_payment_approved"))
                 _update_receipt_message_refs(
                    payment_id,
                    payment_record,
                    f"✅ Settlement Payment {payment_id} approved by {call.from_user.first_name}."
                )
                 return

            user_to_notify = payment_record['user_id']
            user_language = get_user_language(user_to_notify)
            plan_gb = payment_record['plan_gb']
            days = payment_record['days']
            
            unlimited = payment_record.get('unlimited')
            if unlimited is None:
                 plans = load_plans()
                 if plan_gb in plans:
                     unlimited = plans[plan_gb].get('unlimited', False)
                 else:
                     unlimited = False
            
            api_client = APIClient()
            username, result, api_client = create_sale_user_with_note(
                api_client,
                user_to_notify,
                plan_gb,
                days,
                unlimited,
            )
            if result:
                update_payment_record_fields(payment_id, {"username": username, "server_id": api_client.server_id})
                update_payment_status(payment_id, 'completed')
                add_referral_reward(payment_record['user_id'], payment_record['price'])
                
                telegram_username = None
                try:
                    chat = bot.get_chat(user_to_notify)
                    telegram_username = chat.username
                except:
                    pass
                    
                send_admin_payment_notification(
                    user_to_notify, 
                    username, 
                    plan_gb, 
                    payment_record['price'], 
                    payment_id, 
                    payment_record.get('payment_method', 'Card to Card'), 
                    telegram_username=telegram_username,
                    converted_amount=payment_record.get('converted_amount'),
                    converted_currency=payment_record.get('converted_currency'),
                    exchange_rate=payment_record.get('exchange_rate')
                )

                user_uri_data = api_client.get_user_uri(username)
                if user_uri_data and 'normal_sub' in user_uri_data:
                    sub_url = user_uri_data['normal_sub']
                    ipv4_url = user_uri_data.get('ipv4', '')
                    ipv4_info = f"IPv4 URL: `{ipv4_url}`\n\n" if ipv4_url else ""

                    qr = qrcode.make(ipv4_url or sub_url)
                    bio = io.BytesIO()
                    qr.save(bio, 'PNG')
                    bio.seek(0)
                    success_message = get_message_text(user_language, "payment_approved").format(plan_gb=plan_gb, days=days, username=username, sub_url=sub_url, ipv4_info=ipv4_info)
                    bot.send_photo(
                        user_to_notify,
                        photo=bio,
                        caption=success_message,
                        parse_mode="Markdown"
                    )
                else:
                    bot.send_message(user_to_notify, get_message_text(user_language, "payment_approved_no_url"))
                _update_receipt_message_refs(
                    payment_id,
                    payment_record,
                    f"✅ Payment {payment_id} approved by {call.from_user.first_name}."
                )
            else:
                bot.answer_callback_query(call.id, text=get_message_text(language, "failed_to_create_user"))
                bot.send_message(user_to_notify, get_message_text(user_language, "payment_approved_user_error"))
        elif action == 'reject':
            _record_review_audit(payment_id, call, action, reviewer_role)
            update_payment_status(payment_id, 'rejected')
            user_to_notify = payment_record['user_id']
            user_language = get_user_language(user_to_notify)
            current_caption = call.message.caption or ""
            
            if payment_record.get('type') == 'settlement' or payment_record.get('plan_gb') == 'Settlement':
                 bot.send_message(user_to_notify, get_message_text(user_language, "settlement_payment_rejected"))
                 rejection_caption = f"{current_caption}\n\n❌ Settlement Payment {payment_id} rejected by {call.from_user.first_name}."
            else:
                 bot.send_message(user_to_notify, get_message_text(user_language, "payment_rejected"))
                 rejection_caption = f"{current_caption}\n\n❌ Payment {payment_id} rejected by {call.from_user.first_name}."
                 
            _update_receipt_message_refs(payment_id, payment_record, rejection_caption)
    except Exception as e:
        user_id = call.from_user.id
        language = get_user_language(user_id)
        bot.answer_callback_query(call.id, text=get_message_text(language, "error_occurred").format(error=str(e)))

@bot.callback_query_handler(func=lambda call: call.data.startswith('check_payment:'))
def handle_check_payment(call):
    user_id = call.from_user.id
    language = get_user_language(user_id)
    payment_id = call.data.split(':')[1]
    payment_record = get_payment_record(payment_id)
    if not payment_record:
        bot.answer_callback_query(call.id, text=get_message_text(language, "payment_record_not_found"))
        return
    if payment_record.get('status') == 'completed':
        bot.answer_callback_query(call.id, text=get_message_text(language, "payment_already_processed").format(status='completed'))
        return
    if payment_record.get('status') == 'processing':
        bot.answer_callback_query(call.id, text=get_message_text(language, "payment_already_processed").format(status='processing'))
        return
    payment_handler = CryptoPayment()
    payment_status_response = payment_handler.check_payment_status(payment_id)
    if "error" in payment_status_response:
        bot.answer_callback_query(call.id, text=get_message_text(language, "error_checking_payment").format(error=payment_status_response['error']))
        return
    payment_status_data = payment_status_response.get('result', {})
    status = payment_status_data.get('status') or payment_status_data.get('payment_status') or payment_status_data.get('paymentStatus')
    if status and status.lower() == 'paid':
        if not claim_payment_for_processing(payment_id, allowed_statuses={'pending'}):
            latest_record = get_payment_record(payment_id) or {}
            latest_status = latest_record.get('status', 'unknown')
            bot.answer_callback_query(call.id, text=get_message_text(language, "payment_already_processed").format(status=latest_status))
            return

        payment_record = get_payment_record(payment_id) or payment_record
        user_id = payment_record.get('user_id')
        plan_gb = payment_record.get('plan_gb')
        
        if payment_record.get('type') == 'settlement' or plan_gb == 'Settlement':
             from utils.reseller import apply_reseller_payment
             apply_reseller_payment(user_id, _settlement_credit_amount(payment_record))
             update_payment_status(payment_id, 'completed')
             bot.send_message(
                call.message.chat.id,
                get_message_text(language, "debt_cleared"),
                parse_mode="Markdown"
            )
             return

        days = payment_record.get('days')
        price = payment_record.get('price')
        
        unlimited = payment_record.get('unlimited')
        if unlimited is None:
                plans = load_plans()
                if plan_gb in plans:
                    unlimited = plans[plan_gb].get('unlimited', False)
                else:
                    unlimited = False
        
        api_client = APIClient()
        username, result, api_client = create_sale_user_with_note(
            api_client,
            user_id,
            plan_gb,
            days,
            unlimited,
        )
        if result:
            update_payment_record_fields(payment_id, {"username": username, "server_id": api_client.server_id})
            send_admin_payment_notification(user_id, username, plan_gb, price, payment_id, "Crypto", telegram_username=call.from_user.username)
            add_referral_reward(user_id, price)
            user_uri_data = api_client.get_user_uri(username)
            update_payment_status(payment_id, 'completed')
            if user_uri_data and 'normal_sub' in user_uri_data:
                sub_url = user_uri_data['normal_sub']
                ipv4_url = user_uri_data.get('ipv4', '')
                ipv4_info = f"IPv4 URL: `{ipv4_url}`\n\n" if ipv4_url else ""

                qr = qrcode.make(ipv4_url or sub_url)
                bio = io.BytesIO()
                qr.save(bio, 'PNG')
                bio.seek(0)
                success_message = get_message_text(language, "payment_completed").format(plan_gb=plan_gb, username=username, sub_url=sub_url, ipv4_info=ipv4_info)
                bot.send_photo(
                    call.message.chat.id,
                    photo=bio,
                    caption=success_message,
                    parse_mode="Markdown"
                )
            else:
                bot.send_message(
                    call.message.chat.id,
                    get_message_text(language, "payment_completed_no_url"),
                    parse_mode="Markdown"
                )
        else:
            bot.send_message(
                call.message.chat.id,
                get_message_text(language, "payment_completed_user_error"),
                parse_mode="Markdown"
            )
    elif status and status.lower() == 'pending':
        bot.answer_callback_query(call.id, text=get_message_text(language, "payment_pending"))
    else:
        bot.answer_callback_query(call.id, text=get_message_text(language, "payment_status").format(status=status or 'unknown'))
    try:
        import logging
        logging.getLogger('dijiq.payments').debug(f"Check payment response for {payment_id}: {payment_status_response}")
    except Exception:
        pass

def process_payment_webhook(request_data):
    try:
        status = request_data.get('status') or request_data.get('payment_status') or request_data.get('paymentStatus')
        payments = load_payments()
        record_key = None
        if request_data.get('uuid'):
            record_key = request_data.get('uuid')
        elif request_data.get('order_id'):
            incoming_order = request_data.get('order_id')
            for k, v in payments.items():
                if v.get('order_id') == incoming_order or v.get('payment_id') == incoming_order:
                    record_key = k
                    break
        if not record_key:
            return False
        if status and status.lower() == 'paid':
            payment_record = get_payment_record(record_key)
            if payment_record and payment_record.get('status') == 'pending':
                user_id = payment_record.get('user_id')
                user_language = get_user_language(user_id)
                plan_gb = payment_record.get('plan_gb')
                
                if payment_record.get('type') == 'settlement' or plan_gb == 'Settlement':
                     from utils.reseller import apply_reseller_payment
                     apply_reseller_payment(user_id, _settlement_credit_amount(payment_record))
                     update_payment_status(record_key, 'completed')
                     bot.send_message(
                        user_id,
                        get_message_text(user_language, "debt_cleared"),
                        parse_mode="Markdown"
                     )
                     return True

                days = payment_record.get('days')
                price = payment_record.get('price')
                
                unlimited = payment_record.get('unlimited')
                if unlimited is None:
                    plans = load_plans()
                    if plan_gb in plans:
                        unlimited = plans[plan_gb].get('unlimited', False)
                    else:
                        unlimited = False
                
                api_client = APIClient()
                username, result, api_client = create_sale_user_with_note(
                    api_client,
                    user_id,
                    plan_gb,
                    days,
                    unlimited,
                )
                if result:
                    update_payment_record_fields(record_key, {"username": username, "server_id": api_client.server_id})
                    payment_method = "Crypto" if "order_id" in payment_record else "Card to Card"
                    telegram_username = None
                    try:
                        chat = bot.get_chat(user_id)
                        telegram_username = chat.username
                    except:
                        pass
                    send_admin_payment_notification(user_id, username, plan_gb, price, record_key, payment_method, telegram_username=telegram_username)
                    add_referral_reward(user_id, price)
                    
                    user_uri_data = api_client.get_user_uri(username)
                    sub_url = user_uri_data.get('normal_sub') if user_uri_data else None
                    ipv4_url = user_uri_data.get('ipv4', '') if user_uri_data else ''
                    ipv4_info = f"IPv4 URL: `{ipv4_url}`\n\n" if ipv4_url else ""
                    
                    update_payment_status(record_key, 'completed')
                    success_message = get_message_text(user_language, "payment_completed").format(plan_gb=plan_gb, username=username, sub_url=sub_url, ipv4_info=ipv4_info)
                    bot.send_message(
                        user_id,
                        success_message,
                        parse_mode="Markdown"
                    )
                    if sub_url:
                        qr = qrcode.make(ipv4_url or sub_url)
                        bio = io.BytesIO()
                        qr.save(bio, 'PNG')
                        bio.seek(0)
                        bot.send_photo(
                            user_id,
                            photo=bio,
                            caption=get_message_text(user_language, "scan_qr_code")
                        )
                    return True
                else:
                    bot.send_message(
                        user_id,
                        get_message_text(user_language, "payment_completed_user_error"),
                        parse_mode="Markdown"
                    )
                    return False
            return False
        return False
    except Exception as e:
        print(f"Error processing webhook: {str(e)}")
        return False

def check_pending_payments():
    try:
        payments = load_payments()
        payment_handler = CryptoPayment()
        
        for payment_id, record in payments.items():
            if record.get('status') == 'pending':
                # Check if payment is not too old (e.g., > 24 hours) — mark as expired
                created_at_str = record.get('created_at')
                if created_at_str:
                    try:
                        created_at = datetime.datetime.strptime(created_at_str, '%Y-%m-%d %H:%M:%S')
                        if datetime.datetime.now() - created_at > datetime.timedelta(hours=24):
                            update_payment_status(payment_id, 'expired')
                            continue
                    except ValueError:
                        pass

                # Check status
                try:
                    response = payment_handler.check_payment_status(payment_id)
                    if "error" in response:
                        continue
                        
                    result = response.get('result', {})
                    status = result.get('status') or result.get('payment_status') or result.get('paymentStatus')
                    
                    if status and status.lower() == 'paid':
                        # Process payment
                        user_id = record.get('user_id')
                        plan_gb = record.get('plan_gb')
                        
                        if record.get('type') == 'settlement' or plan_gb == 'Settlement':
                             from utils.reseller import apply_reseller_payment
                             apply_reseller_payment(user_id, _settlement_credit_amount(record))
                             update_payment_status(payment_id, 'completed')
                             try:
                                user_language = get_user_language(user_id)
                                bot.send_message(
                                    user_id,
                                    get_message_text(user_language, "debt_cleared"),
                                    parse_mode="Markdown"
                                )
                             except:
                                 pass
                             continue

                        days = record.get('days')
                        price = record.get('price')
                        
                        unlimited = record.get('unlimited')
                        if unlimited is None:
                            plans = load_plans()
                            if plan_gb in plans:
                                unlimited = plans[plan_gb].get('unlimited', False)
                            else:
                                unlimited = False
                        
                        api_client = APIClient()
                        username, add_result, api_client = create_sale_user_with_note(
                            api_client,
                            user_id,
                            plan_gb,
                            days,
                            unlimited,
                        )
                        
                        if add_result:
                            update_payment_record_fields(payment_id, {"username": username, "server_id": api_client.server_id})
                            telegram_username = None
                            try:
                                chat = bot.get_chat(user_id)
                                telegram_username = chat.username
                            except:
                                pass
                            send_admin_payment_notification(user_id, username, plan_gb, price, payment_id, "Crypto", telegram_username=telegram_username)
                            add_referral_reward(user_id, price)
                            user_uri_data = api_client.get_user_uri(username)
                            
                            update_payment_status(payment_id, 'completed')
                            
                            user_language = get_user_language(user_id)
                            
                            if user_uri_data and 'normal_sub' in user_uri_data:
                                sub_url = user_uri_data['normal_sub']
                                ipv4_url = user_uri_data.get('ipv4', '')
                                ipv4_info = f"IPv4 URL: `{ipv4_url}`\n\n" if ipv4_url else ""

                                qr = qrcode.make(ipv4_url or sub_url)
                                bio = io.BytesIO()
                                qr.save(bio, 'PNG')
                                bio.seek(0)
                                success_message = get_message_text(user_language, "payment_completed").format(plan_gb=plan_gb, username=username, sub_url=sub_url, ipv4_info=ipv4_info)
                                try:
                                    bot.send_photo(
                                        user_id,
                                        photo=bio,
                                        caption=success_message,
                                        parse_mode="Markdown"
                                    )
                                except Exception as e:
                                    print(f"Failed to send success message to user {user_id}: {e}")
                            else:
                                try:
                                    bot.send_message(
                                        user_id,
                                        get_message_text(user_language, "payment_completed_no_url"),
                                        parse_mode="Markdown"
                                    )
                                except Exception as e:
                                    print(f"Failed to send success message to user {user_id}: {e}")
                except Exception as e:
                    print(f"Error checking pending payment {payment_id}: {e}")

        # Also run reseller debt reminders/escalations on the same monitoring cycle.
        debt_events = evaluate_reseller_debt_policies()
        for event in debt_events:
            try:
                reseller_id = int(event['user_id'])
            except (TypeError, ValueError):
                continue

            debt = float(event.get('debt', 0.0))
            debt_state = str(event.get('debt_state', 'active'))
            debt_age_days = int(event.get('debt_age_days', 0))
            unlock_amount = float(event.get('unlock_amount', 0.0))

            if event.get('notify_user'):
                try:
                    user_language = get_user_language(reseller_id)
                    if debt_state == 'suspended':
                        user_message = get_message_text(user_language, "reseller_debt_reminder_suspended").format(
                            debt=debt,
                            debt_age_days=debt_age_days,
                            unlock_amount=unlock_amount
                        )
                    else:
                        user_message = get_message_text(user_language, "reseller_debt_reminder_warning").format(
                            debt=debt,
                            debt_age_days=debt_age_days,
                            suspend_threshold=DEBT_SUSPEND_THRESHOLD
                        )

                    markup = types.InlineKeyboardMarkup()
                    markup.add(
                        types.InlineKeyboardButton(
                            get_button_text(user_language, "settle_debt"),
                            callback_data=f"reseller:settle:{debt:.2f}"
                        )
                    )
                    bot.send_message(reseller_id, user_message, reply_markup=markup)
                except Exception:
                    pass

            if event.get('notify_admin'):
                for admin_id in ADMIN_USER_IDS:
                    try:
                        admin_language = get_user_language(admin_id)
                        state_text = get_message_text(admin_language, _debt_state_label_key(debt_state))
                        admin_message = get_message_text(admin_language, "reseller_debt_threshold_crossed_admin").format(
                            reseller_id=reseller_id,
                            debt_state=state_text,
                            debt=debt,
                            debt_age_days=debt_age_days,
                            warning_threshold=DEBT_WARNING_THRESHOLD,
                            suspend_threshold=DEBT_SUSPEND_THRESHOLD
                        )
                        bot.send_message(admin_id, admin_message)
                    except Exception:
                        pass

        try:
            from utils.expired_cleanup import run_expired_user_cleanup
            run_expired_user_cleanup(grace_hours=24)
        except Exception as e:
            print(f"Error in expired user cleanup: {e}")

    except Exception as e:
        print(f"Error in check_pending_payments: {e}")
