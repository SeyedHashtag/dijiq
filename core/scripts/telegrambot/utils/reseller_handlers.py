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
    get_all_resellers, set_reseller_debt, DEBT_WARNING_THRESHOLD
)
from utils.edit_plans import load_plans
from utils.api_client import APIClient
from utils.payments import CryptoPayment
from utils.payment_records import add_payment_record
from utils.purchase_plan import user_data
from utils.username_utils import (
    allocate_username,
    build_user_note,
    extract_existing_usernames,
    format_username_timestamp,
)

def _get_approved_reseller_data(user_id):
    reseller_data = get_reseller_data(user_id)
    if not reseller_data or reseller_data.get('status') != 'approved':
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
    api_client = APIClient()
    users = api_client.get_users()
    if users is None:
        return False

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

    if isinstance(users, dict):
        return any(_is_active_paid(username, config_data or {}) for username, config_data in users.items())

    if isinstance(users, list):
        for config_data in users:
            username = config_data.get('username') if isinstance(config_data, dict) else None
            if _is_active_paid(username, config_data or {}):
                return True

    return False


def _create_reseller_username(api_client, user_id):
    users = api_client.get_users()
    return allocate_username("r", user_id, extract_existing_usernames(users))


def _create_reseller_user_with_note(api_client, user_id, gb, days, chosen_username):
    username = _create_reseller_username(api_client, user_id)
    note_payload = build_user_note(
        username=username,
        traffic_limit=gb,
        expiration_days=days,
        unlimited=False,
        note_text=chosen_username,
        timestamp=format_username_timestamp(),
    )
    result = api_client.add_user(username, int(gb), int(days), note=note_payload)
    if result is None:
        result = api_client.add_user(username, int(gb), int(days))
        if result is not None:
            logging.getLogger("dijiq.usernames").warning(
                "Created reseller user without note fallback. reseller_id=%s username=%s",
                user_id,
                username,
            )
    return username, result

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
        intro = get_message_text(language, "reseller_intro").replace("${debt}", f"${debt:.2f}")
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

    if current_status == 'approved':
        bot.answer_callback_query(call.id, "You are already an approved reseller.")
        return
    if current_status == 'pending':
        bot.answer_callback_query(call.id, get_message_text(language, "reseller_status_pending"))
        return
    if current_status == 'banned':
        bot.answer_callback_query(call.id, get_message_text(language, "reseller_access_banned"))
        return
    if not _has_active_purchased_config(user_id):
        bot.answer_callback_query(call.id, get_message_text(language, "reseller_requires_active_paid_config"), show_alert=True)
        return
    
    # Update status to pending
    if not update_reseller_status(user_id, 'pending', telegram_username=call.from_user.username):
        bot.answer_callback_query(call.id, "Failed to submit request. Please try again.")
        return
    
    bot.edit_message_text(
        get_message_text(language, "reseller_request_sent"),
        chat_id=call.message.chat.id,
        message_id=call.message.message_id
    )
    
    # Notify Admins
    username = call.from_user.username or "Unknown"
    notification = get_message_text(language, "reseller_request_notification").format(user_id=user_id, username=username)
    
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
    reseller_data = _get_approved_reseller_data(user_id)
    if not reseller_data:
        bot.answer_callback_query(call.id, "Reseller access required.")
        return
    if _is_reseller_suspended(reseller_data):
        debt = float(reseller_data.get('debt', 0.0))
        unlock_amount = max(0.0, debt - DEBT_WARNING_THRESHOLD)
        bot.answer_callback_query(
            call.id,
            get_message_text(language, "reseller_suspended_due_debt").format(debt=debt, unlock_amount=unlock_amount)
        )
        return
    
    plans = load_plans()
    sorted_plans = sorted(plans.items(), key=lambda x: int(x[0]))
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    for gb, details in sorted_plans:
        original_price = float(details['price'])
        discounted_price = original_price * 0.8
        button_text = f"{gb} GB - ${discounted_price:.2f} (20% OFF) - {details['days']} days"
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
    reseller_data = _get_approved_reseller_data(user_id)
    if not reseller_data:
        bot.answer_callback_query(call.id, "Reseller access required.")
        return
    if _is_reseller_suspended(reseller_data):
        debt = float(reseller_data.get('debt', 0.0))
        unlock_amount = max(0.0, debt - DEBT_WARNING_THRESHOLD)
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
    original_price = float(plan['price'])
    price = original_price * 0.8  # 20% discount for resellers
    days = plan['days']

    current_debt = float(reseller_data.get('debt', 0.0))
    projected_debt = current_debt + price
    if projected_debt >= DEBT_WARNING_THRESHOLD:
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton(get_message_text(language, "continue_action"), callback_data=f"reseller:confirm_buy:{gb}"))
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
    
    # Prompt for customer username
    user_data[user_id] = {
        'state': 'waiting_reseller_username',
        'gb': gb,
        'days': days,
        'price': price
    }
    
    bot.edit_message_text(
        get_message_text(language, "enter_reseller_customer_username"),
        chat_id=call.message.chat.id,
        message_id=call.message.message_id
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("reseller:confirm_buy:"))
def handle_reseller_confirm_buy(call):
    user_id = call.from_user.id
    language = get_user_language(user_id)
    reseller_data = _get_approved_reseller_data(user_id)
    if not reseller_data:
        bot.answer_callback_query(call.id, "Reseller access required.")
        return
    if _is_reseller_suspended(reseller_data):
        debt = float(reseller_data.get('debt', 0.0))
        unlock_amount = max(0.0, debt - DEBT_WARNING_THRESHOLD)
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
    original_price = float(plan['price'])
    price = original_price * 0.8
    days = plan['days']

    user_data[user_id] = {
        'state': 'waiting_reseller_username',
        'gb': gb,
        'days': days,
        'price': price
    }

    bot.edit_message_text(
        get_message_text(language, "enter_reseller_customer_username"),
        chat_id=call.message.chat.id,
        message_id=call.message.message_id
    )

@bot.message_handler(func=lambda message: message.from_user.id in user_data and user_data[message.from_user.id].get('state') == 'waiting_reseller_username')
def handle_reseller_username_input(message):
    user_id = message.from_user.id
    language = get_user_language(user_id)
    reseller_data = _get_approved_reseller_data(user_id)
    if not reseller_data:
        if user_id in user_data:
            del user_data[user_id]
        bot.reply_to(message, "Your reseller access is not active.")
        return
    if _is_reseller_suspended(reseller_data):
        debt = float(reseller_data.get('debt', 0.0))
        unlock_amount = max(0.0, debt - DEBT_WARNING_THRESHOLD)
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
    
    # Create user
    api_client = APIClient()
    username, result = _create_reseller_user_with_note(
        api_client,
        user_id,
        gb,
        days,
        chosen_username,
    )
    
    if result:
        # Add debt
        config_data = {
            "username": username,
            "gb": gb,
            "days": days,
            "price": price
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
            price=price,
            sub_url=sub_url,
            ipv4_info=ipv4_info
        )
        
        if sub_url != 'N/A':
            qr = qrcode.make(sub_url)
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
    reseller_data = _get_approved_reseller_data(user_id)
    if not reseller_data:
        bot.answer_callback_query(call.id, "Reseller access required.")
        return
    debt = float(reseller_data.get('debt', 0.0))
    debt_state = reseller_data.get('debt_state', 'active')
    debt_state_text = get_message_text(language, _debt_state_label(debt_state))
    debt_since = reseller_data.get('debt_since') or 'N/A'
    last_payment_at = reseller_data.get('last_payment_at') or 'N/A'
    unlock_amount = max(0.0, debt - DEBT_WARNING_THRESHOLD) if debt_state == 'suspended' else 0.0
    
    markup = types.InlineKeyboardMarkup()
    if debt > 0:
        markup.add(types.InlineKeyboardButton(get_button_text(language, "settle_debt"), callback_data=f"reseller:settle:{debt:.2f}"))
    markup.add(types.InlineKeyboardButton(get_button_text(language, "cancel"), callback_data="reseller:cancel"))
    
    bot.edit_message_text(
        (
            f"{get_message_text(language, 'current_debt').replace('${debt}', f'${debt:.2f}')}\n"
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
    reseller_data = _get_approved_reseller_data(user_id)
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
    card_to_card_configured = os.getenv('CARD_TO_CARD_NUMBER')
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    if crypto_configured:
        markup.add(types.InlineKeyboardButton(get_button_text(language, "crypto"), callback_data=f"reseller:pay:crypto:{amount:.2f}"))
    if card_to_card_configured:
        markup.add(types.InlineKeyboardButton(get_button_text(language, "card_to_card"), callback_data=f"reseller:pay:card:{amount:.2f}"))
        
    markup.add(types.InlineKeyboardButton(get_button_text(language, "cancel"), callback_data="reseller:cancel"))
    
    bot.edit_message_text(
        get_message_text(language, "select_payment_method"),
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("reseller:pay:"))
def handle_reseller_payment(call):
    user_id = call.from_user.id
    language = get_user_language(user_id)
    reseller_data = _get_approved_reseller_data(user_id)
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
        payment_handler = CryptoPayment()
        payment_response = payment_handler.create_payment(
            amount_to_pay, "Settlement", user_id
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
                'price': amount_to_pay,
                'days': 0,
                'payment_id': payment_id,
                'status': 'pending',
                'type': 'settlement',
                'payment_method': 'Crypto'
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
            bot.send_photo(call.message.chat.id, bio, caption=get_message_text(language, "payment_instructions").format(price=amount_to_pay, payment_url=payment_url, payment_id=payment_id), reply_markup=markup)

    elif method == 'card':
        # Card to card logic
        exchange_rate = os.getenv('EXCHANGE_RATE', '1')
        card_number = os.getenv('CARD_TO_CARD_NUMBER')
        price_in_tomans = amount_to_pay * float(exchange_rate)
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(get_button_text(language, "cancel"), callback_data="reseller:cancel"))
        
        bot.edit_message_text(
             get_message_text(language, "card_to_card_payment").format(price=price_in_tomans, card_number=card_number),
             chat_id=call.message.chat.id,
             message_id=call.message.message_id,
             parse_mode="Markdown",
             reply_markup=markup
        )
        
        user_data[user_id] = {
            'state': 'waiting_receipt',
            'plan_gb': 'Settlement',
            'price': amount_to_pay,
            'type': 'settlement',
            'cancel_callback': 'reseller:cancel'
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
    reseller_data = _get_approved_reseller_data(user_id)
    
    if not reseller_data:
        bot.answer_callback_query(call.id, "Reseller access required.")
        return

    configs = reseller_data.get('configs', [])
    total_configs = len(configs)
    
    total_value = sum(float(c.get('price', 0)) for c in configs)
    current_debt = float(reseller_data.get('debt', 0.0))
    total_paid = total_value - current_debt
    
    msg = get_message_text(language, "reseller_stats_message").format(
        user_id=user_id,
        joined_date=reseller_data.get('created_at', 'N/A'),
        total_configs=total_configs,
        total_value=f"{total_value:.2f}",
        total_paid=f"{total_paid:.2f}",
        current_debt=f"{current_debt:.2f}"
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

@bot.callback_query_handler(func=lambda call: call.data.startswith("reseller:my_customers:"))
def handle_reseller_my_customers(call):
    user_id = call.from_user.id
    language = get_user_language(user_id)
    reseller_data = _get_approved_reseller_data(user_id)

    if not reseller_data:
        bot.answer_callback_query(call.id, "Reseller access required.")
        return

    try:
        page = int(call.data.split(":")[2])
    except (IndexError, ValueError):
        page = 0

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

    total_pages = max(1, (total + RESELLER_CUSTOMERS_PAGE_SIZE - 1) // RESELLER_CUSTOMERS_PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))

    start = page * RESELLER_CUSTOMERS_PAGE_SIZE
    end = start + RESELLER_CUSTOMERS_PAGE_SIZE
    page_configs = configs[start:end]

    entries_lines = []
    for i, cfg in enumerate(page_configs, start=start + 1):
        username = cfg.get('username', 'N/A')
        gb = cfg.get('gb', '?')
        days = cfg.get('days', '?')
        price = cfg.get('price', 0)
        timestamp = cfg.get('timestamp', 'N/A')
        entries_lines.append(
            f"{i}. `{username}`\n"
            f"   📊 {gb} GB | 📅 {days}d | 💰 ${float(price):.2f}\n"
            f"   🕒 {timestamp}"
        )

    entries_text = "\n\n".join(entries_lines)

    msg = get_message_text(language, "reseller_customers_list_header").format(
        total=total,
        page=page + 1,
        total_pages=total_pages,
        entries=entries_text
    )

    markup = types.InlineKeyboardMarkup(row_width=1)
    # Add numbered buttons for each customer on this page in a single row
    row_buttons = []
    for i, cfg in enumerate(page_configs, start=start + 1):
        username = cfg.get('username', 'N/A')
        row_buttons.append(types.InlineKeyboardButton(f"{i}", callback_data=f"reseller:cfg:{username}:{page}"))
    if row_buttons:
        markup.row(*row_buttons)

    # Navigation row
    nav_buttons = []
    if page > 0:
        nav_buttons.append(
            types.InlineKeyboardButton("⬅️", callback_data=f"reseller:my_customers:{page - 1}")
        )
    nav_buttons.append(
        types.InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="reseller:my_customers_noop")
    )
    if page < total_pages - 1:
        nav_buttons.append(
            types.InlineKeyboardButton("➡️", callback_data=f"reseller:my_customers:{page + 1}")
        )
    if nav_buttons:
        markup.row(*nav_buttons)
    markup.add(types.InlineKeyboardButton(get_button_text(language, "cancel"), callback_data="reseller:cancel"))

    if call.message.photo or call.message.document or call.message.sticker:
        # The current message is a media message; delete it and send a fresh text message
        try:
            bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)
        except Exception:
            pass
        bot.send_message(
            call.message.chat.id,
            msg,
            reply_markup=markup,
            parse_mode="Markdown"
        )
    else:
        bot.edit_message_text(
            msg,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=markup,
            parse_mode="Markdown"
        )

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

    # Parse callback data: reseller:cfg:{username}:{page}
    parts = call.data.split(":")
    if len(parts) < 4:
        bot.answer_callback_query(call.id, "Invalid request.")
        return

    username = parts[2]
    try:
        return_page = int(parts[3])
    except (ValueError, IndexError):
        return_page = 0

    bot.answer_callback_query(call.id)

    # Fetch live config data from API
    api_client = APIClient()
    user_config = api_client.get_user(username)

    back_markup = types.InlineKeyboardMarkup()
    back_markup.add(
        types.InlineKeyboardButton(
            get_button_text(language, "reseller_back_to_customers"),
            callback_data=f"reseller:my_customers:{return_page}"
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
        message_text = f"❌ **Configuration expired/blocked**\n{formatted_details}"
        bot.edit_message_text(
            message_text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=back_markup,
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
    caption += f"Subscription URL:\n`{sub_url}`"

    try:
        qr_code = qrcode.make(sub_url)
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


# Admin Management Handlers

ADMIN_RESELLER_STATUS_ORDER = ["pending", "suspended", "banned", "approved", "rejected"]
ADMIN_RESELLER_PAGE_SIZE = 8
ADMIN_RESELLER_MAX_DEBT = 100000.0
ADMIN_RESELLER_DEFAULT_LIST_STATUS = "pending"
ADMIN_RESELLER_DEBT_INPUT_STATE = {}
ADMIN_RESELLER_VIEW_CONTEXT = {}


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


def _username_display(language, reseller_data):
    username = str((reseller_data or {}).get("telegram_username") or "").strip().lstrip("@")
    if username:
        return f"@{username}"
    return get_message_text(language, "admin_username_unknown")


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


def _paginate(items, page, page_size=ADMIN_RESELLER_PAGE_SIZE):
    if not items:
        return [], 1, 0
    total_pages = (len(items) + page_size - 1) // page_size
    page = max(0, min(page, total_pages - 1))
    start = page * page_size
    end = start + page_size
    return items[start:end], total_pages, page


def _build_admin_reseller_list_text(language, grouped):
    lines = [get_message_text(language, "admin_resellers_list_grouped")]
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

            if not visible:
                markup.add(
                    types.InlineKeyboardButton(
                        get_message_text(language, "admin_reseller_no_entries"),
                        callback_data="admin_reseller_ui:noop",
                    )
                )
            else:
                for rid, data in visible:
                    markup.add(
                        types.InlineKeyboardButton(
                            get_message_text(language, "admin_reseller_row_compact").format(
                                status_icon=_admin_status_icon(status),
                                user_id=rid,
                                username_display=_username_display(language, data),
                                debt=_safe_float(data.get("debt", 0.0)),
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
    configs_count = len((reseller_data or {}).get("configs", []))
    return get_message_text(language, "admin_reseller_details_extended").format(
        user_id=reseller_id,
        username_display=_username_display(language, reseller_data),
        status=_admin_status_label(language, status),
        debt=f"{debt:.2f}",
        debt_state=debt_state,
        configs_count=configs_count,
        created_at=(reseller_data or {}).get("created_at", "N/A"),
        last_payment_at=(reseller_data or {}).get("last_payment_at", "N/A"),
        debt_since=(reseller_data or {}).get("debt_since", "N/A"),
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
    if status == "banned":
        markup.add(
            types.InlineKeyboardButton(
                get_message_text(language, "admin_action_unban"),
                callback_data=f"admin_reseller_ui:action:{reseller_id}:unban",
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


def _render_admin_reseller_detail(call, reseller_id, return_status, return_page):
    language = get_user_language(call.from_user.id)
    reseller_data = get_reseller_data(reseller_id)
    if not reseller_data:
        bot.answer_callback_query(call.id, get_message_text(language, "admin_reseller_not_found"), show_alert=True)
        _render_admin_reseller_list(call.message.chat.id, call.message.message_id, call.from_user.id, return_status, return_page)
        return

    _set_admin_view_context(call.from_user.id, return_status, return_page)
    bot.edit_message_text(
        _build_admin_reseller_detail_text(language, reseller_id, reseller_data),
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=_build_admin_reseller_detail_markup(language, reseller_id, reseller_data, return_status, return_page),
        parse_mode="Markdown",
    )


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
        current_debt=f"{current_debt:.2f}",
    )

    markup = types.InlineKeyboardMarkup(row_width=2)
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
        old_debt=f"{old_debt:.2f}",
        new_debt=f"{normalized:.2f}",
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
        old_debt=f"{old_debt:.2f}",
        new_debt=f"{normalized:.2f}",
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
        elif target_action == "ban":
            update_reseller_status(reseller_id, "banned")
        elif target_action == "unban":
            update_reseller_status(reseller_id, "approved")
        else:
            bot.answer_callback_query(call.id, get_message_text(language, "admin_invalid_action"), show_alert=True)
            return

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
