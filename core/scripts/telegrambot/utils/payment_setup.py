from telebot import types
from utils.command import bot, is_admin
from utils.common import create_main_markup
import os
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
    markup.row(types.KeyboardButton("💳 Crypto"), types.KeyboardButton("💳 Card to Card (Iran)"))
    markup.row(types.KeyboardButton("🔀 Card to Card Mode"), types.KeyboardButton("💱 Exchange Rate"))
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
    elif message.text == "💳 Card to Card (Iran)":
        setup_card_to_card(message)
    elif message.text == "🔀 Card to Card Mode":
        setup_card_to_card_mode(message)
    elif message.text == "💱 Exchange Rate":
        setup_exchange_rate(message)
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

def setup_card_to_card(message):
    load_dotenv(env_path, override=True)
    current_card_number = os.getenv('CARD_TO_CARD_NUMBER')
    
    status_text = "Current Card to Card Settings:\n"
    status_text += f"Card Number: {current_card_number if current_card_number else '❌ Not configured'}\n\n"
    status_text += "Please enter the card number for 'Card to Card' payments:"
    
    msg = bot.reply_to(
        message, 
        status_text,
        reply_markup=create_cancel_markup()
    )
    bot.register_next_step_handler(msg, process_card_to_card_number)

def process_card_to_card_number(message):
    if message.text == "❌ Cancel":
        bot.reply_to(message, "Operation canceled.", reply_markup=create_main_markup(is_admin=True))
        return

    card_number = message.text.strip()
    
    if not card_number:
        msg = bot.reply_to(
            message,
            "Card number cannot be empty. Please enter a valid card number:",
            reply_markup=create_cancel_markup()
        )
        bot.register_next_step_handler(msg, process_card_to_card_number)
        return

    try:
        if not os.path.exists(env_path):
            with open(env_path, 'w') as f:
                pass
        
        set_key(env_path, 'CARD_TO_CARD_NUMBER', card_number)
        load_dotenv(env_path, override=True)
        
        bot.reply_to(
            message,
            "✅ Card to Card number has been updated successfully!",
            reply_markup=create_main_markup(is_admin=True)
        )
    except Exception as e:
        bot.reply_to(
            message,
            f"❌ Error updating Card to Card number: {str(e)}",
            reply_markup=create_main_markup(is_admin=True)
        )


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
