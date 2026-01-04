import telebot
from telebot import types
import uuid
import qrcode
import io
import os
import datetime
import re
from dotenv import load_dotenv

from utils.command import bot, ADMIN_USER_IDS, is_admin
from utils.language import get_user_language
from utils.translations import get_message_text, get_button_text, BUTTON_TRANSLATIONS
from utils.reseller import (
    get_reseller_data, update_reseller_status, add_reseller_debt, 
    clear_reseller_debt, get_all_resellers, set_reseller_debt
)
from utils.edit_plans import load_plans
from utils.adduser import APIClient
from utils.payments import CryptoPayment
from utils.payment_records import add_payment_record
from utils.purchase_plan import user_data

# Reseller Menu Handler
@bot.message_handler(func=lambda message: any(
    message.text == get_button_text(get_user_language(message.from_user.id), "reseller_panel") for lang in BUTTON_TRANSLATIONS
))
def reseller_panel(message):
    user_id = message.from_user.id
    language = get_user_language(user_id)
    reseller_data = get_reseller_data(user_id)
    
    status = reseller_data.get('status') if reseller_data else None
    
    if status == 'approved':
        # Show Reseller Menu
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton(get_button_text(language, "generate_config"), callback_data="reseller:generate"),
            types.InlineKeyboardButton(get_button_text(language, "my_debt"), callback_data="reseller:debt")
        )
        markup.add(types.InlineKeyboardButton(get_button_text(language, "reseller_stats"), callback_data="reseller:stats"))
        debt = reseller_data.get('debt', 0.0)
        bot.reply_to(message, get_message_text(language, "reseller_intro").replace("${debt}", f"${debt}"), reply_markup=markup)
        
    elif status == 'pending':
        bot.reply_to(message, get_message_text(language, "reseller_status_pending"))
        
    elif status == 'rejected':
        bot.reply_to(message, get_message_text(language, "reseller_status_rejected"))
        
    else:
        # Not a reseller yet
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(get_button_text(language, "request_reseller"), callback_data="reseller:request"))
        bot.reply_to(message, get_message_text(language, "reseller_intro").replace("${debt}", "0") + "\n\n" + get_message_text(language, "request_reseller"), reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "reseller:request")
def handle_reseller_request(call):
    user_id = call.from_user.id
    language = get_user_language(user_id)
    
    # Update status to pending
    update_reseller_status(user_id, 'pending')
    
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
    
    plans = load_plans()
    sorted_plans = sorted(plans.items(), key=lambda x: int(x[0]))
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    for gb, details in sorted_plans:
        button_text = f"{gb} GB - ${details['price']} - {details['days']} days"
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
    gb = call.data.split(':')[2]
    
    plans = load_plans()
    if gb not in plans:
        return
        
    plan = plans[gb]
    price = plan['price']
    days = plan['days']
    
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

@bot.message_handler(func=lambda message: message.from_user.id in user_data and user_data[message.from_user.id].get('state') == 'waiting_reseller_username')
def handle_reseller_username_input(message):
    user_id = message.from_user.id
    language = get_user_language(user_id)
    chosen_username = message.text.strip()
    
    # Validate username: alphanumeric and max 8 chars
    if not re.match(r'^[a-zA-Z0-9]{1,8}$', chosen_username):
        bot.reply_to(message, get_message_text(language, "invalid_username_format"))
        return
        
    data = user_data[user_id]
    gb = data['gb']
    days = data['days']
    price = data['price']
    
    # Generate final username: reseller{reseller_id}t{timestamp}{chosen_username}
    timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    username = f"reseller{user_id}t{timestamp}{chosen_username}"
    
    # Create user
    api_client = APIClient()
    result = api_client.add_user(username, int(gb), int(days))
    
    if result:
        # Add debt
        config_data = {
            "username": username,
            "gb": gb,
            "days": days,
            "price": price
        }
        add_reseller_debt(user_id, price, config_data)
        
        # Get subscription URL
        user_uri_data = api_client.get_user_uri(username)
        sub_url = user_uri_data.get('normal_sub', 'N/A') if user_uri_data else 'N/A'
        
        msg = get_message_text(language, "reseller_config_created").format(
            username=username,
            plan_gb=gb,
            days=days,
            price=price,
            sub_url=sub_url
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
    reseller_data = get_reseller_data(user_id)
    debt = reseller_data.get('debt', 0.0)
    
    markup = types.InlineKeyboardMarkup()
    if debt > 0:
        markup.add(types.InlineKeyboardButton(get_button_text(language, "settle_debt"), callback_data=f"reseller:settle:{debt}"))
    markup.add(types.InlineKeyboardButton(get_button_text(language, "cancel"), callback_data="reseller:cancel"))
    
    bot.edit_message_text(
        get_message_text(language, "current_debt").replace("${debt}", f"${debt}"),
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("reseller:settle:"))
def handle_reseller_settle(call):
    user_id = call.from_user.id
    language = get_user_language(user_id)
    amount = float(call.data.split(':')[2])
    
    # Re-use payment logic
    env_path = '/etc/dijiq/core/scripts/telegrambot/.env'
    load_dotenv(env_path)
    
    crypto_configured = all(os.getenv(key) for key in ['CRYPTO_MERCHANT_ID', 'CRYPTO_API_KEY'])
    card_to_card_configured = os.getenv('CARD_TO_CARD_NUMBER')
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    if crypto_configured:
        markup.add(types.InlineKeyboardButton(get_button_text(language, "crypto"), callback_data=f"reseller:pay:crypto:{amount}"))
    if card_to_card_configured:
        markup.add(types.InlineKeyboardButton(get_button_text(language, "card_to_card"), callback_data=f"reseller:pay:card:{amount}"))
        
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
    _, _, method, amount = call.data.split(':')
    amount = float(amount)
    
    if method == 'crypto':
        payment_handler = CryptoPayment()
        payment_response = payment_handler.create_payment(
            amount, "Settlement", user_id
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
                'price': amount,
                'days': 0,
                'payment_id': payment_id,
                'status': 'pending',
                'type': 'settlement'
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
            bot.send_photo(call.message.chat.id, bio, caption=get_message_text(language, "payment_instructions").format(price=amount, payment_url=payment_url, payment_id=payment_id), reply_markup=markup)

    elif method == 'card':
        # Card to card logic
        exchange_rate = os.getenv('EXCHANGE_RATE', '1')
        card_number = os.getenv('CARD_TO_CARD_NUMBER')
        price_in_tomans = amount * float(exchange_rate)
        
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
            'price': amount,
            'type': 'settlement' 
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
    reseller_data = get_reseller_data(user_id)
    
    if not reseller_data:
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

# Admin Management Handlers

@bot.message_handler(func=lambda message: any(
    message.text == get_button_text(get_user_language(message.from_user.id), "manage_resellers") for lang in BUTTON_TRANSLATIONS
))
def admin_manage_resellers(message):
    if not is_admin(message.from_user.id):
        return
        
    user_id = message.from_user.id
    language = get_user_language(user_id)
    resellers = get_all_resellers()
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    for rid, data in resellers.items():
        status_icon = "✅" if data.get('status') == 'approved' else "⏳" if data.get('status') == 'pending' else "❌"
        markup.add(types.InlineKeyboardButton(f"{status_icon} {rid}", callback_data=f"admin_manage:{rid}"))
        
    markup.add(types.InlineKeyboardButton(get_button_text(language, "cancel"), callback_data="reseller:cancel"))
    
    bot.reply_to(message, get_message_text(language, "admin_resellers_list"), reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_manage:"))
def handle_admin_manage_detail(call):
    if not is_admin(call.from_user.id):
        return
        
    target_id = call.data.split(':')[1]
    language = get_user_language(call.from_user.id)
    reseller_data = get_reseller_data(target_id)
    
    if not reseller_data:
        bot.answer_callback_query(call.id, "Reseller not found")
        return
        
    status = reseller_data.get('status')
    debt = reseller_data.get('debt', 0.0)
    configs_count = len(reseller_data.get('configs', []))
    
    msg = get_message_text(language, "admin_reseller_details").format(
        user_id=target_id,
        status=status,
        debt=debt,
        configs_count=configs_count
    )
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📝 Adjust Debt", callback_data=f"admin_adjust_debt:{target_id}"),
        types.InlineKeyboardButton("🚫 Ban/Unban", callback_data=f"admin_toggle_ban:{target_id}")
    )
    markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="admin_back_resellers"))
    
    bot.edit_message_text(
        msg,
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data == "admin_back_resellers")
def handle_admin_back_resellers(call):
    if not is_admin(call.from_user.id):
        return
    # Re-use the list logic, but we need a message object. Construct a fake one or just edit.
    # Editing is better.
    user_id = call.from_user.id
    language = get_user_language(user_id)
    resellers = get_all_resellers()
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    for rid, data in resellers.items():
        status_icon = "✅" if data.get('status') == 'approved' else "⏳" if data.get('status') == 'pending' else "❌"
        markup.add(types.InlineKeyboardButton(f"{status_icon} {rid}", callback_data=f"admin_manage:{rid}"))
        
    markup.add(types.InlineKeyboardButton(get_button_text(language, "cancel"), callback_data="reseller:cancel"))
    
    bot.edit_message_text(
        get_message_text(language, "admin_resellers_list"),
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_toggle_ban:"))
def handle_admin_toggle_ban(call):
    if not is_admin(call.from_user.id):
        return
    
    target_id = call.data.split(':')[1]
    reseller_data = get_reseller_data(target_id)
    current_status = reseller_data.get('status')
    
    new_status = 'rejected' if current_status == 'approved' else 'approved'
    update_reseller_status(target_id, new_status)
    
    # Refresh view
    handle_admin_manage_detail(call) # This parses call.data, but we need to pass a modified call or just call the logic.
    # The logic extracts target_id from data "admin_manage:target_id".
    # We can just change call.data and re-call.
    call.data = f"admin_manage:{target_id}"
    handle_admin_manage_detail(call)

@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_adjust_debt:"))
def handle_admin_adjust_debt_prompt(call):
    if not is_admin(call.from_user.id):
        return
        
    target_id = call.data.split(':')[1]
    language = get_user_language(call.from_user.id)
    
    bot.send_message(
        call.message.chat.id, 
        get_message_text(language, "admin_adjust_debt").format(user_id=target_id),
        reply_markup=types.ForceReply()
    )
    # Store state to handle text reply
    user_data[call.from_user.id] = {
        'state': 'waiting_debt_amount',
        'target_reseller': target_id
    }

@bot.message_handler(func=lambda message: message.from_user.id in user_data and user_data[message.from_user.id].get('state') == 'waiting_debt_amount')
def handle_admin_debt_input(message):
    try:
        data = user_data[message.from_user.id]
        target_id = data['target_reseller']
        new_amount = float(message.text.strip())
        
        set_reseller_debt(target_id, new_amount)
        
        language = get_user_language(message.from_user.id)
        bot.reply_to(message, get_message_text(language, "debt_updated"))
        
        del user_data[message.from_user.id]
        
    except ValueError:
        bot.reply_to(message, "Invalid amount. Please enter a number.")
