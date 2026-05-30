from telebot import types
from utils.command import bot, is_admin
from utils.common import create_main_markup
from utils.payment_records import load_payments
from utils.receipt_checker import (
    RECEIPT_TYPE_REGULAR,
    RECEIPT_TYPE_SETTLEMENT,
    get_receipt_checker_types,
    get_receipt_checker_user_id,
    get_receipt_type_label,
    normalize_receipt_types,
)
import os
import datetime
from dotenv import load_dotenv, set_key

# FIX: Go up one level ('..') to find the root .env file
# This prevents creating a duplicate .env inside your handlers/utils folder
env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.env'))

def create_cancel_markup():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(types.KeyboardButton("❌ Cancel"))
    return markup

def create_payment_method_selection_markup():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(types.KeyboardButton("💳 Crypto"), types.KeyboardButton("💳 Main Card"))
    markup.row(types.KeyboardButton("💳 Checker Card"), types.KeyboardButton("🔀 Card to Card Mode"))
    markup.row(types.KeyboardButton("💱 Exchange Rate"), types.KeyboardButton("🏢 Reseller Settlement Threshold"))
    markup.row(types.KeyboardButton("👤 Receipt Checker"), types.KeyboardButton("📋 Checker Receipt Types"))
    markup.row(types.KeyboardButton("📊 Checker Stats"))
    markup.row(types.KeyboardButton("❌ Cancel"))
    return markup

@bot.message_handler(func=lambda message: is_admin(message.from_user.id) and message.text == '💳 Payment Settings')
def payment_settings(message):
    msg = bot.reply_to(
        message, 
        "Please select a payment method to configure:",
        reply_markup=create_payment_method_selection_markup()
    )
    bot.register_next_step_handler(msg, process_payment_method_selection)

def process_payment_method_selection(message):
    if message.text == "❌ Cancel":
        bot.reply_to(message, "Operation canceled.", reply_markup=create_main_markup(is_admin=True))
        return

    if message.text == "💳 Crypto":
        setup_crypto(message)
    elif message.text in ("💳 Card to Card (Iran)", "💳 Main Card"):
        setup_card_to_card(message, "main")
    elif message.text == "💳 Checker Card":
        setup_card_to_card(message, "checker")
    elif message.text == "🔀 Card to Card Mode":
        setup_card_to_card_mode(message)
    elif message.text == "💱 Exchange Rate":
        setup_exchange_rate(message)
    elif message.text == "🏢 Reseller Settlement Threshold":
        setup_reseller_settlement_threshold(message)
    elif message.text == "👤 Receipt Checker":
        setup_receipt_checker(message)
    elif message.text == "📋 Checker Receipt Types":
        setup_receipt_checker_types(message)
    elif message.text == "📊 Checker Stats":
        show_receipt_checker_stats(message)
    else:
        bot.reply_to(message, "Invalid selection. Please try again.", reply_markup=create_main_markup(is_admin=True))

def setup_crypto(message):
    load_dotenv(env_path, override=True)
    
    current_merchant_id = os.getenv('CRYPTO_MERCHANT_ID')
    current_api_key = os.getenv('CRYPTO_API_KEY')
    
    status_text = "Current Crypto Settings:\n"
    status_text += f"Merchant ID: {'✅ Configured' if current_merchant_id else '❌ Not configured'}\n"
    status_text += f"API Key: {'✅ Configured' if current_api_key else '❌ Not configured'}\n\n"
    status_text += "Please enter your Crypto Merchant ID:"
    
    msg = bot.reply_to(
        message, 
        status_text,
        reply_markup=create_cancel_markup()
    )
    bot.register_next_step_handler(msg, process_merchant_id)

def process_merchant_id(message):
    if message.text == "❌ Cancel":
        bot.reply_to(message, "Operation canceled.", reply_markup=create_main_markup(is_admin=True))
        return

    merchant_id = message.text.strip()
    
    if not merchant_id:
        msg = bot.reply_to(
            message,
            "Merchant ID cannot be empty. Please enter a valid Merchant ID:",
            reply_markup=create_cancel_markup()
        )
        bot.register_next_step_handler(msg, process_merchant_id)
        return

    msg = bot.reply_to(
        message,
        "Now enter your Crypto API Key:",
        reply_markup=create_cancel_markup()
    )
    bot.register_next_step_handler(msg, process_api_key, merchant_id)

def process_api_key(message, merchant_id):
    if message.text == "❌ Cancel":
        bot.reply_to(message, "Operation canceled.", reply_markup=create_main_markup(is_admin=True))
        return

    api_key = message.text.strip()
    
    if not api_key:
        msg = bot.reply_to(
            message,
            "API Key cannot be empty. Please enter a valid API Key:",
            reply_markup=create_cancel_markup()
        )
        bot.register_next_step_handler(msg, process_api_key, merchant_id)
        return

    try:
        if not os.path.exists(env_path):
            with open(env_path, 'w') as f:
                pass
        
        # Write to file
        set_key(env_path, 'CRYPTO_MERCHANT_ID', merchant_id)
        set_key(env_path, 'CRYPTO_API_KEY', api_key)
        
        # Reload immediately with override=True so the bot uses new values
        load_dotenv(env_path, override=True)
        
        bot.reply_to(
            message,
            "✅ Crypto credentials have been updated successfully!",
            reply_markup=create_main_markup(is_admin=True)
        )
    except Exception as e:
        bot.reply_to(
            message,
            f"❌ Error updating Crypto credentials: {str(e)}",
            reply_markup=create_main_markup(is_admin=True)
        )

def setup_card_to_card(message, slot="main"):
    load_dotenv(env_path, override=True)
    env_key = 'CARD_TO_CARD_CHECKER_NUMBER' if slot == "checker" else 'CARD_TO_CARD_NUMBER'
    slot_label = "Checker" if slot == "checker" else "Main"
    current_card_number = os.getenv(env_key)
    
    status_text = f"Current {slot_label} Card to Card Settings:\n"
    status_text += f"{slot_label} Card Number: {current_card_number if current_card_number else '❌ Not configured'}\n\n"
    status_text += f"Please enter the {slot_label.lower()} card number for 'Card to Card' payments:"
    
    msg = bot.reply_to(
        message, 
        status_text,
        reply_markup=create_cancel_markup()
    )
    bot.register_next_step_handler(msg, process_card_to_card_number, slot)

def process_card_to_card_number(message, slot="main"):
    if message.text == "❌ Cancel":
        bot.reply_to(message, "Operation canceled.", reply_markup=create_main_markup(is_admin=True))
        return

    card_number = message.text.strip()
    env_key = 'CARD_TO_CARD_CHECKER_NUMBER' if slot == "checker" else 'CARD_TO_CARD_NUMBER'
    slot_label = "Checker" if slot == "checker" else "Main"
    
    if not card_number:
        msg = bot.reply_to(
            message,
            "Card number cannot be empty. Please enter a valid card number:",
            reply_markup=create_cancel_markup()
        )
        bot.register_next_step_handler(msg, process_card_to_card_number, slot)
        return

    try:
        if not os.path.exists(env_path):
            with open(env_path, 'w') as f:
                pass
        
        set_key(env_path, env_key, card_number)
        load_dotenv(env_path, override=True)
        
        bot.reply_to(
            message,
            f"✅ {slot_label} Card to Card number has been updated successfully!",
            reply_markup=create_main_markup(is_admin=True)
        )
    except Exception as e:
        bot.reply_to(
            message,
            f"❌ Error updating {slot_label} Card to Card number: {str(e)}",
            reply_markup=create_main_markup(is_admin=True)
        )


def setup_receipt_checker(message):
    load_dotenv(env_path, override=True)
    current_checker_id = os.getenv('RECEIPT_CHECKER_USER_ID', '').strip()
    status_text = "Current Receipt Checker Settings:\n"
    status_text += f"Checker User ID: {current_checker_id if current_checker_id else '❌ Not configured'}\n\n"
    status_text += "Please enter the numeric Telegram user ID for the receipt checker:"

    msg = bot.reply_to(message, status_text, reply_markup=create_cancel_markup())
    bot.register_next_step_handler(msg, process_receipt_checker_id)


def process_receipt_checker_id(message):
    if message.text == "❌ Cancel":
        bot.reply_to(message, "Operation canceled.", reply_markup=create_main_markup(is_admin=True))
        return

    checker_id = message.text.strip()
    if not checker_id.isdigit():
        msg = bot.reply_to(
            message,
            "Checker user ID must be numeric. Please enter a valid Telegram user ID:",
            reply_markup=create_cancel_markup()
        )
        bot.register_next_step_handler(msg, process_receipt_checker_id)
        return

    try:
        if not os.path.exists(env_path):
            with open(env_path, 'w') as f:
                pass
        set_key(env_path, 'RECEIPT_CHECKER_USER_ID', checker_id)
        load_dotenv(env_path, override=True)
        bot.reply_to(
            message,
            "✅ Receipt checker has been updated successfully!",
            reply_markup=create_main_markup(is_admin=True)
        )
    except Exception as e:
        bot.reply_to(
            message,
            f"❌ Error updating receipt checker: {str(e)}",
            reply_markup=create_main_markup(is_admin=True)
        )


def setup_receipt_checker_types(message):
    checker_id = get_receipt_checker_user_id()
    current_types = get_receipt_checker_types()
    current_label = ", ".join(get_receipt_type_label(t) for t in current_types) if current_types else "❌ None"
    checker_label = checker_id if checker_id is not None else "❌ Not configured"
    text = (
        "📋 Checker Receipt Types\n\n"
        f"Checker User ID: {checker_label}\n"
        f"Current Types: {current_label}\n\n"
        "Select which receipts should also go to the checker:"
    )
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("Regular Customers", callback_data="checker_types:regular"),
        types.InlineKeyboardButton("Reseller Settlements", callback_data="checker_types:settlement"),
        types.InlineKeyboardButton("Both", callback_data="checker_types:both"),
        types.InlineKeyboardButton("None", callback_data="checker_types:none"),
    )
    bot.reply_to(message, text, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith('checker_types:'))
def handle_receipt_checker_type_selection(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, text="Not authorized.")
        return

    selection = call.data.split(':')[1]
    if selection == "both":
        receipt_types = [RECEIPT_TYPE_REGULAR, RECEIPT_TYPE_SETTLEMENT]
    elif selection == "none":
        receipt_types = []
    else:
        receipt_types = normalize_receipt_types(selection)

    try:
        if not os.path.exists(env_path):
            with open(env_path, 'w') as f:
                pass
        set_key(env_path, 'RECEIPT_CHECKER_TYPES', ",".join(receipt_types))
        load_dotenv(env_path, override=True)
        label = ", ".join(get_receipt_type_label(t) for t in receipt_types) if receipt_types else "None"
        bot.edit_message_text(
            f"✅ Checker receipt types updated to: {label}",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id
        )
    except Exception as e:
        bot.answer_callback_query(call.id, text=f"Error: {str(e)}")


def _parse_payment_datetime(value):
    if not value:
        return None
    try:
        return datetime.datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
    except (TypeError, ValueError):
        return None


def show_receipt_checker_stats(message):
    checker_id = get_receipt_checker_user_id()
    checker_types = get_receipt_checker_types()
    payments = load_payments()
    stats = {
        RECEIPT_TYPE_REGULAR: {"pending": 0, "approved": 0, "rejected": 0, "approved_total": 0.0},
        RECEIPT_TYPE_SETTLEMENT: {"pending": 0, "approved": 0, "rejected": 0, "approved_total": 0.0},
    }
    latest_review = None

    for payment_id, record in payments.items():
        if not record.get('routed_to_checker'):
            continue
        if checker_id is not None:
            try:
                routed_checker_id = int(record.get('receipt_checker_user_id'))
            except (TypeError, ValueError):
                routed_checker_id = None
            if routed_checker_id != checker_id:
                continue
        receipt_type = record.get('receipt_type')
        if receipt_type not in stats:
            continue

        status = record.get('status')
        if status == 'pending_approval':
            stats[receipt_type]["pending"] += 1
        elif status == 'completed':
            stats[receipt_type]["approved"] += 1
            try:
                stats[receipt_type]["approved_total"] += float(record.get('price', 0) or 0)
            except (TypeError, ValueError):
                pass
        elif status == 'rejected':
            stats[receipt_type]["rejected"] += 1

        reviewed_at = _parse_payment_datetime(record.get('reviewed_at'))
        if reviewed_at and (latest_review is None or reviewed_at > latest_review[0]):
            latest_review = (reviewed_at, payment_id, record)

    checker_label = checker_id if checker_id is not None else "Not configured"
    type_label = ", ".join(get_receipt_type_label(t) for t in checker_types) if checker_types else "None"
    text = (
        "📊 Receipt Checker Stats\n\n"
        f"Checker User ID: {checker_label}\n"
        f"Enabled Types: {type_label}\n\n"
    )
    for receipt_type in (RECEIPT_TYPE_REGULAR, RECEIPT_TYPE_SETTLEMENT):
        item = stats[receipt_type]
        text += (
            f"{get_receipt_type_label(receipt_type)}\n"
            f"Pending: {item['pending']}\n"
            f"Approved: {item['approved']} (${item['approved_total']:.2f})\n"
            f"Rejected: {item['rejected']}\n\n"
        )

    if latest_review:
        reviewed_at, payment_id, record = latest_review
        text += (
            "Latest Review\n"
            f"Payment ID: {payment_id}\n"
            f"Type: {get_receipt_type_label(record.get('receipt_type'))}\n"
            f"Action: {record.get('reviewed_action', 'N/A')}\n"
            f"Reviewer ID: {record.get('reviewed_by_user_id', 'N/A')}\n"
            f"Time: {reviewed_at.strftime('%Y-%m-%d %H:%M:%S')}"
        )
    else:
        text += "Latest Review\nNo routed receipts reviewed yet."

    bot.reply_to(message, text, reply_markup=create_main_markup(is_admin=True))


def setup_exchange_rate(message):
    load_dotenv(env_path, override=True)
    current_exchange_rate = os.getenv('EXCHANGE_RATE')
    
    status_text = "Current Exchange Rate Settings:\n"
    status_text += f"Exchange Rate (USD to Toman): {current_exchange_rate if current_exchange_rate else '❌ Not configured'}\n\n"
    status_text += "Please enter the exchange rate (e.g., 100 for 1 USD = 100 Tomans):"
    
    msg = bot.reply_to(
        message,
        status_text,
        reply_markup=create_cancel_markup()
    )
    bot.register_next_step_handler(msg, process_exchange_rate)


def process_exchange_rate(message):
    if message.text == "❌ Cancel":
        bot.reply_to(message, "Operation canceled.", reply_markup=create_main_markup(is_admin=True))
        return

    exchange_rate = message.text.strip()
    
    if not exchange_rate:
        msg = bot.reply_to(
            message,
            "Exchange rate cannot be empty. Please enter a valid exchange rate:",
            reply_markup=create_cancel_markup()
        )
        bot.register_next_step_handler(msg, process_exchange_rate)
        return

    if not exchange_rate.isdigit():
        msg = bot.reply_to(
            message,
            "Exchange rate must be a number. Please enter a valid exchange rate:",
            reply_markup=create_cancel_markup()
        )
        bot.register_next_step_handler(msg, process_exchange_rate)
        return

    try:
        if not os.path.exists(env_path):
            with open(env_path, 'w') as f:
                pass
        
        set_key(env_path, 'EXCHANGE_RATE', exchange_rate)
        load_dotenv(env_path, override=True)
        
        bot.reply_to(
            message,
            "✅ Exchange rate has been updated successfully!",
            reply_markup=create_main_markup(is_admin=True)
        )
    except Exception as e:
        bot.reply_to(
            message,
            f"❌ Error updating exchange rate: {str(e)}",
            reply_markup=create_main_markup(is_admin=True)
        )


MODE_LABELS = {
    'on': '✅ On (All Customers)',
    'off': '❌ Off (Disabled)',
    'previous_customers': '👤 Previous Customers Only'
}

def setup_card_to_card_mode(message):
    load_dotenv(env_path, override=True)
    current_mode = os.getenv('CARD_TO_CARD_MODE', 'on')
    current_label = MODE_LABELS.get(current_mode, MODE_LABELS['on'])

    status_text = (
        "🔀 Card to Card Mode Settings\n\n"
        f"Current Mode: {current_label}\n\n"
        "Select a new mode:"
    )

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("✅ On (All Customers)", callback_data="c2c_mode:on"),
        types.InlineKeyboardButton("❌ Off (Disabled)", callback_data="c2c_mode:off"),
        types.InlineKeyboardButton("👤 Previous Customers Only", callback_data="c2c_mode:previous_customers")
    )

    bot.reply_to(
        message,
        status_text,
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('c2c_mode:'))
def handle_card_to_card_mode_selection(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, text="Not authorized.")
        return

    mode = call.data.split(':')[1]
    if mode not in ('on', 'off', 'previous_customers'):
        bot.answer_callback_query(call.id, text="Invalid mode.")
        return

    try:
        if not os.path.exists(env_path):
            with open(env_path, 'w') as f:
                pass

        set_key(env_path, 'CARD_TO_CARD_MODE', mode)
        load_dotenv(env_path, override=True)

        mode_label = MODE_LABELS.get(mode, mode)
        bot.edit_message_text(
            f"✅ Card to Card mode updated to: {mode_label}",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id
        )
    except Exception as e:
        bot.answer_callback_query(call.id, text=f"Error: {str(e)}")

def setup_reseller_settlement_threshold(message):
    load_dotenv(env_path, override=True)
    current_threshold = os.getenv('RESELLER_SETTLEMENT_THRESHOLD', '2.0')
    
    status_text = "Current Reseller Settlement Threshold:\n"
    status_text += f"Amount: {current_threshold} USD\n\n"
    status_text += "Please enter the new threshold amount in USD (e.g., 2.0 or 5.5):"
    
    msg = bot.reply_to(
        message,
        status_text,
        reply_markup=create_cancel_markup()
    )
    bot.register_next_step_handler(msg, process_reseller_settlement_threshold)

def process_reseller_settlement_threshold(message):
    if message.text == "❌ Cancel":
        bot.reply_to(message, "Operation canceled.", reply_markup=create_main_markup(is_admin=True))
        return

    threshold_str = message.text.strip()
    
    if not threshold_str:
        msg = bot.reply_to(
            message,
            "Threshold cannot be empty. Please enter a valid number:",
            reply_markup=create_cancel_markup()
        )
        bot.register_next_step_handler(msg, process_reseller_settlement_threshold)
        return

    try:
        threshold_val = float(threshold_str)
        if threshold_val < 0:
            raise ValueError("Threshold cannot be negative.")
    except ValueError:
        msg = bot.reply_to(
            message,
            "Invalid amount. Please enter a valid positive number:",
            reply_markup=create_cancel_markup()
        )
        bot.register_next_step_handler(msg, process_reseller_settlement_threshold)
        return

    try:
        if not os.path.exists(env_path):
            with open(env_path, 'w') as f:
                pass
        
        set_key(env_path, 'RESELLER_SETTLEMENT_THRESHOLD', str(threshold_val))
        load_dotenv(env_path, override=True)
        
        bot.reply_to(
            message,
            "✅ Reseller Settlement Threshold has been updated successfully!",
            reply_markup=create_main_markup(is_admin=True)
        )
    except Exception as e:
        bot.reply_to(
            message,
            f"❌ Error updating threshold: {str(e)}",
            reply_markup=create_main_markup(is_admin=True)
        )
