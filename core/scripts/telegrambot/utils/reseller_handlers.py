import telebot
from telebot import types
import uuid
import qrcode
import io
import os
import re
import logging
from dotenv import load_dotenv

from utils.command import bot, ADMIN_USER_IDS, is_admin
from utils.language import get_user_language
from utils.translations import get_message_text, get_button_text, BUTTON_TRANSLATIONS
from utils.reseller import (
    get_reseller_data, update_reseller_status, add_reseller_debt,
    get_all_resellers, set_reseller_debt, DEBT_WARNING_THRESHOLD,
    SUSPENDED_REASON_UNBAN_GRACE, get_reseller_unlock_amount,
    get_banned_reseller_cleanup_candidates, cleanup_banned_reseller_users,
    can_reseller_add_debt, get_reseller_total_paid, get_reseller_trust_limit,
    apply_reseller_payment, validate_reseller_manual_payment_amount,
)
from utils.edit_plans import load_plans
from utils.api_client import APIClient, MultiServerAPI
from utils.payments import CryptoPayment
from utils.payment_records import add_payment_record
from utils.currency_format import format_toman_amount, format_usd_amount
from utils.purchase_plan import (
    build_crypto_discount_display,
    build_crypto_discount_metadata,
    get_crypto_discount_button_text,
    get_exchange_rate,
    user_data,
)
from utils.receipt_checker import RECEIPT_TYPE_SETTLEMENT, get_card_number_for_receipt_type
from utils.username_utils import (
    allocate_username,
    build_user_note,
    extract_existing_usernames,
    format_username_timestamp,
)

TELEGRAM_ENV_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.env'))


def _get_approved_reseller_data(user_id):
    reseller_data = get_reseller_data(user_id)
    if not reseller_data or reseller_data.get('status') != 'approved':
        return None
    return reseller_data


def _get_active_reseller_data(user_id):
    reseller_data = get_reseller_data(user_id)
    if not reseller_data or reseller_data.get('status') not in ('approved', 'suspended'):
        return None
    return reseller_data


def _is_reseller_suspended(reseller_data):
    """Check if reseller is suspended (either by status or debt state)."""
    if not reseller_data:
        return False
    # Check if status is explicitly suspended
    if reseller_data.get('status') == 'suspended':
        return True
    # Check if debt state is suspended and has debt
    return reseller_data.get('debt_state') == 'suspended' and float(reseller_data.get('debt', 0.0)) > 0


def _debt_state_label(debt_state):
    if debt_state == 'suspended':
        return "debt_state_suspended"
    if debt_state == 'warning':
        return "debt_state_warning"
    return "debt_state_active"


def _has_active_purchased_config(user_id):
    multi_api = MultiServerAPI()

    paid_patterns = (
        re.compile(rf"^s{user_id}[a-z]*$", re.IGNORECASE),  # current purchased usernames
        re.compile(rf"^{user_id}t"),      # legacy purchased usernames
        re.compile(rf"^sell{user_id}t"),  # current purchased usernames
    )

    def _is_active_paid(username, config_data):
        if not username or not any(pattern.match(username) for pattern in paid_patterns):
            return False
        if bool(config_data.get('blocked', False)):
            return False
        try:
            return int(config_data.get('expiration_days', 0) or 0) > 0
        except (TypeError, ValueError):
            return False

    for _, username, config_data in multi_api.iter_all_users():
        if _is_active_paid(username, config_data or {}):
            return True

    return False


def _create_reseller_username(api_client, user_id):
    if isinstance(api_client, set):
        return allocate_username("r", user_id, api_client)
    multi_api = MultiServerAPI()
    creation = multi_api.prepare_new_user_creation()
    usernames = creation.get("existing_usernames") or set()
    if not usernames and api_client is not None:
        usernames = extract_existing_usernames(api_client.get_users())
    return allocate_username("r", user_id, usernames)


def _create_reseller_user_with_note(api_client, user_id, gb, days, chosen_username, unlimited=False):
    multi_api = MultiServerAPI()

    def allocate(existing_usernames):
        return allocate_username("r", user_id, existing_usernames)

    def create(target_client, username):
        note_payload = build_user_note(
            username=username,
            traffic_limit=gb,
            expiration_days=days,
            unlimited=unlimited,
            note_text=chosen_username,
        )
        result = target_client.add_user(username, int(gb), int(days), unlimited=unlimited, note=note_payload)
        if result is None:
            result = target_client.add_user(username, int(gb), int(days))
            if result is not None:
                logging.getLogger("dijiq.usernames").warning(
                    "Created reseller user without note fallback. reseller_id=%s username=%s",
                    user_id,
                    username,
                )
        return result

    return multi_api.create_user_with_retry(allocate, create, fallback_client=api_client)


def _build_reseller_purchase_details(language, gb, days, price, current_debt, trust_limit):
    exchange_rate = get_exchange_rate()
    converted_price = price * exchange_rate
    projected_debt = current_debt + price
    return get_message_text(language, "reseller_purchase_details").format(
        plan_gb=gb,
        days=days,
        price=format_usd_amount(price),
        exchange_rate=format_toman_amount(exchange_rate),
        toman_price=format_toman_amount(converted_price),
        current_debt=format_usd_amount(current_debt),
        projected_debt=format_usd_amount(projected_debt),
        trust_limit=format_usd_amount(trust_limit),
    ) + get_message_text(language, "purchase_connection_warning")


def _reseller_username_prompt_markup(language):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(get_button_text(language, "cancel"), callback_data="reseller:cancel"))
    return markup


def _show_reseller_purchase_details(call, language, gb, days, price, current_debt, trust_limit):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton(get_button_text(language, "confirm"), callback_data=f"reseller:confirm_buy:{gb}"))
    markup.add(types.InlineKeyboardButton(get_button_text(language, "cancel"), callback_data="reseller:cancel"))

    bot.edit_message_text(
        _build_reseller_purchase_details(language, gb, days, price, current_debt, trust_limit),
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=markup
    )


def _show_reseller_trust_limit_block(call, language, current_debt, purchase_adds, trust_limit, available_credit):
    markup = types.InlineKeyboardMarkup(row_width=1)
    if current_debt > 0:
        markup.add(types.InlineKeyboardButton(get_button_text(language, "settle_debt"), callback_data=f"reseller:settle:{current_debt:.2f}"))
    markup.add(types.InlineKeyboardButton(get_button_text(language, "cancel"), callback_data="reseller:cancel"))
    bot.edit_message_text(
        get_message_text(language, "reseller_trust_limit_exceeded").format(
            current_debt=current_debt,
            purchase_adds=purchase_adds,
            projected_debt=current_debt + purchase_adds,
            trust_limit=trust_limit,
            available_credit=available_credit,
        ),
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=markup
    )

# Reseller Menu Handler
@bot.message_handler(func=lambda message: any(
    message.text == get_button_text(get_user_language(message.from_user.id), "reseller_panel") for lang in BUTTON_TRANSLATIONS
))
def reseller_panel(message):
    user_id = message.from_user.id
    language = get_user_language(user_id)
    reseller_data = get_reseller_data(user_id)
    
    status = reseller_data.get('status') if reseller_data else None
    
    if status in ('approved', 'suspended'):
        # Show Reseller Menu (suspended can still access panel but with restrictions)
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton(get_button_text(language, "generate_config"), callback_data="reseller:generate"),
            types.InlineKeyboardButton(get_button_text(language, "reseller_my_customers"), callback_data="reseller:my_customers:0")
        )
        markup.add(
            types.InlineKeyboardButton(get_button_text(language, "reseller_stats"), callback_data="reseller:stats"),
            types.InlineKeyboardButton(get_button_text(language, "my_debt"), callback_data="reseller:debt")
        )
        debt = float(reseller_data.get('debt', 0.0))
        debt_state_text = get_message_text(language, _debt_state_label(reseller_data.get('debt_state', 'active')))
        trust_limit = get_reseller_trust_limit(get_reseller_total_paid(reseller_data))
        intro = get_message_text(language, "reseller_intro").replace("${debt}", f"${format_usd_amount(debt)}")
        intro += "\n" + get_message_text(language, "reseller_trust_limit_line").format(trust_limit=trust_limit)
        intro += "\n" + get_message_text(language, "reseller_debt_status_line").format(debt_state=debt_state_text)
        if _is_reseller_suspended(reseller_data) or status == 'suspended':
            intro += "\n" + get_message_text(language, "reseller_suspended_intro_notice")
        bot.reply_to(message, intro, reply_markup=markup)
        
    elif status == 'pending':
        bot.reply_to(message, get_message_text(language, "reseller_status_pending"))
        
    elif status == 'rejected':
        bot.reply_to(message, get_message_text(language, "reseller_status_rejected"))
    elif status == 'banned':
        bot.reply_to(message, get_message_text(language, "reseller_access_banned"))
        
    else:
        # Not a reseller yet
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(get_button_text(language, "request_reseller"), callback_data="reseller:request"))
        bot.reply_to(message, get_message_text(language, "reseller_intro").replace("${debt}", "0") + "\n\n" + get_message_text(language, "request_reseller"), reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "reseller:request")
def handle_reseller_request(call):
    user_id = call.from_user.id
    language = get_user_language(user_id)
    reseller_data = get_reseller_data(user_id)
    current_status = reseller_data.get('status') if reseller_data else None
    telegram_username = str(call.from_user.username or "").strip().lstrip("@")

    if current_status == 'approved':
        bot.answer_callback_query(call.id, "You are already an approved reseller.")
        return
    if current_status == 'pending':
        bot.answer_callback_query(call.id, get_message_text(language, "reseller_status_pending"))
        return
    if current_status == 'banned':
        bot.answer_callback_query(call.id, get_message_text(language, "reseller_access_banned"))
        return
    if not telegram_username:
        bot.answer_callback_query(call.id, get_message_text(language, "reseller_requires_telegram_username"), show_alert=True)
        return
    if not _has_active_purchased_config(user_id):
        bot.answer_callback_query(call.id, get_message_text(language, "reseller_requires_active_paid_config"), show_alert=True)
        return
    
    # Update status to pending
    if not update_reseller_status(user_id, 'pending', telegram_username=telegram_username):
        bot.answer_callback_query(call.id, "Failed to submit request. Please try again.")
        return
    
    bot.edit_message_text(
        get_message_text(language, "reseller_request_sent"),
        chat_id=call.message.chat.id,
        message_id=call.message.message_id
    )
    
    # Notify Admins
    notification = get_message_text(language, "reseller_request_notification").format(user_id=user_id, username=telegram_username)
    
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ Approve", callback_data=f"admin_reseller:approve:{user_id}"),
        types.InlineKeyboardButton("❌ Reject", callback_data=f"admin_reseller:reject:{user_id}")
    )
    
    for admin_id in ADMIN_USER_IDS:
        try:
            bot.send_message(admin_id, notification, reply_markup=markup)
        except:
            pass

@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_reseller:"))
def handle_admin_reseller(call):
    if not is_admin(call.from_user.id):
        return
        
    action, target_user_id = call.data.split(':')[1], call.data.split(':')[2]
    target_user_id = int(target_user_id)
    target_language = get_user_language(target_user_id)
    
    if action == 'approve':
        update_reseller_status(target_user_id, 'approved')
        try:
            bot.send_message(target_user_id, get_message_text(target_language, "reseller_approved_notification"))
        except:
            pass
        bot.edit_message_text(f"✅ User {target_user_id} approved as reseller.", chat_id=call.message.chat.id, message_id=call.message.message_id)
        
    elif action == 'reject':
        update_reseller_status(target_user_id, 'rejected')
        try:
            bot.send_message(target_user_id, get_message_text(target_language, "reseller_rejected_notification"))
        except:
            pass
        bot.edit_message_text(f"❌ User {target_user_id} rejected as reseller.", chat_id=call.message.chat.id, message_id=call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data == "reseller:generate")
def handle_reseller_generate(call):
    user_id = call.from_user.id
    language = get_user_language(user_id)
    reseller_data = _get_active_reseller_data(user_id)
    if not reseller_data:
        bot.answer_callback_query(call.id, "Reseller access required.")
        return
    if _is_reseller_suspended(reseller_data):
        debt = float(reseller_data.get('debt', 0.0))
        unlock_amount = get_reseller_unlock_amount(debt)
        bot.answer_callback_query(
            call.id,
            get_message_text(language, "reseller_suspended_due_debt").format(debt=debt, unlock_amount=unlock_amount)
        )
        return
    
    plans = load_plans()
    sorted_plans = sorted(plans.items(), key=lambda x: int(x[0]))
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    for gb, details in sorted_plans:
        if details.get("target", "both") == "customer":
            continue
        original_price = float(details['price'])
        discounted_price = original_price * 0.8
        button_text = f"{gb} GB - ${format_usd_amount(discounted_price)} (20% OFF) - {details['days']} days"
        markup.add(types.InlineKeyboardButton(button_text, callback_data=f"reseller:buy:{gb}"))
        
    markup.add(types.InlineKeyboardButton(get_button_text(language, "cancel"), callback_data="reseller:cancel"))
    
    bot.edit_message_text(
        get_message_text(language, "select_plan"),
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("reseller:buy:"))
def handle_reseller_buy(call):
    user_id = call.from_user.id
    language = get_user_language(user_id)
    reseller_data = _get_active_reseller_data(user_id)
    if not reseller_data:
        bot.answer_callback_query(call.id, "Reseller access required.")
        return
    if _is_reseller_suspended(reseller_data):
        debt = float(reseller_data.get('debt', 0.0))
        unlock_amount = get_reseller_unlock_amount(debt)
        bot.answer_callback_query(
            call.id,
            get_message_text(language, "reseller_suspended_due_debt").format(debt=debt, unlock_amount=unlock_amount)
        )
        return
    gb = call.data.split(':')[2]
    
    plans = load_plans()
    if gb not in plans:
        return
        
    plan = plans[gb]
    if plan.get("target", "both") == "customer":
        bot.answer_callback_query(call.id, "This plan is for customers only.")
        return
        
    original_price = float(plan['price'])
    price = original_price * 0.8  # 20% discount for resellers
    days = plan['days']

    current_debt = float(reseller_data.get('debt', 0.0))
    projected_debt = current_debt + price
    can_add, trust_limit, available_credit = can_reseller_add_debt(reseller_data, price)
    if not can_add:
        _show_reseller_trust_limit_block(call, language, current_debt, price, trust_limit, available_credit)
        return

    if projected_debt >= DEBT_WARNING_THRESHOLD:
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton(get_message_text(language, "continue_action"), callback_data=f"reseller:details:{gb}"))
        markup.add(types.InlineKeyboardButton(get_button_text(language, "cancel"), callback_data="reseller:cancel"))
        warning_msg = get_message_text(language, "reseller_debt_warning_message").format(
            current_debt=current_debt,
            purchase_adds=price,
            projected_debt=projected_debt
        )
        bot.edit_message_text(
            warning_msg,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=markup
        )
        return
    
    _show_reseller_purchase_details(call, language, gb, days, price, current_debt, trust_limit)


@bot.callback_query_handler(func=lambda call: call.data.startswith("reseller:details:"))
def handle_reseller_purchase_details(call):
    user_id = call.from_user.id
    language = get_user_language(user_id)
    reseller_data = _get_active_reseller_data(user_id)
    if not reseller_data:
        bot.answer_callback_query(call.id, "Reseller access required.")
        return
    if _is_reseller_suspended(reseller_data):
        debt = float(reseller_data.get('debt', 0.0))
        unlock_amount = get_reseller_unlock_amount(debt)
        bot.answer_callback_query(
            call.id,
            get_message_text(language, "reseller_suspended_due_debt").format(debt=debt, unlock_amount=unlock_amount)
        )
        return

    gb = call.data.split(':')[2]
    plans = load_plans()
    if gb not in plans:
        bot.answer_callback_query(call.id, "Plan not found.")
        return

    plan = plans[gb]
    if plan.get("target", "both") == "customer":
        bot.answer_callback_query(call.id, "This plan is for customers only.")
        return

    price = float(plan['price']) * 0.8
    current_debt = float(reseller_data.get('debt', 0.0))
    can_add, trust_limit, available_credit = can_reseller_add_debt(reseller_data, price)
    if not can_add:
        _show_reseller_trust_limit_block(call, language, current_debt, price, trust_limit, available_credit)
        return

    _show_reseller_purchase_details(call, language, gb, plan['days'], price, current_debt, trust_limit)


@bot.callback_query_handler(func=lambda call: call.data.startswith("reseller:confirm_buy:"))
def handle_reseller_confirm_buy(call):
    user_id = call.from_user.id
    language = get_user_language(user_id)
    reseller_data = _get_active_reseller_data(user_id)
    if not reseller_data:
        bot.answer_callback_query(call.id, "Reseller access required.")
        return
    if _is_reseller_suspended(reseller_data):
        debt = float(reseller_data.get('debt', 0.0))
        unlock_amount = get_reseller_unlock_amount(debt)
        bot.answer_callback_query(
            call.id,
            get_message_text(language, "reseller_suspended_due_debt").format(debt=debt, unlock_amount=unlock_amount)
        )
        return

    gb = call.data.split(':')[2]
    plans = load_plans()
    if gb not in plans:
        bot.answer_callback_query(call.id, "Plan not found.")
        return

    plan = plans[gb]
    if plan.get("target", "both") == "customer":
        bot.answer_callback_query(call.id, "This plan is for customers only.")
        return
        
    original_price = float(plan['price'])
    price = original_price * 0.8
    days = plan['days']
    current_debt = float(reseller_data.get('debt', 0.0))
    can_add, trust_limit, available_credit = can_reseller_add_debt(reseller_data, price)
    if not can_add:
        bot.answer_callback_query(
            call.id,
            get_message_text(language, "reseller_trust_limit_exceeded_short").format(
                trust_limit=trust_limit,
                available_credit=available_credit,
            ),
            show_alert=True
        )
        _show_reseller_trust_limit_block(call, language, current_debt, price, trust_limit, available_credit)
        return

    user_data[user_id] = {
        'state': 'waiting_reseller_username',
        'gb': gb,
        'days': days,
        'price': price,
        'unlimited': plan.get('unlimited', False)
    }

    bot.edit_message_text(
        get_message_text(language, "enter_reseller_customer_username"),
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=_reseller_username_prompt_markup(language)
    )

@bot.message_handler(func=lambda message: message.from_user.id in user_data and user_data[message.from_user.id].get('state') == 'waiting_reseller_username')
def handle_reseller_username_input(message):
    user_id = message.from_user.id
    language = get_user_language(user_id)
    reseller_data = _get_active_reseller_data(user_id)
    if not reseller_data:
        if user_id in user_data:
            del user_data[user_id]
        bot.reply_to(message, "Your reseller access is not active.")
        return
    if _is_reseller_suspended(reseller_data):
        debt = float(reseller_data.get('debt', 0.0))
        unlock_amount = get_reseller_unlock_amount(debt)
        if user_id in user_data:
            del user_data[user_id]
        bot.reply_to(message, get_message_text(language, "reseller_suspended_due_debt").format(debt=debt, unlock_amount=unlock_amount))
        return
    chosen_username = message.text.strip()
    
    # Validate username: alphanumeric and max 8 chars
    if not re.match(r'^[a-zA-Z0-9]{1,8}$', chosen_username):
        bot.reply_to(message, get_message_text(language, "invalid_username_format"))
        return
        
    data = user_data[user_id]
    gb = data['gb']
    days = data['days']
    price = data['price']
    unlimited = data.get('unlimited', False)
    
    # Create user
    api_client = APIClient()
    username, result, api_client = _create_reseller_user_with_note(
        api_client,
        user_id,
        gb,
        days,
        chosen_username,
        unlimited=unlimited,
    )
    
    if result:
        # Add debt
        config_data = {
            "username": username,
            "customer_name": chosen_username,
            "gb": gb,
            "days": days,
            "price": price,
            "server_id": api_client.server_id,
        }
        debt_added = add_reseller_debt(user_id, price, config_data)
        if not debt_added:
            for admin_id in ADMIN_USER_IDS:
                try:
                    bot.send_message(admin_id, f"⚠️ Reseller debt write failed for user {user_id} after config creation: {username}")
                except:
                    pass
            bot.reply_to(message, "Config was created, but accounting failed. Admins have been notified.")
            if user_id in user_data:
                del user_data[user_id]
            return
        
        # Get subscription URL
        user_uri_data = api_client.get_user_uri(username)
        sub_url = user_uri_data.get('normal_sub', 'N/A') if user_uri_data else 'N/A'
        ipv4_url = user_uri_data.get('ipv4', '') if user_uri_data else ''
        ipv4_info = f"IPv4 URL: `{ipv4_url}`\n\n" if ipv4_url else ""
        
        msg = get_message_text(language, "reseller_config_created").format(
            username=username,
            plan_gb=gb,
            days=days,
            price=format_usd_amount(price),
            sub_url=sub_url,
            ipv4_info=ipv4_info
        )
        
        if sub_url != 'N/A':
            qr = qrcode.make(ipv4_url or sub_url)
            bio = io.BytesIO()
            qr.save(bio, 'PNG')
            bio.seek(0)
            bot.send_photo(message.chat.id, bio, caption=msg, parse_mode="Markdown")
        else:
            bot.send_message(message.chat.id, msg, parse_mode="Markdown")
            
        # Clear state
        del user_data[user_id]
    else:
        bot.reply_to(message, "Failed to create config. Please try again or contact support.")
        del user_data[user_id]

@bot.callback_query_handler(func=lambda call: call.data == "reseller:debt")
def handle_reseller_debt(call):
    user_id = call.from_user.id
    language = get_user_language(user_id)
    reseller_data = _get_active_reseller_data(user_id)
    if not reseller_data:
        bot.answer_callback_query(call.id, "Reseller access required.")
        return
    debt = float(reseller_data.get('debt', 0.0))
    debt_state = reseller_data.get('debt_state', 'active')
    debt_state_text = get_message_text(language, _debt_state_label(debt_state))
    debt_since = reseller_data.get('debt_since') or 'N/A'
    last_payment_at = reseller_data.get('last_payment_at') or 'N/A'
    trust_limit = get_reseller_trust_limit(get_reseller_total_paid(reseller_data))
    unlock_amount = get_reseller_unlock_amount(debt) if debt_state == 'suspended' else 0.0
    
    markup = types.InlineKeyboardMarkup()
    if debt > 0:
        markup.add(types.InlineKeyboardButton(get_button_text(language, "settle_debt"), callback_data=f"reseller:settle:{debt:.2f}"))
    markup.add(types.InlineKeyboardButton(get_button_text(language, "cancel"), callback_data="reseller:cancel"))
    
    bot.edit_message_text(
        (
            f"{get_message_text(language, 'current_debt').replace('${debt}', f'${format_usd_amount(debt)}')}\n"
            f"{get_message_text(language, 'reseller_trust_limit_line').format(trust_limit=trust_limit)}\n"
            f"{get_message_text(language, 'reseller_debt_status_line').format(debt_state=debt_state_text)}\n"
            f"{get_message_text(language, 'reseller_oldest_unpaid_date_line').format(debt_since=debt_since)}\n"
            f"{get_message_text(language, 'reseller_last_payment_date_line').format(last_payment_at=last_payment_at)}\n"
            f"{get_message_text(language, 'reseller_amount_due_to_unlock_line').format(unlock_amount=unlock_amount)}"
        ),
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("reseller:settle:"))
def handle_reseller_settle(call):
    user_id = call.from_user.id
    language = get_user_language(user_id)
    reseller_data = _get_active_reseller_data(user_id)
    if not reseller_data:
        bot.answer_callback_query(call.id, "Reseller access required.")
        return
    amount = float(reseller_data.get('debt', 0.0))
    if amount <= 0:
        bot.answer_callback_query(call.id, get_message_text(language, "debt_cleared"))
        return
    
    # Re-use payment logic
    env_path = '/etc/dijiq/core/scripts/telegrambot/.env'
    load_dotenv(env_path)
    
    crypto_configured = all(os.getenv(key) for key in ['CRYPTO_MERCHANT_ID', 'CRYPTO_API_KEY'])
    card_to_card_configured = get_card_number_for_receipt_type(RECEIPT_TYPE_SETTLEMENT)
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    if crypto_configured:
        markup.add(types.InlineKeyboardButton(get_crypto_discount_button_text(language), callback_data=f"reseller:pay:crypto:{amount:.2f}"))
    if card_to_card_configured:
        markup.add(types.InlineKeyboardButton(get_button_text(language, "card_to_card"), callback_data=f"reseller:pay:card:{amount:.2f}"))
        
    markup.add(types.InlineKeyboardButton(get_button_text(language, "cancel"), callback_data="reseller:cancel"))

    message = get_message_text(language, "select_payment_method")
    
    bot.edit_message_text(
        message,
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("reseller:pay:"))
def handle_reseller_payment(call):
    user_id = call.from_user.id
    language = get_user_language(user_id)
    reseller_data = _get_active_reseller_data(user_id)
    if not reseller_data:
        bot.answer_callback_query(call.id, "Reseller access required.")
        return
    _, _, method, amount = call.data.split(':')
    amount = float(amount)
    current_debt = float(reseller_data.get('debt', 0.0))
    if current_debt <= 0:
        bot.answer_callback_query(call.id, get_message_text(language, "debt_cleared"))
        return
    amount_to_pay = min(amount, current_debt)
    
    if method == 'crypto':
        discount_metadata = build_crypto_discount_metadata(amount_to_pay)
        discounted_amount_to_pay = discount_metadata['price']
        payment_handler = CryptoPayment()
        payment_response = payment_handler.create_payment(
            discounted_amount_to_pay, "Settlement", user_id
        )
        if "error" in payment_response:
             bot.answer_callback_query(call.id, f"Error: {payment_response['error']}")
             return
             
        payment_data = payment_response.get('result', {})
        payment_id = payment_data.get('uuid')
        payment_url = payment_data.get('url')
        
        if payment_id and payment_url:
            payment_record = {
                'user_id': user_id,
                'plan_gb': 'Settlement',
                'days': 0,
                'payment_id': payment_id,
                'status': 'pending',
                'type': 'settlement',
                'payment_method': 'Crypto',
                'settlement_amount': amount_to_pay,
                **discount_metadata,
            }
            add_payment_record(payment_id, payment_record)
            
            qr = qrcode.make(payment_url)
            bio = io.BytesIO()
            qr.save(bio, 'PNG')
            bio.seek(0)
            
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton(get_button_text(language, "payment_link"), url=payment_url),
                types.InlineKeyboardButton(get_button_text(language, "check_status"), callback_data=f"check_payment:{payment_id}")
            )
            
            bot.delete_message(call.message.chat.id, call.message.message_id)
            payment_message = get_message_text(language, "payment_instructions").format(
                price=format_usd_amount(discounted_amount_to_pay),
                payment_url=payment_url,
                payment_id=payment_id
            )
            payment_message += "\n\n" + build_crypto_discount_display(language, discount_metadata)['summary']
            bot.send_photo(
                call.message.chat.id,
                bio,
                caption=payment_message,
                reply_markup=markup
            )

    elif method == 'card':
        # Card to card logic
        exchange_rate = get_exchange_rate()
        card_number = get_card_number_for_receipt_type(RECEIPT_TYPE_SETTLEMENT)
        price_in_tomans = amount_to_pay * exchange_rate
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(get_button_text(language, "cancel"), callback_data="reseller:cancel"))
        
        bot.edit_message_text(
             get_message_text(language, "card_to_card_payment").format(
                 price=format_toman_amount(price_in_tomans),
                 exchange_rate=format_toman_amount(exchange_rate),
                 card_number=card_number
             ),
             chat_id=call.message.chat.id,
             message_id=call.message.message_id,
             parse_mode="Markdown",
             reply_markup=markup
        )
        
        user_data[user_id] = {
            'state': 'waiting_receipt',
            'plan_gb': 'Settlement',
            'price': amount_to_pay,
            'settlement_amount': amount_to_pay,
            'converted_amount': price_in_tomans,
            'converted_currency': 'Tomans',
            'exchange_rate': exchange_rate,
            'type': 'settlement',
            'receipt_type': RECEIPT_TYPE_SETTLEMENT,
            'cancel_callback': 'reseller:cancel',
            'receipt_prompt_message_id': call.message.message_id,
        }

@bot.callback_query_handler(func=lambda call: call.data == "reseller:cancel")
def handle_reseller_cancel(call):
    user_id = call.from_user.id
    if user_id in user_data:
        del user_data[user_id]
    bot.delete_message(call.message.chat.id, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data == "reseller:stats")
def handle_reseller_stats(call):
    user_id = call.from_user.id
    language = get_user_language(user_id)
    reseller_data = _get_active_reseller_data(user_id)
    
    if not reseller_data:
        bot.answer_callback_query(call.id, "Reseller access required.")
        return

    configs = reseller_data.get('configs', [])
    total_configs = len(configs)
    
    total_value = sum(_reseller_config_value(c) for c in configs if isinstance(c, dict))
    current_debt = float(reseller_data.get('debt', 0.0))
    total_paid = get_reseller_total_paid(reseller_data)
    trust_limit = get_reseller_trust_limit(total_paid)
    
    msg = get_message_text(language, "reseller_stats_message").format(
        user_id=user_id,
        joined_date=reseller_data.get('created_at', 'N/A'),
        total_configs=total_configs,
        total_value=format_usd_amount(total_value),
        total_paid=format_usd_amount(total_paid),
        current_debt=format_usd_amount(current_debt),
        trust_limit=format_usd_amount(trust_limit),
    )
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(get_button_text(language, "cancel"), callback_data="reseller:cancel"))
    
    bot.edit_message_text(
        msg,
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=markup,
        parse_mode="Markdown"
    )

RESELLER_CUSTOMERS_PAGE_SIZE = 5
RESELLER_CUSTOMER_LOW_THRESHOLD = 80
RESELLER_CUSTOMER_CATEGORY_ORDER = ("active", "low_days", "low_gb", "expired", "deleted")
RESELLER_CUSTOMER_CATEGORY_ICONS = {
    "active": "✅",
    "low_days": "📅",
    "low_gb": "📊",
    "expired": "⌛",
    "deleted": "🗑",
}


def _safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _valid_reseller_customer_name(value):
    name = str(value or "").strip()
    if re.match(r"^[a-zA-Z0-9]{1,8}$", name):
        return name
    return ""


def _extract_customer_name_from_note(note):
    if not isinstance(note, str):
        return ""
    match = re.search(r"📝\s*([^|]+?)\s*\|", note)
    if not match:
        return ""
    return _valid_reseller_customer_name(match.group(1))


def _resolve_reseller_customer_name(cfg):
    stored_name = _valid_reseller_customer_name((cfg or {}).get("customer_name"))
    if stored_name:
        return stored_name
    user_config = (cfg or {}).get("_user_config") or {}
    return _extract_customer_name_from_note(user_config.get("note"))


def _is_removed_config(cfg):
    return isinstance(cfg, dict) and bool(cfg.get("removed_from_vpn"))


def _removed_config_reason_line(cfg):
    if not _is_removed_config(cfg):
        return ""
    note = str(cfg.get("removal_note") or "Removed from VPN during cleanup").strip()
    removed_at = str(cfg.get("removed_at") or "").strip()
    if removed_at:
        return f"\n   🧾 {note} ({removed_at})"
    return f"\n   🧾 {note}"


def _format_reseller_customer_entry(index, cfg, category, language):
    username = cfg.get('username', 'N/A')
    customer_name = _resolve_reseller_customer_name(cfg)
    gb = cfg.get('gb', '?')
    days = cfg.get('days', '?')
    price = cfg.get('price', 0)
    timestamp = cfg.get('timestamp', 'N/A')
    status_category = cfg.get("_status_category", category)
    status_label = _customer_category_label(language, status_category)
    if cfg.get("_status_note") == "status_unavailable":
        status_label = get_message_text(language, "reseller_customer_status_unavailable")

    identifier_lines = [f"{index}. {RESELLER_CUSTOMER_CATEGORY_ICONS.get(status_category, '✅')} `{customer_name or username}`"]
    if customer_name:
        identifier_lines.append(f"   🆔 `{username}`")
    removal_reason = _removed_config_reason_line(cfg)

    return (
        "\n".join(identifier_lines) + "\n"
        f"   {status_label}\n"
        f"   📊 {gb} GB | 📅 {days}d | 💰 ${format_usd_amount(price)}\n"
        f"   🕒 {timestamp}"
        f"{removal_reason}"
    )


def _load_reseller_live_users():
    multi_api = MultiServerAPI()
    live_users = {}
    unavailable_server_ids = set()

    for server, client in multi_api.iter_clients(include_disabled=True):
        server_id = server.get("id") or client.server_id
        users = client.get_users()
        if users is None:
            unavailable_server_ids.add(server_id)
            continue

        if isinstance(users, dict):
            for username, data in users.items():
                if username and isinstance(data, dict):
                    live_users[str(username)] = data
        elif isinstance(users, list):
            for data in users:
                if isinstance(data, dict) and data.get("username"):
                    live_users[str(data["username"])] = data

    return live_users, unavailable_server_ids


def _traffic_usage_percent(user_config):
    max_download_bytes = user_config.get("max_download_bytes", 0) or 0
    if max_download_bytes <= 0:
        return 0
    used_bytes = (user_config.get("upload_bytes", 0) or 0) + (user_config.get("download_bytes", 0) or 0)
    return (used_bytes / max_download_bytes) * 100


def _days_usage_percent(cfg, user_config):
    total_days = _safe_int(cfg.get("days"), 0)
    expiration_days = _safe_int(user_config.get("expiration_days"), 0)
    if total_days <= 0:
        return 0
    days_used = max(0, total_days - expiration_days)
    return (days_used / total_days) * 100


def _is_customer_expired(user_config):
    if bool(user_config.get("blocked", False)):
        return True
    if _safe_int(user_config.get("expiration_days"), 0) <= 0:
        return True
    max_download_bytes = user_config.get("max_download_bytes", 0) or 0
    if max_download_bytes > 0:
        used_bytes = (user_config.get("upload_bytes", 0) or 0) + (user_config.get("download_bytes", 0) or 0)
        return used_bytes >= max_download_bytes
    return False


def _categorize_reseller_customers(configs):
    live_users, unavailable_server_ids = _load_reseller_live_users()
    categorized = {category: [] for category in RESELLER_CUSTOMER_CATEGORY_ORDER}

    for cfg in configs:
        username = cfg.get("username")
        user_config = live_users.get(str(username)) if username else None
        server_id = cfg.get("server_id")
        enriched = {**cfg, "_user_config": user_config}

        if _is_removed_config(cfg):
            enriched["_status_category"] = "deleted"
            categorized["deleted"].append(enriched)
            continue

        if not user_config:
            if server_id and server_id in unavailable_server_ids:
                enriched["_status_category"] = "active"
                enriched["_status_note"] = "status_unavailable"
                categorized["active"].append(enriched)
            else:
                enriched["_status_category"] = "deleted"
                categorized["deleted"].append(enriched)
            continue

        if _is_customer_expired(user_config):
            enriched["_status_category"] = "expired"
            categorized["expired"].append(enriched)
            continue

        enriched["_status_category"] = "active"
        categorized["active"].append(enriched)

        if _days_usage_percent(cfg, user_config) >= RESELLER_CUSTOMER_LOW_THRESHOLD:
            low_days = {**enriched, "_status_category": "low_days"}
            categorized["low_days"].append(low_days)

        if _traffic_usage_percent(user_config) >= RESELLER_CUSTOMER_LOW_THRESHOLD:
            low_gb = {**enriched, "_status_category": "low_gb"}
            categorized["low_gb"].append(low_gb)

    return categorized


def _customer_category_label(language, category):
    return get_message_text(language, f"reseller_customer_category_{category}")


def _render_reseller_customer_message(call, msg, markup):
    if call.message.photo or call.message.document or call.message.sticker:
        try:
            bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)
        except Exception:
            pass
        bot.send_message(call.message.chat.id, msg, reply_markup=markup, parse_mode="Markdown")
        return

    bot.edit_message_text(
        msg,
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=markup,
        parse_mode="Markdown"
    )


def _render_reseller_customer_overview(call, language, categorized, total):
    lines = []
    for category in RESELLER_CUSTOMER_CATEGORY_ORDER:
        lines.append(
            get_message_text(language, "reseller_customer_category_count").format(
                icon=RESELLER_CUSTOMER_CATEGORY_ICONS[category],
                label=_customer_category_label(language, category),
                count=len(categorized[category])
            )
        )

    msg = get_message_text(language, "reseller_customers_overview").format(
        total=total,
        categories="\n".join(lines)
    )

    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = []
    for category in RESELLER_CUSTOMER_CATEGORY_ORDER:
        buttons.append(
            types.InlineKeyboardButton(
                f"{RESELLER_CUSTOMER_CATEGORY_ICONS[category]} {_customer_category_label(language, category)} ({len(categorized[category])})",
                callback_data=f"reseller:my_customers:{category}:0"
            )
        )
    markup.add(*buttons)
    markup.add(types.InlineKeyboardButton(get_button_text(language, "cancel"), callback_data="reseller:cancel"))
    _render_reseller_customer_message(call, msg, markup)


def _render_reseller_customer_category(call, language, categorized, category, page):
    category_configs = categorized.get(category, [])
    total = len(category_configs)
    label = _customer_category_label(language, category)

    if total == 0:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(get_button_text(language, "reseller_back_to_customers"), callback_data="reseller:my_customers:overview"))
        markup.add(types.InlineKeyboardButton(get_button_text(language, "cancel"), callback_data="reseller:cancel"))
        _render_reseller_customer_message(
            call,
            get_message_text(language, "reseller_customers_empty_category").format(category=label),
            markup
        )
        return

    total_pages = max(1, (total + RESELLER_CUSTOMERS_PAGE_SIZE - 1) // RESELLER_CUSTOMERS_PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    start = page * RESELLER_CUSTOMERS_PAGE_SIZE
    end = start + RESELLER_CUSTOMERS_PAGE_SIZE
    page_configs = category_configs[start:end]

    entries_lines = []
    for i, cfg in enumerate(page_configs, start=start + 1):
        entries_lines.append(_format_reseller_customer_entry(i, cfg, category, language))

    msg = get_message_text(language, "reseller_customers_category_header").format(
        category=label,
        total=total,
        page=page + 1,
        total_pages=total_pages,
        entries="\n\n".join(entries_lines)
    )

    markup = types.InlineKeyboardMarkup(row_width=1)
    row_buttons = []
    for i, cfg in enumerate(page_configs, start=start + 1):
        username = cfg.get('username', 'N/A')
        row_buttons.append(types.InlineKeyboardButton(f"{i}", callback_data=f"reseller:cfg:{username}:{category}:{page}"))
    if row_buttons:
        markup.row(*row_buttons)

    nav_buttons = []
    if page > 0:
        nav_buttons.append(types.InlineKeyboardButton("⬅️", callback_data=f"reseller:my_customers:{category}:{page - 1}"))
    nav_buttons.append(types.InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="reseller:my_customers_noop"))
    if page < total_pages - 1:
        nav_buttons.append(types.InlineKeyboardButton("➡️", callback_data=f"reseller:my_customers:{category}:{page + 1}"))
    if nav_buttons:
        markup.row(*nav_buttons)

    markup.add(types.InlineKeyboardButton(get_button_text(language, "reseller_back_to_customers"), callback_data="reseller:my_customers:overview"))
    markup.add(types.InlineKeyboardButton(get_button_text(language, "cancel"), callback_data="reseller:cancel"))
    _render_reseller_customer_message(call, msg, markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("reseller:my_customers:"))
def handle_reseller_my_customers(call):
    user_id = call.from_user.id
    language = get_user_language(user_id)
    reseller_data = _get_active_reseller_data(user_id)

    if not reseller_data:
        bot.answer_callback_query(call.id, "Reseller access required.")
        return

    configs = list(reseller_data.get('configs', []))
    # Show newest configs first
    configs = list(reversed(configs))
    total = len(configs)

    if total == 0:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(get_button_text(language, "cancel"), callback_data="reseller:cancel"))
        bot.edit_message_text(
            get_message_text(language, "reseller_no_configs_created"),
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=markup
        )
        return

    categorized = _categorize_reseller_customers(configs)
    parts = call.data.split(":")
    category = parts[2] if len(parts) > 2 else "overview"

    if category == "overview" or category.isdigit():
        _render_reseller_customer_overview(call, language, categorized, total)
        return

    if category not in RESELLER_CUSTOMER_CATEGORY_ORDER:
        bot.answer_callback_query(call.id, "Invalid customer category.")
        return

    try:
        page = int(parts[3])
    except (IndexError, ValueError):
        page = 0

    _render_reseller_customer_category(call, language, categorized, category, page)

@bot.callback_query_handler(func=lambda call: call.data == "reseller:my_customers_noop")
def handle_reseller_customers_noop(call):
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("reseller:cfg:"))
def handle_reseller_customer_config(call):
    """Show the config card for a specific customer of the reseller."""
    user_id = call.from_user.id
    language = get_user_language(user_id)

    # Validate reseller access (both approved and suspended can view configs)
    reseller_data = get_reseller_data(user_id)
    if not reseller_data or reseller_data.get('status') not in ('approved', 'suspended'):
        bot.answer_callback_query(call.id, "Reseller access required.")
        return

    # Parse callback data: reseller:cfg:{username}:{category}:{page}
    # Legacy callback shape reseller:cfg:{username}:{page} is still accepted.
    parts = call.data.split(":")
    if len(parts) < 4:
        bot.answer_callback_query(call.id, "Invalid request.")
        return

    username = parts[2]
    return_category = "overview"
    if len(parts) >= 5:
        return_category = parts[3] if parts[3] in RESELLER_CUSTOMER_CATEGORY_ORDER else "overview"
        try:
            return_page = int(parts[4])
        except (ValueError, IndexError):
            return_page = 0
    else:
        try:
            return_page = int(parts[3])
        except (ValueError, IndexError):
            return_page = 0

    bot.answer_callback_query(call.id)

    preferred_server_id = None
    matched_config_index = None
    for index, cfg in enumerate((reseller_data or {}).get('configs', [])):
        if cfg.get('username') == username:
            preferred_server_id = cfg.get('server_id')
            matched_config_index = index
            break

    # Fetch live config data from the server that owns this config.
    multi_api = MultiServerAPI()
    api_client, user_config = multi_api.find_user(username, preferred_server_id=preferred_server_id)

    back_markup = types.InlineKeyboardMarkup()
    back_markup.add(
        types.InlineKeyboardButton(
            get_button_text(language, "reseller_back_to_customers"),
            callback_data=f"reseller:my_customers:{return_category}:{return_page}"
        )
    )

    if not user_config:
        bot.edit_message_text(
            f"⚠️ Could not retrieve data for `{username}`. The config may have been deleted.",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=back_markup,
            parse_mode="Markdown"
        )
        return

    # Extract stats
    is_blocked = bool(user_config.get('blocked', False))
    upload_bytes = user_config.get('upload_bytes', 0) or 0
    download_bytes = user_config.get('download_bytes', 0) or 0
    max_download_bytes = user_config.get('max_download_bytes', 0) or 0
    expiration_days = user_config.get('expiration_days', 0)
    account_creation_date = user_config.get('account_creation_date', 'N/A')
    status = user_config.get('status', 'Unknown')

    upload_gb = upload_bytes / (1024 ** 3)
    download_gb = download_bytes / (1024 ** 3)
    total_usage_gb = upload_gb + download_gb
    max_traffic_gb = max_download_bytes / (1024 ** 3)

    traffic_limit_display = f"{max_traffic_gb:.2f} GB" if max_traffic_gb > 0 else "Unlimited"

    if upload_bytes == 0 and download_bytes == 0:
        traffic_message = "**Traffic Data:**\nNo traffic data available."
    else:
        traffic_message = (
            f"🔼 Upload: {upload_gb:.2f} GB\n"
            f"🔽 Download: {download_gb:.2f} GB\n"
            f"📊 Total Usage: {total_usage_gb:.2f} GB"
        )
        if max_traffic_gb > 0:
            traffic_message += f" / {max_traffic_gb:.2f} GB"
        traffic_message += f"\n🌐 Status: {status}"

    formatted_details = (
        f"\n🆔 Username: `{username}`\n"
        f"📊 Traffic Limit: {traffic_limit_display}\n"
        f"📅 Days Remaining: {expiration_days}\n"
        f"⏳ Creation Date: {account_creation_date}\n"
        f"💡 Status: {'❌ Blocked/Expired' if is_blocked else '✅ Active'}\n\n"
        f"{traffic_message}"
    )

    if is_blocked:
        expired_markup = back_markup
        if matched_config_index is not None and not _is_reseller_suspended(reseller_data):
            try:
                from utils.renewal import find_reseller_renewal_offer

                offer = find_reseller_renewal_offer(
                    user_id,
                    matched_config_index,
                    api_client,
                    user_config,
                    load_plans(),
                    reseller_data=reseller_data,
                )
                if offer.get("eligible"):
                    expired_markup = types.InlineKeyboardMarkup()
                    expired_markup.add(
                        types.InlineKeyboardButton(
                            get_button_text(language, "renew_plan") or "Renew Plan",
                            callback_data=f"reseller:renew:{offer['token']}"
                        )
                    )
                    expired_markup.add(
                        types.InlineKeyboardButton(
                            get_button_text(language, "reseller_back_to_customers"),
                            callback_data=f"reseller:my_customers:{return_category}:{return_page}"
                        )
                    )
            except Exception as renewal_error:
                print(f"Error building reseller renewal offer for {username}: {renewal_error}")
        message_text = f"❌ **Configuration expired/blocked**\n{formatted_details}"
        bot.edit_message_text(
            message_text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=expired_markup,
            parse_mode="Markdown"
        )
        return

    # Active config — fetch subscription URL and send QR code
    user_uri_data = api_client.get_user_uri(username)
    if not user_uri_data or 'normal_sub' not in user_uri_data:
        bot.edit_message_text(
            f"⚠️ Could not generate subscription URL for `{username}`.",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=back_markup,
            parse_mode="Markdown"
        )
        return

    sub_url = user_uri_data['normal_sub']
    ipv4_url = user_uri_data.get('ipv4', '')

    caption = f"{formatted_details}\n\n"
    if ipv4_url:
        caption += f"IPv4 URL: `{ipv4_url}`\n\n"
    caption += f"Subscription URL:\n{sub_url}"

    try:
        qr_code = qrcode.make(ipv4_url or sub_url)
        bio = io.BytesIO()
        qr_code.save(bio, 'PNG')
        bio.seek(0)

        bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)
        bot.send_photo(
            call.message.chat.id,
            photo=bio,
            caption=caption,
            parse_mode="Markdown",
            reply_markup=back_markup
        )
    except Exception as e:
        bot.send_message(
            call.message.chat.id,
            caption,
            parse_mode="Markdown",
            reply_markup=back_markup
        )


def _resolve_reseller_renewal_offer_for_call(call, token):
    from utils.renewal import resolve_reseller_renewal_token

    reseller_data = get_reseller_data(call.from_user.id)
    return resolve_reseller_renewal_token(
        call.from_user.id,
        token,
        load_plans(),
        reseller_data=reseller_data,
    ), reseller_data


def _reseller_renewal_details_message(language, offer, current_debt, trust_limit):
    from utils.renewal import format_renewal_offer

    projected_debt = current_debt + float(offer.get('price', 0.0))
    message = format_renewal_offer(language, offer, include_payment_prompt=False)
    message += "\n\n" + get_message_text(language, "reseller_renewal_debt_details").format(
        price=format_usd_amount(offer.get('price', 0.0)),
        current_debt=format_usd_amount(current_debt),
        projected_debt=format_usd_amount(projected_debt),
        trust_limit=format_usd_amount(trust_limit),
    )
    if projected_debt >= DEBT_WARNING_THRESHOLD:
        message += "\n\n" + get_message_text(language, "reseller_debt_warning_message").format(
            current_debt=current_debt,
            purchase_adds=float(offer.get('price', 0.0)),
            projected_debt=projected_debt,
        )
    return message


def _renewal_reason_text(language, reason):
    return get_message_text(language, reason or "renewal_failed") or str(reason or "renewal_failed")


@bot.callback_query_handler(func=lambda call: call.data.startswith("reseller:renew:"))
def handle_reseller_renewal_start(call):
    user_id = call.from_user.id
    language = get_user_language(user_id)
    reseller_data = _get_active_reseller_data(user_id)
    if not reseller_data:
        bot.answer_callback_query(call.id, "Reseller access required.")
        return
    if _is_reseller_suspended(reseller_data):
        debt = float(reseller_data.get('debt', 0.0))
        unlock_amount = get_reseller_unlock_amount(debt)
        bot.answer_callback_query(
            call.id,
            get_message_text(language, "reseller_suspended_due_debt").format(debt=debt, unlock_amount=unlock_amount),
            show_alert=True,
        )
        return

    token = call.data.split(":", 2)[2]
    offer, reseller_data = _resolve_reseller_renewal_offer_for_call(call, token)
    if not offer.get("eligible"):
        bot.answer_callback_query(
            call.id,
            get_message_text(language, "renewal_unavailable").format(reason=_renewal_reason_text(language, offer.get("reason"))),
            show_alert=True,
        )
        return

    price = float(offer.get('price', 0.0))
    current_debt = float(reseller_data.get('debt', 0.0))
    can_add, trust_limit, available_credit = can_reseller_add_debt(reseller_data, price)
    if not can_add:
        _show_reseller_trust_limit_block(call, language, current_debt, price, trust_limit, available_credit)
        return

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton(get_button_text(language, "confirm"), callback_data=f"reseller:renew_confirm:{token}"))
    markup.add(types.InlineKeyboardButton(get_button_text(language, "cancel"), callback_data="reseller:cancel"))
    bot.edit_message_text(
        _reseller_renewal_details_message(language, offer, current_debt, trust_limit),
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=markup,
        parse_mode="Markdown",
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("reseller:renew_confirm:"))
def handle_reseller_renewal_confirm(call):
    user_id = call.from_user.id
    language = get_user_language(user_id)
    reseller_data = _get_active_reseller_data(user_id)
    if not reseller_data:
        bot.answer_callback_query(call.id, "Reseller access required.")
        return
    if _is_reseller_suspended(reseller_data):
        debt = float(reseller_data.get('debt', 0.0))
        unlock_amount = get_reseller_unlock_amount(debt)
        bot.answer_callback_query(
            call.id,
            get_message_text(language, "reseller_suspended_due_debt").format(debt=debt, unlock_amount=unlock_amount),
            show_alert=True,
        )
        return

    token = call.data.split(":", 2)[2]
    offer, reseller_data = _resolve_reseller_renewal_offer_for_call(call, token)
    if not offer.get("eligible"):
        bot.answer_callback_query(
            call.id,
            get_message_text(language, "renewal_unavailable").format(reason=_renewal_reason_text(language, offer.get("reason"))),
            show_alert=True,
        )
        return

    price = float(offer.get('price', 0.0))
    current_debt = float(reseller_data.get('debt', 0.0))
    can_add, trust_limit, available_credit = can_reseller_add_debt(reseller_data, price)
    if not can_add:
        _show_reseller_trust_limit_block(call, language, current_debt, price, trust_limit, available_credit)
        return

    from utils.renewal import execute_reseller_renewal, format_renewal_success, reseller_renewal_record
    from utils.reseller import add_reseller_renewal_debt

    result = execute_reseller_renewal(offer)
    if not result.get('success'):
        bot.edit_message_text(
            get_message_text(language, "renewal_failed").format(reason=_renewal_reason_text(language, result.get('reason'))),
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="Markdown",
        )
        return

    renewal_record = reseller_renewal_record(offer, result.get('before_state'), result.get('after_state'))
    debt_added = add_reseller_renewal_debt(
        user_id,
        offer.get('username'),
        price,
        renewal_record,
        server_id=offer.get('server_id'),
    )
    if not debt_added:
        for admin_id in ADMIN_USER_IDS:
            try:
                bot.send_message(admin_id, f"⚠️ Reseller renewal accounting failed for user {user_id}: {offer.get('username')}")
            except:
                pass
        bot.edit_message_text(
            get_message_text(language, "renewal_accounting_failed"),
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="Markdown",
        )
        return

    api_client = result.get('api_client')
    user_uri_data = api_client.get_user_uri(offer.get('username')) if api_client else None
    sub_url = user_uri_data.get('normal_sub') if user_uri_data else None
    ipv4_url = user_uri_data.get('ipv4', '') if user_uri_data else ''
    success_message = format_renewal_success(
        language,
        result,
        offer.get('plan_gb'),
        offer.get('days'),
        sub_url=sub_url,
        ipv4_url=ipv4_url,
    )

    if sub_url:
        qr = qrcode.make(ipv4_url or sub_url)
        bio = io.BytesIO()
        qr.save(bio, 'PNG')
        bio.seek(0)
        try:
            bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)
        except Exception:
            pass
        bot.send_photo(
            call.message.chat.id,
            photo=bio,
            caption=success_message,
            parse_mode="Markdown",
        )
    else:
        bot.edit_message_text(
            success_message,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="Markdown",
        )


# Admin Management Handlers

ADMIN_RESELLER_STATUS_ORDER = ["pending", "suspended", "banned", "approved", "rejected"]
ADMIN_RESELLER_PAGE_SIZE = 8
ADMIN_RESELLER_MAX_DEBT = 100000.0
ADMIN_RESELLER_DEFAULT_LIST_STATUS = "pending"
ADMIN_RESELLER_DEBT_INPUT_STATE = {}
ADMIN_RESELLER_VIEW_CONTEXT = {}
ADMIN_RESELLER_CLEANUP_MAX_ITEMS = 45


def _admin_status_icon(status):
    if status == "approved":
        return "✅"
    if status == "pending":
        return "⏳"
    if status == "suspended":
        return "⚠️"
    if status == "banned":
        return "🚫"
    return "❌"


def _admin_status_label(language, status):
    status_key = {
        "pending": "admin_status_pending",
        "suspended": "admin_status_suspended",
        "banned": "admin_status_banned",
        "approved": "admin_status_approved",
        "rejected": "admin_status_rejected",
    }.get(status, "admin_status_rejected")
    return get_message_text(language, status_key)


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _reseller_config_value(config):
    try:
        from utils.reseller import get_reseller_config_value
        return get_reseller_config_value(config)
    except Exception:
        if not isinstance(config, dict) or _is_removed_config(config):
            return 0.0
        renewals = config.get("renewals", [])
        renewal_total = 0.0
        if isinstance(renewals, list):
            renewal_total = sum(
                _safe_float(renewal.get("price", 0.0))
                for renewal in renewals
                if isinstance(renewal, dict)
            )
        return _safe_float(config.get("price", 0.0)) + renewal_total


def _username_display(language, reseller_data):
    username = str((reseller_data or {}).get("telegram_username") or "").strip().lstrip("@")
    if username:
        return f"@{username}"
    return get_message_text(language, "admin_username_unknown")


def _escape_markdown(value):
    return str(value).replace("\\", "\\\\").replace("_", "\\_").replace("*", "\\*").replace("`", "\\`").replace("[", "\\[")


def _sort_resellers(items):
    def _id_key(reseller_id):
        as_str = str(reseller_id)
        if as_str.isdigit():
            return (0, int(as_str))
        return (1, as_str)

    return sorted(
        items,
        key=lambda item: (
            -_safe_float((item[1] or {}).get("debt", 0.0)),
            _id_key(item[0]),
        ),
    )


def _group_resellers(resellers):
    grouped = {status: [] for status in ADMIN_RESELLER_STATUS_ORDER}
    for rid, data in resellers.items():
        status = (data or {}).get("status", "rejected")
        if status not in grouped:
            status = "rejected"
        grouped[status].append((str(rid), data or {}))
    for status in grouped:
        grouped[status] = _sort_resellers(grouped[status])
    return grouped


def _reseller_financial_stats(reseller_data):
    configs = (reseller_data or {}).get("configs", [])
    if not isinstance(configs, list):
        configs = []

    total_configs = len(configs)
    billable_configs = [
        config
        for config in configs
        if isinstance(config, dict) and not _is_removed_config(config)
    ]
    total_turnover = sum(_reseller_config_value(config) for config in billable_configs)
    current_debt = _safe_float((reseller_data or {}).get("debt", 0.0))
    total_paid = get_reseller_total_paid(reseller_data)
    trust_limit = get_reseller_trust_limit(total_paid)
    average_config_value = total_turnover / len(billable_configs) if billable_configs else 0.0
    last_config_at = "N/A"

    for config in reversed(configs):
        if not isinstance(config, dict):
            continue
        timestamp = config.get("timestamp")
        if timestamp:
            last_config_at = timestamp
            break

    return {
        "total_configs": total_configs,
        "total_turnover": total_turnover,
        "total_paid": total_paid,
        "total_debt": current_debt,
        "trust_limit": trust_limit,
        "average_config_value": average_config_value,
        "last_config_at": last_config_at,
    }


def _reseller_admin_summary(resellers):
    summary = {
        "total_resellers": 0,
        "total_configs": 0,
        "total_turnover": 0.0,
        "total_paid": 0.0,
        "total_debt": 0.0,
    }

    for reseller_data in (resellers or {}).values():
        stats = _reseller_financial_stats(reseller_data)
        summary["total_resellers"] += 1
        summary["total_configs"] += stats["total_configs"]
        summary["total_turnover"] += stats["total_turnover"]
        summary["total_paid"] += stats["total_paid"]
        summary["total_debt"] += stats["total_debt"]

    return summary


def _paginate(items, page, page_size=ADMIN_RESELLER_PAGE_SIZE):
    if not items:
        return [], 1, 0
    total_pages = (len(items) + page_size - 1) // page_size
    page = max(0, min(page, total_pages - 1))
    start = page * page_size
    end = start + page_size
    return items[start:end], total_pages, page


def _build_admin_reseller_list_text(language, grouped):
    resellers = {}
    for items in grouped.values():
        for rid, data in items:
            resellers[str(rid)] = data
    summary = _reseller_admin_summary(resellers)
    lines = [
        get_message_text(language, "admin_resellers_list_grouped").format(
            total_resellers=summary["total_resellers"],
            total_configs=summary["total_configs"],
            total_turnover=format_usd_amount(summary["total_turnover"]),
            total_paid=format_usd_amount(summary["total_paid"]),
            total_debt=format_usd_amount(summary["total_debt"]),
        )
    ]
    for status in ADMIN_RESELLER_STATUS_ORDER:
        status_text = _admin_status_label(language, status)
        count = len(grouped.get(status, []))
        lines.append(
            get_message_text(language, "admin_reseller_section_count").format(
                status_icon=_admin_status_icon(status),
                status_label=status_text,
                count=count,
            )
        )
    return "\n".join(lines)


def _build_admin_reseller_list_markup(language, grouped, active_status=ADMIN_RESELLER_DEFAULT_LIST_STATUS, active_page=0):
    markup = types.InlineKeyboardMarkup(row_width=1)
    for status in ADMIN_RESELLER_STATUS_ORDER:
        items = grouped.get(status, [])
        status_text = _admin_status_label(language, status)

        # Status header button — clicking it expands this section
        markup.add(
            types.InlineKeyboardButton(
                get_message_text(language, "admin_reseller_section_button").format(
                    status_icon=_admin_status_icon(status),
                    status_label=status_text,
                    count=len(items),
                ),
                callback_data=f"admin_reseller_ui:list:{status}:0",
            )
        )

        # Only show entries for the currently active/expanded status
        if status == active_status:
            page = active_page
            visible, total_pages, page = _paginate(items, page)

            for rid, data in visible:
                stats = _reseller_financial_stats(data)
                markup.add(
                    types.InlineKeyboardButton(
                        get_message_text(language, "admin_reseller_row_compact").format(
                            status_icon=_admin_status_icon(status),
                            user_id=rid,
                            username_display=_username_display(language, data),
                            debt=_safe_float(data.get("debt", 0.0)),
                            total_paid=stats["total_paid"],
                            trust_limit=stats["trust_limit"],
                        ),
                        callback_data=f"admin_reseller_ui:detail:{rid}:{status}:{page}",
                    )
                )
            if total_pages > 1:
                nav_buttons = []
                if page > 0:
                    nav_buttons.append(
                        types.InlineKeyboardButton(
                            get_message_text(language, "admin_prev_page"),
                            callback_data=f"admin_reseller_ui:list:{status}:{page - 1}",
                        )
                    )
                nav_buttons.append(
                    types.InlineKeyboardButton(
                        get_message_text(language, "admin_page_indicator").format(page=page + 1, total=total_pages),
                        callback_data="admin_reseller_ui:noop",
                    )
                )
                if page < total_pages - 1:
                    nav_buttons.append(
                        types.InlineKeyboardButton(
                            get_message_text(language, "admin_next_page"),
                            callback_data=f"admin_reseller_ui:list:{status}:{page + 1}",
                        )
                    )
                markup.row(*nav_buttons)

    markup.add(types.InlineKeyboardButton(get_button_text(language, "cancel"), callback_data="reseller:cancel"))
    return markup


def _admin_view_context(admin_id):
    context = ADMIN_RESELLER_VIEW_CONTEXT.get(admin_id) or {}
    return {
        "return_status": context.get("return_status", ADMIN_RESELLER_DEFAULT_LIST_STATUS),
        "return_page": int(context.get("return_page", 0)),
    }


def _set_admin_view_context(admin_id, return_status, return_page):
    if return_status not in ADMIN_RESELLER_STATUS_ORDER:
        return_status = ADMIN_RESELLER_DEFAULT_LIST_STATUS
    ADMIN_RESELLER_VIEW_CONTEXT[admin_id] = {
        "return_status": return_status,
        "return_page": max(0, int(return_page)),
    }


def _render_admin_reseller_list(chat_id, message_id, admin_id, active_status, active_page):
    language = get_user_language(admin_id)
    resellers = get_all_resellers()
    grouped = _group_resellers(resellers)
    bot.edit_message_text(
        _build_admin_reseller_list_text(language, grouped),
        chat_id=chat_id,
        message_id=message_id,
        reply_markup=_build_admin_reseller_list_markup(language, grouped, active_status, active_page),
    )


def _build_admin_reseller_detail_text(language, reseller_id, reseller_data):
    debt = _safe_float((reseller_data or {}).get("debt", 0.0))
    status = (reseller_data or {}).get("status", "rejected")
    debt_state = get_message_text(language, _debt_state_label((reseller_data or {}).get("debt_state", "active")))
    stats = _reseller_financial_stats(reseller_data)
    return get_message_text(language, "admin_reseller_details_extended").format(
        user_id=_escape_markdown(reseller_id),
        username_display=_escape_markdown(_username_display(language, reseller_data)),
        status=_escape_markdown(_admin_status_label(language, status)),
        debt=format_usd_amount(debt),
        debt_state=_escape_markdown(debt_state),
        configs_count=stats["total_configs"],
        total_turnover=format_usd_amount(stats["total_turnover"]),
        total_paid=format_usd_amount(stats["total_paid"]),
        trust_limit=format_usd_amount(stats["trust_limit"]),
        average_config_value=format_usd_amount(stats["average_config_value"]),
        last_config_at=_escape_markdown(stats["last_config_at"]),
        created_at=_escape_markdown((reseller_data or {}).get("created_at", "N/A")),
        last_payment_at=_escape_markdown((reseller_data or {}).get("last_payment_at", "N/A")),
        debt_since=_escape_markdown((reseller_data or {}).get("debt_since", "N/A")),
    )


def _build_admin_reseller_detail_markup(language, reseller_id, reseller_data, return_status, return_page):
    status = (reseller_data or {}).get("status", "rejected")
    markup = types.InlineKeyboardMarkup(row_width=2)

    if status in ("pending", "rejected", "suspended"):
        markup.add(
            types.InlineKeyboardButton(
                get_message_text(language, "admin_action_approve"),
                callback_data=f"admin_reseller_ui:action:{reseller_id}:approve",
            )
        )
    if status in ("pending", "approved", "suspended"):
        markup.add(
            types.InlineKeyboardButton(
                get_message_text(language, "admin_action_reject"),
                callback_data=f"admin_reseller_ui:action:{reseller_id}:reject",
            )
        )
    if status == "approved":
        markup.add(
            types.InlineKeyboardButton(
                get_message_text(language, "admin_action_suspend"),
                callback_data=f"admin_reseller_ui:action:{reseller_id}:suspend",
            )
        )
    if status == "banned":
        markup.add(
            types.InlineKeyboardButton(
                get_message_text(language, "admin_action_unban"),
                callback_data=f"admin_reseller_ui:action:{reseller_id}:unban",
            )
        )
        markup.add(
            types.InlineKeyboardButton(
                get_message_text(language, "admin_action_cleanup_unpaid"),
                callback_data=f"admin_reseller_ui:cleanup:{reseller_id}:{return_status}:{return_page}",
            )
        )
    if status == "suspended":
        markup.add(
            types.InlineKeyboardButton(
                get_message_text(language, "admin_action_ban"),
                callback_data=f"admin_reseller_ui:action:{reseller_id}:ban",
            )
        )
    elif status != "banned":
        markup.add(
            types.InlineKeyboardButton(
                get_message_text(language, "admin_action_ban"),
                callback_data=f"admin_reseller_ui:action:{reseller_id}:ban",
            )
        )

    # Add delete button for rejected resellers
    if status == "rejected":
        markup.add(
            types.InlineKeyboardButton(
                get_message_text(language, "admin_action_delete"),
                callback_data=f"admin_reseller_ui:delete:{reseller_id}:{return_status}:{return_page}",
            )
        )

    markup.add(
        types.InlineKeyboardButton(
            get_message_text(language, "admin_action_adjust_debt"),
            callback_data=f"admin_reseller_ui:debt:{reseller_id}:{return_status}:{return_page}",
        ),
        types.InlineKeyboardButton(
            get_message_text(language, "admin_action_refresh"),
            callback_data=f"admin_reseller_ui:detail:{reseller_id}:{return_status}:{return_page}",
        ),
    )
    markup.add(
        types.InlineKeyboardButton(
            get_message_text(language, "admin_action_back_to_list"),
            callback_data=f"admin_reseller_ui:back:{return_status}:{return_page}",
        )
    )
    return markup


def _admin_reseller_action_label_key(action):
    return {
        "suspend": "admin_action_suspend",
        "ban": "admin_action_ban",
        "unban": "admin_action_unban",
    }.get(action)


def _reseller_status_notification_key(action):
    return {
        "suspend": "reseller_suspended_notification",
        "ban": "reseller_banned_notification",
        "unban": "reseller_unbanned_notification",
    }.get(action)


def _render_admin_reseller_action_confirm(call, reseller_id, target_action):
    language = get_user_language(call.from_user.id)
    reseller_data = get_reseller_data(reseller_id)
    label_key = _admin_reseller_action_label_key(target_action)
    if not reseller_data:
        bot.answer_callback_query(call.id, get_message_text(language, "admin_reseller_not_found"), show_alert=True)
        return
    if not label_key:
        bot.answer_callback_query(call.id, get_message_text(language, "admin_invalid_action"), show_alert=True)
        return

    action_label = get_message_text(language, label_key)
    msg = get_message_text(language, "admin_reseller_action_confirm").format(
        user_id=reseller_id,
        action=action_label,
    )
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton(
            get_message_text(language, "admin_reseller_action_confirm_notify"),
            callback_data=f"admin_reseller_ui:actionconfirm:{reseller_id}:{target_action}:notify",
        ),
        types.InlineKeyboardButton(
            get_message_text(language, "admin_reseller_action_confirm_silent"),
            callback_data=f"admin_reseller_ui:actionconfirm:{reseller_id}:{target_action}:silent",
        ),
    )
    context = _admin_view_context(call.from_user.id)
    markup.add(
        types.InlineKeyboardButton(
            get_message_text(language, "admin_debt_cancel"),
            callback_data=f"admin_reseller_ui:detail:{reseller_id}:{context['return_status']}:{context['return_page']}",
        )
    )
    bot.edit_message_text(
        msg,
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=markup,
        parse_mode="Markdown",
    )
    bot.answer_callback_query(call.id)


def _send_reseller_status_notification(reseller_id, action, fallback_language):
    if not str(reseller_id).isdigit():
        return
    key = _reseller_status_notification_key(action)
    if not key:
        return
    target_language = get_user_language(int(reseller_id)) if str(reseller_id).isdigit() else fallback_language
    try:
        bot.send_message(int(reseller_id), get_message_text(target_language, key))
    except Exception:
        pass


def _apply_admin_reseller_status_action(reseller_id, target_action):
    if target_action == "ban":
        return update_reseller_status(reseller_id, "banned")
    if target_action == "unban":
        return update_reseller_status(reseller_id, "suspended", suspended_reason=SUSPENDED_REASON_UNBAN_GRACE)
    if target_action == "suspend":
        return update_reseller_status(reseller_id, "suspended")
    return False


def _render_admin_reseller_detail(call, reseller_id, return_status, return_page):
    language = get_user_language(call.from_user.id)
    reseller_data = get_reseller_data(reseller_id)
    if not reseller_data:
        bot.answer_callback_query(call.id, get_message_text(language, "admin_reseller_not_found"), show_alert=True)
        _render_admin_reseller_list(call.message.chat.id, call.message.message_id, call.from_user.id, return_status, return_page)
        return

    _set_admin_view_context(call.from_user.id, return_status, return_page)
    detail_text = _build_admin_reseller_detail_text(language, reseller_id, reseller_data)
    detail_markup = _build_admin_reseller_detail_markup(language, reseller_id, reseller_data, return_status, return_page)
    bot.answer_callback_query(call.id)
    try:
        bot.edit_message_text(
            detail_text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=detail_markup,
            parse_mode="Markdown",
        )
    except Exception:
        logging.exception("Failed to render admin reseller detail with Markdown. reseller_id=%s", reseller_id)
        bot.edit_message_text(
            detail_text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=detail_markup,
        )


def _cleanup_no_payment_text(language):
    return get_message_text(language, "admin_cleanup_no_payment") or "No successful payment"


def _cleanup_item_line(candidate):
    username = _escape_markdown(candidate.get("username", "N/A"))
    customer_name = str(candidate.get("customer_name") or "").strip()
    customer_display = f" ({_escape_markdown(customer_name)})" if customer_name else ""
    timestamp = _escape_markdown(candidate.get("timestamp") or "N/A")
    price = format_usd_amount(_safe_float(candidate.get("price", 0.0)))
    return f"- `{username}`{customer_display} | {timestamp} | ${price}"


def _cleanup_item_lines(candidates):
    visible = list(candidates[:ADMIN_RESELLER_CLEANUP_MAX_ITEMS])
    lines = [_cleanup_item_line(candidate) for candidate in visible]
    omitted = max(0, len(candidates) - len(visible))
    if omitted:
        lines.append(f"... and {omitted} more")
    return "\n".join(lines)


def _build_admin_cleanup_preview_text(language, reseller_id, reseller_data, candidates):
    last_payment_at = (reseller_data or {}).get("last_payment_at") or _cleanup_no_payment_text(language)
    total_value = sum(_safe_float(candidate.get("price", 0.0)) for candidate in candidates)

    if not candidates:
        return (
            f"{get_message_text(language, 'admin_cleanup_preview_title')}\n\n"
            f"Reseller: `{_escape_markdown(reseller_id)}`\n"
            f"Last successful payment: `{_escape_markdown(last_payment_at)}`\n\n"
            f"{get_message_text(language, 'admin_cleanup_no_candidates')}"
        )

    return (
        f"{get_message_text(language, 'admin_cleanup_preview_title')}\n\n"
        f"Reseller: `{_escape_markdown(reseller_id)}`\n"
        f"Last successful payment: `{_escape_markdown(last_payment_at)}`\n"
        f"Matched users: *{len(candidates)}*\n"
        f"Total matched value: *${format_usd_amount(total_value)}*\n\n"
        f"*Users to remove from VPN:*\n{_cleanup_item_lines(candidates)}\n\n"
        f"{get_message_text(language, 'admin_cleanup_confirm_warning')}"
    )


def _build_admin_cleanup_result_text(language, reseller_id, result):
    def _section(title, items):
        if not items:
            return f"*{title}:* 0"
        return f"*{title}:* {len(items)}\n{_cleanup_item_lines(items)}"

    deleted = result.get("deleted", [])
    already_missing = result.get("already_missing", [])
    failed = result.get("failed", [])

    return (
        f"{get_message_text(language, 'admin_cleanup_result_title')}\n\n"
        f"Reseller: `{_escape_markdown(reseller_id)}`\n"
        f"VPN access removed: *{result.get('removed_count', 0)}*\n"
        f"History records tagged: *{result.get('tagged_count', result.get('removed_count', 0))}*\n"
        f"Removed value: *${format_usd_amount(result.get('removed_value', 0.0))}*\n"
        f"Remaining configs: *{result.get('remaining_configs', 0)}*\n"
        f"Remaining debt: *${format_usd_amount(result.get('remaining_debt', 0.0))}*\n\n"
        f"{_section('Deleted from VPN', deleted)}\n\n"
        f"{_section('Already missing, record tagged', already_missing)}\n\n"
        f"{_section('Failed, record kept', failed)}"
    )


def _render_admin_reseller_cleanup_preview(call, reseller_id, return_status, return_page):
    language = get_user_language(call.from_user.id)
    reseller_data = get_reseller_data(reseller_id)
    if not reseller_data:
        bot.answer_callback_query(call.id, get_message_text(language, "admin_reseller_not_found"), show_alert=True)
        _render_admin_reseller_list(call.message.chat.id, call.message.message_id, call.from_user.id, return_status, return_page)
        return
    if reseller_data.get("status") != "banned":
        bot.answer_callback_query(call.id, get_message_text(language, "admin_cleanup_banned_only"), show_alert=True)
        _render_admin_reseller_detail(call, reseller_id, return_status, return_page)
        return

    candidates = get_banned_reseller_cleanup_candidates(reseller_data)
    markup = types.InlineKeyboardMarkup(row_width=2)
    if candidates:
        markup.add(
            types.InlineKeyboardButton(
                get_message_text(language, "admin_cleanup_confirm_delete"),
                callback_data=f"admin_reseller_ui:cleanupconfirm:{reseller_id}:{return_status}:{return_page}",
            ),
            types.InlineKeyboardButton(
                get_message_text(language, "admin_debt_cancel"),
                callback_data=f"admin_reseller_ui:detail:{reseller_id}:{return_status}:{return_page}",
            ),
        )
    else:
        markup.add(
            types.InlineKeyboardButton(
                get_message_text(language, "admin_action_back_to_detail"),
                callback_data=f"admin_reseller_ui:detail:{reseller_id}:{return_status}:{return_page}",
            )
        )

    bot.edit_message_text(
        _build_admin_cleanup_preview_text(language, reseller_id, reseller_data, candidates),
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=markup,
        parse_mode="Markdown",
    )
    bot.answer_callback_query(call.id)


def _render_admin_reseller_cleanup_result(call, reseller_id, return_status, return_page):
    language = get_user_language(call.from_user.id)
    multi_api = MultiServerAPI()
    success, result = cleanup_banned_reseller_users(reseller_id, multi_api)
    if not success:
        bot.answer_callback_query(call.id, result.get("reason", get_message_text(language, "admin_invalid_action")), show_alert=True)
        _render_admin_reseller_detail(call, reseller_id, return_status, return_page)
        return

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton(
            get_message_text(language, "admin_action_back_to_detail"),
            callback_data=f"admin_reseller_ui:detail:{reseller_id}:{return_status}:{return_page}",
        )
    )
    bot.edit_message_text(
        _build_admin_cleanup_result_text(language, reseller_id, result),
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=markup,
        parse_mode="Markdown",
    )
    bot.answer_callback_query(call.id)


def _render_admin_debt_adjust(call, reseller_id, return_status, return_page):
    language = get_user_language(call.from_user.id)
    reseller_data = get_reseller_data(reseller_id)
    if not reseller_data:
        bot.answer_callback_query(call.id, get_message_text(language, "admin_reseller_not_found"), show_alert=True)
        _render_admin_reseller_list(call.message.chat.id, call.message.message_id, call.from_user.id, return_status, return_page)
        return

    _set_admin_view_context(call.from_user.id, return_status, return_page)
    current_debt = _safe_float(reseller_data.get("debt", 0.0))
    msg = get_message_text(language, "admin_debt_adjust_menu").format(
        user_id=reseller_id,
        current_debt=format_usd_amount(current_debt),
    )

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton(
            get_message_text(language, "admin_manual_payment_button"),
            callback_data=f"admin_reseller_ui:manualpay:{reseller_id}:{return_status}:{return_page}",
        )
    )
    markup.add(
        types.InlineKeyboardButton(get_message_text(language, "admin_debt_set_zero"), callback_data=f"admin_reseller_ui:debtquick:{reseller_id}:set:0"),
        types.InlineKeyboardButton(get_message_text(language, "admin_debt_plus_five"), callback_data=f"admin_reseller_ui:debtquick:{reseller_id}:add:5"),
    )
    markup.add(
        types.InlineKeyboardButton(get_message_text(language, "admin_debt_plus_ten"), callback_data=f"admin_reseller_ui:debtquick:{reseller_id}:add:10"),
        types.InlineKeyboardButton(get_message_text(language, "admin_debt_minus_five"), callback_data=f"admin_reseller_ui:debtquick:{reseller_id}:sub:5"),
    )
    markup.add(
        types.InlineKeyboardButton(get_message_text(language, "admin_debt_minus_ten"), callback_data=f"admin_reseller_ui:debtquick:{reseller_id}:sub:10"),
        types.InlineKeyboardButton(get_message_text(language, "admin_debt_custom_amount"), callback_data=f"admin_reseller_ui:debtquick:{reseller_id}:custom:0"),
    )
    markup.add(
        types.InlineKeyboardButton(
            get_message_text(language, "admin_action_back_to_detail"),
            callback_data=f"admin_reseller_ui:detail:{reseller_id}:{return_status}:{return_page}",
        )
    )

    bot.edit_message_text(
        msg,
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=markup,
    )


def _normalize_debt_amount(value):
    rounded = round(float(value), 2)
    if rounded < 0:
        return 0.0
    if rounded > ADMIN_RESELLER_MAX_DEBT:
        return ADMIN_RESELLER_MAX_DEBT
    return rounded


def _render_admin_debt_confirm(call, reseller_id, new_amount):
    language = get_user_language(call.from_user.id)
    reseller_data = get_reseller_data(reseller_id)
    if not reseller_data:
        bot.answer_callback_query(call.id, get_message_text(language, "admin_reseller_not_found"), show_alert=True)
        context = _admin_view_context(call.from_user.id)
        _render_admin_reseller_list(
            call.message.chat.id,
            call.message.message_id,
            call.from_user.id,
            context["return_status"],
            context["return_page"],
        )
        return

    context = _admin_view_context(call.from_user.id)
    old_debt = _safe_float(reseller_data.get("debt", 0.0))
    normalized = _normalize_debt_amount(new_amount)
    delta = normalized - old_debt
    msg = get_message_text(language, "admin_debt_confirm_message").format(
        user_id=reseller_id,
        old_debt=format_usd_amount(old_debt),
        new_debt=format_usd_amount(normalized),
        delta=f"{delta:+.2f}",
    )
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton(
            get_message_text(language, "admin_debt_confirm"),
            callback_data=f"admin_reseller_ui:debtconfirm:{reseller_id}:{normalized:.2f}",
        ),
        types.InlineKeyboardButton(
            get_message_text(language, "admin_debt_cancel"),
            callback_data=f"admin_reseller_ui:detail:{reseller_id}:{context['return_status']}:{context['return_page']}",
        ),
    )
    bot.edit_message_text(
        msg,
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=markup,
    )


def _manual_payment_record_id(reseller_id):
    return f"manual-settlement-{reseller_id}-{uuid.uuid4()}"


def _create_manual_payment_audit_record(reseller_id, admin_id, amount, notify_user):
    payment_id = _manual_payment_record_id(reseller_id)
    add_payment_record(payment_id, {
        "user_id": int(reseller_id) if str(reseller_id).isdigit() else reseller_id,
        "plan_gb": "Settlement",
        "days": 0,
        "payment_id": payment_id,
        "status": "completed",
        "type": "settlement",
        "payment_method": "Manual Admin",
        "price": amount,
        "settlement_amount": amount,
        "manual_recorded_by": int(admin_id),
        "manual_notify_user": bool(notify_user),
    })
    return payment_id


def _send_manual_payment_confirmation(chat_id, admin_id, reseller_id, amount):
    language = get_user_language(admin_id)
    context = _admin_view_context(admin_id)
    reseller_data = get_reseller_data(reseller_id)
    if not reseller_data:
        bot.send_message(chat_id, get_message_text(language, "admin_reseller_not_found"))
        return

    current_debt = _safe_float(reseller_data.get("debt", 0.0))
    valid, normalized, reason = validate_reseller_manual_payment_amount(amount, current_debt)
    if not valid:
        if reason == "over_debt":
            bot.send_message(
                chat_id,
                get_message_text(language, "admin_manual_payment_over_debt").format(
                    current_debt=format_usd_amount(current_debt)
                ),
            )
        else:
            bot.send_message(chat_id, get_message_text(language, "admin_manual_payment_invalid"))
        return

    remaining_debt = max(0.0, round(current_debt - normalized, 2))
    msg = get_message_text(language, "admin_manual_payment_confirm").format(
        user_id=reseller_id,
        amount=format_usd_amount(normalized),
        current_debt=format_usd_amount(current_debt),
        remaining_debt=format_usd_amount(remaining_debt),
    )
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton(
            get_message_text(language, "admin_manual_payment_confirm_notify"),
            callback_data=f"admin_reseller_ui:manualpayconfirm:{reseller_id}:{normalized:.2f}:notify",
        ),
        types.InlineKeyboardButton(
            get_message_text(language, "admin_manual_payment_confirm_silent"),
            callback_data=f"admin_reseller_ui:manualpayconfirm:{reseller_id}:{normalized:.2f}:silent",
        ),
        types.InlineKeyboardButton(
            get_message_text(language, "admin_debt_cancel"),
            callback_data=f"admin_reseller_ui:detail:{reseller_id}:{context['return_status']}:{context['return_page']}",
        ),
    )
    bot.send_message(chat_id, msg, reply_markup=markup)


@bot.message_handler(func=lambda message: message.from_user.id in ADMIN_RESELLER_DEBT_INPUT_STATE and ADMIN_RESELLER_DEBT_INPUT_STATE[message.from_user.id].get("state") == "waiting_manual_payment")
def handle_admin_manual_payment_input(message):
    if not is_admin(message.from_user.id):
        return

    language = get_user_language(message.from_user.id)
    state = ADMIN_RESELLER_DEBT_INPUT_STATE.get(message.from_user.id) or {}
    reseller_id = state.get("reseller_id")
    if not reseller_id:
        ADMIN_RESELLER_DEBT_INPUT_STATE.pop(message.from_user.id, None)
        return

    try:
        amount = float((message.text or "").strip())
    except ValueError:
        bot.reply_to(message, get_message_text(language, "admin_manual_payment_invalid"))
        return

    reseller_data = get_reseller_data(reseller_id)
    if not reseller_data:
        ADMIN_RESELLER_DEBT_INPUT_STATE.pop(message.from_user.id, None)
        bot.reply_to(message, get_message_text(language, "admin_reseller_not_found"))
        return

    current_debt = _safe_float(reseller_data.get("debt", 0.0))
    valid, normalized, reason = validate_reseller_manual_payment_amount(amount, current_debt)
    if not valid:
        if reason == "over_debt":
            bot.reply_to(
                message,
                get_message_text(language, "admin_manual_payment_over_debt").format(
                    current_debt=format_usd_amount(current_debt)
                ),
            )
        else:
            bot.reply_to(message, get_message_text(language, "admin_manual_payment_invalid"))
        return

    ADMIN_RESELLER_DEBT_INPUT_STATE.pop(message.from_user.id, None)
    _send_manual_payment_confirmation(message.chat.id, message.from_user.id, reseller_id, normalized)


@bot.message_handler(func=lambda message: message.from_user.id in ADMIN_RESELLER_DEBT_INPUT_STATE and ADMIN_RESELLER_DEBT_INPUT_STATE[message.from_user.id].get("state") == "waiting_custom_debt")
def handle_admin_custom_debt_input(message):
    if not is_admin(message.from_user.id):
        return

    language = get_user_language(message.from_user.id)
    state = ADMIN_RESELLER_DEBT_INPUT_STATE.get(message.from_user.id) or {}
    reseller_id = state.get("reseller_id")
    if not reseller_id:
        ADMIN_RESELLER_DEBT_INPUT_STATE.pop(message.from_user.id, None)
        return

    raw = (message.text or "").strip()
    try:
        new_amount = float(raw)
    except ValueError:
        bot.reply_to(message, get_message_text(language, "admin_debt_invalid_number"))
        return

    if new_amount < 0 or new_amount > ADMIN_RESELLER_MAX_DEBT:
        bot.reply_to(
            message,
            get_message_text(language, "admin_debt_invalid_range").format(
                min_value="0.00",
                max_value=f"{ADMIN_RESELLER_MAX_DEBT:.2f}",
            ),
        )
        return

    normalized = _normalize_debt_amount(new_amount)
    ADMIN_RESELLER_DEBT_INPUT_STATE.pop(message.from_user.id, None)
    reseller_data = get_reseller_data(reseller_id)
    if not reseller_data:
        bot.reply_to(message, get_message_text(language, "admin_reseller_not_found"))
        return

    old_debt = _safe_float(reseller_data.get("debt", 0.0))
    delta = normalized - old_debt
    context = _admin_view_context(message.from_user.id)
    confirmation = get_message_text(language, "admin_debt_confirm_message").format(
        user_id=reseller_id,
        old_debt=format_usd_amount(old_debt),
        new_debt=format_usd_amount(normalized),
        delta=f"{delta:+.2f}",
    )
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton(
            get_message_text(language, "admin_debt_confirm"),
            callback_data=f"admin_reseller_ui:debtconfirm:{reseller_id}:{normalized:.2f}",
        ),
        types.InlineKeyboardButton(
            get_message_text(language, "admin_debt_cancel"),
            callback_data=f"admin_reseller_ui:detail:{reseller_id}:{context['return_status']}:{context['return_page']}",
        ),
    )
    bot.send_message(message.chat.id, confirmation, reply_markup=markup)


@bot.message_handler(func=lambda message: any(
    message.text == get_button_text(get_user_language(message.from_user.id), "manage_resellers") for lang in BUTTON_TRANSLATIONS
))
def admin_manage_resellers(message):
    if not is_admin(message.from_user.id):
        return

    ADMIN_RESELLER_DEBT_INPUT_STATE.pop(message.from_user.id, None)
    _set_admin_view_context(message.from_user.id, ADMIN_RESELLER_DEFAULT_LIST_STATUS, 0)
    language = get_user_language(message.from_user.id)
    grouped = _group_resellers(get_all_resellers())
    bot.reply_to(
        message,
        _build_admin_reseller_list_text(language, grouped),
        reply_markup=_build_admin_reseller_list_markup(
            language,
            grouped,
            ADMIN_RESELLER_DEFAULT_LIST_STATUS,
            0,
        ),
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_reseller_ui:"))
def handle_admin_reseller_ui(call):
    if not is_admin(call.from_user.id):
        return

    language = get_user_language(call.from_user.id)
    parts = call.data.split(":")
    if len(parts) < 2:
        bot.answer_callback_query(call.id, get_message_text(language, "admin_invalid_action"), show_alert=True)
        return

    action = parts[1]

    if action == "noop":
        bot.answer_callback_query(call.id)
        return

    if action == "list":
        if len(parts) != 4:
            bot.answer_callback_query(call.id, get_message_text(language, "admin_invalid_action"), show_alert=True)
            return
        status = parts[2]
        if status not in ADMIN_RESELLER_STATUS_ORDER:
            bot.answer_callback_query(call.id, get_message_text(language, "admin_invalid_action"), show_alert=True)
            return
        try:
            page = int(parts[3])
        except ValueError:
            bot.answer_callback_query(call.id, get_message_text(language, "admin_invalid_action"), show_alert=True)
            return
        _set_admin_view_context(call.from_user.id, status, max(page, 0))
        _render_admin_reseller_list(call.message.chat.id, call.message.message_id, call.from_user.id, status, page)
        return

    if action == "detail":
        if len(parts) != 5:
            bot.answer_callback_query(call.id, get_message_text(language, "admin_invalid_action"), show_alert=True)
            return
        reseller_id = parts[2]
        return_status = parts[3]
        try:
            return_page = int(parts[4])
        except ValueError:
            bot.answer_callback_query(call.id, get_message_text(language, "admin_invalid_action"), show_alert=True)
            return
        _render_admin_reseller_detail(call, reseller_id, return_status, return_page)
        return

    if action == "back":
        if len(parts) != 4:
            bot.answer_callback_query(call.id, get_message_text(language, "admin_invalid_action"), show_alert=True)
            return
        return_status = parts[2]
        try:
            return_page = int(parts[3])
        except ValueError:
            bot.answer_callback_query(call.id, get_message_text(language, "admin_invalid_action"), show_alert=True)
            return
        _set_admin_view_context(call.from_user.id, return_status, return_page)
        _render_admin_reseller_list(call.message.chat.id, call.message.message_id, call.from_user.id, return_status, return_page)
        return

    if action == "action":
        if len(parts) != 4:
            bot.answer_callback_query(call.id, get_message_text(language, "admin_invalid_action"), show_alert=True)
            return
        reseller_id = parts[2]
        target_action = parts[3]
        reseller_data = get_reseller_data(reseller_id)
        if not reseller_data:
            bot.answer_callback_query(call.id, get_message_text(language, "admin_reseller_not_found"), show_alert=True)
            context = _admin_view_context(call.from_user.id)
            _render_admin_reseller_list(
                call.message.chat.id,
                call.message.message_id,
                call.from_user.id,
                context["return_status"],
                context["return_page"],
            )
            return

        if target_action == "approve":
            update_reseller_status(reseller_id, "approved")
            target_language = get_user_language(int(reseller_id)) if str(reseller_id).isdigit() else language
            try:
                bot.send_message(int(reseller_id), get_message_text(target_language, "reseller_approved_notification"))
            except:
                pass
        elif target_action == "reject":
            update_reseller_status(reseller_id, "rejected")
            target_language = get_user_language(int(reseller_id)) if str(reseller_id).isdigit() else language
            try:
                bot.send_message(int(reseller_id), get_message_text(target_language, "reseller_rejected_notification"))
            except:
                pass
        elif target_action in {"ban", "unban", "suspend"}:
            _render_admin_reseller_action_confirm(call, reseller_id, target_action)
            return
        else:
            bot.answer_callback_query(call.id, get_message_text(language, "admin_invalid_action"), show_alert=True)
            return

        context = _admin_view_context(call.from_user.id)
        _render_admin_reseller_detail(call, reseller_id, context["return_status"], context["return_page"])
        return

    if action == "actionconfirm":
        if len(parts) != 5:
            bot.answer_callback_query(call.id, get_message_text(language, "admin_invalid_action"), show_alert=True)
            return
        reseller_id = parts[2]
        target_action = parts[3]
        delivery = parts[4]
        if target_action not in {"ban", "unban", "suspend"} or delivery not in {"notify", "silent"}:
            bot.answer_callback_query(call.id, get_message_text(language, "admin_invalid_action"), show_alert=True)
            return
        if not get_reseller_data(reseller_id):
            bot.answer_callback_query(call.id, get_message_text(language, "admin_reseller_not_found"), show_alert=True)
            context = _admin_view_context(call.from_user.id)
            _render_admin_reseller_list(
                call.message.chat.id,
                call.message.message_id,
                call.from_user.id,
                context["return_status"],
                context["return_page"],
            )
            return
        if not _apply_admin_reseller_status_action(reseller_id, target_action):
            bot.answer_callback_query(call.id, get_message_text(language, "admin_invalid_action"), show_alert=True)
            return
        if delivery == "notify":
            _send_reseller_status_notification(reseller_id, target_action, language)

        context = _admin_view_context(call.from_user.id)
        _render_admin_reseller_detail(call, reseller_id, context["return_status"], context["return_page"])
        return

    if action == "debt":
        if len(parts) != 5:
            bot.answer_callback_query(call.id, get_message_text(language, "admin_invalid_action"), show_alert=True)
            return
        reseller_id = parts[2]
        return_status = parts[3]
        try:
            return_page = int(parts[4])
        except ValueError:
            bot.answer_callback_query(call.id, get_message_text(language, "admin_invalid_action"), show_alert=True)
            return
        _render_admin_debt_adjust(call, reseller_id, return_status, return_page)
        return

    if action == "manualpay":
        if len(parts) != 5:
            bot.answer_callback_query(call.id, get_message_text(language, "admin_invalid_action"), show_alert=True)
            return
        reseller_id = parts[2]
        return_status = parts[3]
        try:
            return_page = int(parts[4])
        except ValueError:
            bot.answer_callback_query(call.id, get_message_text(language, "admin_invalid_action"), show_alert=True)
            return

        reseller_data = get_reseller_data(reseller_id)
        if not reseller_data:
            bot.answer_callback_query(call.id, get_message_text(language, "admin_reseller_not_found"), show_alert=True)
            return

        current_debt = _safe_float(reseller_data.get("debt", 0.0))
        if current_debt <= 0:
            bot.answer_callback_query(call.id, get_message_text(language, "debt_cleared"), show_alert=True)
            return

        _set_admin_view_context(call.from_user.id, return_status, return_page)
        ADMIN_RESELLER_DEBT_INPUT_STATE[call.from_user.id] = {
            "state": "waiting_manual_payment",
            "reseller_id": reseller_id,
            "return_status": return_status,
            "return_page": return_page,
        }
        bot.send_message(
            call.message.chat.id,
            get_message_text(language, "admin_manual_payment_prompt").format(
                user_id=reseller_id,
                current_debt=format_usd_amount(current_debt),
            ),
        )
        bot.answer_callback_query(call.id)
        return

    if action == "manualpayconfirm":
        if len(parts) != 5:
            bot.answer_callback_query(call.id, get_message_text(language, "admin_invalid_action"), show_alert=True)
            return
        reseller_id = parts[2]
        try:
            amount = float(parts[3])
        except ValueError:
            bot.answer_callback_query(call.id, get_message_text(language, "admin_invalid_action"), show_alert=True)
            return
        notify_user = parts[4] == "notify"
        if parts[4] not in {"notify", "silent"}:
            bot.answer_callback_query(call.id, get_message_text(language, "admin_invalid_action"), show_alert=True)
            return

        reseller_data = get_reseller_data(reseller_id)
        if not reseller_data:
            bot.answer_callback_query(call.id, get_message_text(language, "admin_reseller_not_found"), show_alert=True)
            return

        current_debt = _safe_float(reseller_data.get("debt", 0.0))
        valid, normalized, reason = validate_reseller_manual_payment_amount(amount, current_debt)
        if not valid:
            if reason == "over_debt":
                bot.answer_callback_query(
                    call.id,
                    get_message_text(language, "admin_manual_payment_over_debt").format(
                        current_debt=format_usd_amount(current_debt)
                    ),
                    show_alert=True,
                )
            else:
                bot.answer_callback_query(call.id, get_message_text(language, "admin_manual_payment_invalid"), show_alert=True)
            return

        success, new_debt = apply_reseller_payment(reseller_id, normalized)
        if not success:
            bot.answer_callback_query(call.id, get_message_text(language, "admin_reseller_not_found"), show_alert=True)
            return

        payment_id = _create_manual_payment_audit_record(reseller_id, call.from_user.id, normalized, notify_user)
        if notify_user and str(reseller_id).isdigit():
            try:
                user_language = get_user_language(int(reseller_id))
                bot.send_message(
                    int(reseller_id),
                    get_message_text(user_language, "reseller_manual_payment_recorded").format(
                        amount=format_usd_amount(normalized),
                        remaining_debt=format_usd_amount(new_debt),
                    ),
                )
            except Exception:
                pass

        bot.answer_callback_query(
            call.id,
            get_message_text(language, "admin_manual_payment_success").format(
                amount=format_usd_amount(normalized),
                remaining_debt=format_usd_amount(new_debt),
                payment_id=payment_id,
            ),
            show_alert=True,
        )
        context = _admin_view_context(call.from_user.id)
        _render_admin_reseller_detail(call, reseller_id, context["return_status"], context["return_page"])
        return

    if action == "debtquick":
        if len(parts) != 5:
            bot.answer_callback_query(call.id, get_message_text(language, "admin_invalid_action"), show_alert=True)
            return
        reseller_id = parts[2]
        op = parts[3]
        try:
            value = float(parts[4])
        except ValueError:
            bot.answer_callback_query(call.id, get_message_text(language, "admin_invalid_action"), show_alert=True)
            return

        reseller_data = get_reseller_data(reseller_id)
        if not reseller_data:
            bot.answer_callback_query(call.id, get_message_text(language, "admin_reseller_not_found"), show_alert=True)
            return

        current = _safe_float(reseller_data.get("debt", 0.0))
        if op == "set":
            candidate = value
        elif op == "add":
            candidate = current + value
        elif op == "sub":
            candidate = current - value
        elif op == "custom":
            context = _admin_view_context(call.from_user.id)
            ADMIN_RESELLER_DEBT_INPUT_STATE[call.from_user.id] = {
                "state": "waiting_custom_debt",
                "reseller_id": reseller_id,
                "return_status": context["return_status"],
                "return_page": context["return_page"],
            }
            bot.send_message(
                call.message.chat.id,
                get_message_text(language, "admin_debt_custom_prompt").format(
                    user_id=reseller_id,
                    min_value="0.00",
                    max_value=f"{ADMIN_RESELLER_MAX_DEBT:.2f}",
                ),
            )
            bot.answer_callback_query(call.id)
            return
        else:
            bot.answer_callback_query(call.id, get_message_text(language, "admin_invalid_action"), show_alert=True)
            return

        candidate = _normalize_debt_amount(candidate)
        _render_admin_debt_confirm(call, reseller_id, candidate)
        return

    if action == "debtconfirm":
        if len(parts) != 4:
            bot.answer_callback_query(call.id, get_message_text(language, "admin_invalid_action"), show_alert=True)
            return
        reseller_id = parts[2]
        try:
            new_amount = float(parts[3])
        except ValueError:
            bot.answer_callback_query(call.id, get_message_text(language, "admin_invalid_action"), show_alert=True)
            return
        if new_amount < 0 or new_amount > ADMIN_RESELLER_MAX_DEBT:
            bot.answer_callback_query(
                call.id,
                get_message_text(language, "admin_debt_invalid_range").format(
                    min_value="0.00",
                    max_value=f"{ADMIN_RESELLER_MAX_DEBT:.2f}",
                ),
                show_alert=True,
            )
            return

        reseller_data = get_reseller_data(reseller_id)
        if not reseller_data:
            bot.answer_callback_query(call.id, get_message_text(language, "admin_reseller_not_found"), show_alert=True)
            context = _admin_view_context(call.from_user.id)
            _render_admin_reseller_list(
                call.message.chat.id,
                call.message.message_id,
                call.from_user.id,
                context["return_status"],
                context["return_page"],
            )
            return

        set_reseller_debt(reseller_id, _normalize_debt_amount(new_amount))
        context = _admin_view_context(call.from_user.id)
        _render_admin_reseller_detail(call, reseller_id, context["return_status"], context["return_page"])
        return

    if action == "cleanup":
        if len(parts) != 5:
            bot.answer_callback_query(call.id, get_message_text(language, "admin_invalid_action"), show_alert=True)
            return
        reseller_id = parts[2]
        return_status = parts[3]
        try:
            return_page = int(parts[4])
        except ValueError:
            bot.answer_callback_query(call.id, get_message_text(language, "admin_invalid_action"), show_alert=True)
            return
        _render_admin_reseller_cleanup_preview(call, reseller_id, return_status, return_page)
        return

    if action == "cleanupconfirm":
        if len(parts) != 5:
            bot.answer_callback_query(call.id, get_message_text(language, "admin_invalid_action"), show_alert=True)
            return
        reseller_id = parts[2]
        return_status = parts[3]
        try:
            return_page = int(parts[4])
        except ValueError:
            bot.answer_callback_query(call.id, get_message_text(language, "admin_invalid_action"), show_alert=True)
            return
        _render_admin_reseller_cleanup_result(call, reseller_id, return_status, return_page)
        return

    if action == "delete":
        if len(parts) != 5:
            bot.answer_callback_query(call.id, get_message_text(language, "admin_invalid_action"), show_alert=True)
            return
        reseller_id = parts[2]
        return_status = parts[3]
        try:
            return_page = int(parts[4])
        except ValueError:
            bot.answer_callback_query(call.id, get_message_text(language, "admin_invalid_action"), show_alert=True)
            return

        reseller_data = get_reseller_data(reseller_id)
        if not reseller_data:
            bot.answer_callback_query(call.id, get_message_text(language, "admin_reseller_not_found"), show_alert=True)
            _render_admin_reseller_list(call.message.chat.id, call.message.message_id, call.from_user.id, return_status, return_page)
            return

        # Show confirmation dialog
        msg = get_message_text(language, "admin_delete_confirm").format(user_id=reseller_id)
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton(
                get_button_text(language, "yes"),
                callback_data=f"admin_reseller_ui:deleteconfirm:{reseller_id}:{return_status}:{return_page}",
            ),
            types.InlineKeyboardButton(
                get_button_text(language, "no"),
                callback_data=f"admin_reseller_ui:detail:{reseller_id}:{return_status}:{return_page}",
            ),
        )
        bot.edit_message_text(
            msg,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=markup,
            parse_mode="Markdown",
        )
        return

    if action == "deleteconfirm":
        if len(parts) != 5:
            bot.answer_callback_query(call.id, get_message_text(language, "admin_invalid_action"), show_alert=True)
            return
        reseller_id = parts[2]
        return_status = parts[3]
        try:
            return_page = int(parts[4])
        except ValueError:
            bot.answer_callback_query(call.id, get_message_text(language, "admin_invalid_action"), show_alert=True)
            return

        from utils.reseller import delete_reseller
        success = delete_reseller(reseller_id)
        if success:
            bot.edit_message_text(
                get_message_text(language, "admin_reseller_deleted").format(user_id=reseller_id),
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
            )
            # Show the list again after a short delay or let admin navigate back
            _render_admin_reseller_list(call.message.chat.id, call.message.message_id, call.from_user.id, return_status, return_page)
        else:
            bot.answer_callback_query(call.id, get_message_text(language, "admin_reseller_not_found"), show_alert=True)
            _render_admin_reseller_list(call.message.chat.id, call.message.message_id, call.from_user.id, return_status, return_page)
        return

    bot.answer_callback_query(call.id, get_message_text(language, "admin_invalid_action"), show_alert=True)
