from telebot import types
from utils.command import bot, is_admin
from utils.common import create_main_markup
import os
from dotenv import load_dotenv, set_key

env_path = os.path.join(os.path.dirname(__file__), '.env')

def create_cancel_markup():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(types.KeyboardButton("❌ Cancel"))
    return markup

def create_payment_method_selection_markup():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(types.KeyboardButton("💳 Cryptomus"), types.KeyboardButton("💳 Card to Card (Iran)"))
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

    if message.text == "💳 Cryptomus":
        setup_cryptomus(message)
    elif message.text == "💳 Card to Card (Iran)":
        setup_card_to_card(message)
    else:
        bot.reply_to(message, "Invalid selection. Please try again.", reply_markup=create_main_markup(is_admin=True))

def setup_cryptomus(message):
    load_dotenv(env_path)
    
    current_merchant_id = os.getenv('CRYPTOMUS_MERCHANT_ID')
    current_api_key = os.getenv('CRYPTOMUS_API_KEY')
    
    status_text = "Current Cryptomus Settings:\n"
    status_text += f"Merchant ID: {'✅ Configured' if current_merchant_id else '❌ Not configured'}\n"
    status_text += f"API Key: {'✅ Configured' if current_api_key else '❌ Not configured'}\n\n"
    status_text += "Please enter your Cryptomus Merchant ID:"
    
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
        "Now enter your Cryptomus API Key:",
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
        load_dotenv(env_path)
        set_key(env_path, 'CRYPTOMUS_MERCHANT_ID', merchant_id)
        set_key(env_path, 'CRYPTOMUS_API_KEY', api_key)
        load_dotenv(env_path)
        
        bot.reply_to(
            message,
            "✅ Cryptomus credentials have been updated successfully!",
            reply_markup=create_main_markup(is_admin=True)
        )
    except Exception as e:
        bot.reply_to(
            message,
            f"❌ Error updating Cryptomus credentials: {str(e)}",
            reply_markup=create_main_markup(is_admin=True)
        )

def setup_card_to_card(message):
    load_dotenv(env_path)
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
        load_dotenv(env_path)
        set_key(env_path, 'CARD_TO_CARD_NUMBER', card_number)
        load_dotenv(env_path)
        
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
