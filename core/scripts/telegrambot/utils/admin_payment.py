from telebot import types
from utils.command import *
from utils.common import create_main_markup
import os
from dotenv import load_dotenv, set_key

def create_cancel_markup():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(types.KeyboardButton("❌ Cancel"))
    return markup

@bot.message_handler(func=lambda message: is_admin(message.from_user.id) and message.text == '💳 Payment Settings')
def payment_settings(message):
    msg = bot.reply_to(
        message, 
        "Please enter your Cryptomus Merchant ID:",
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
        env_path = '/etc/hysteria/core/scripts/telegrambot/.env'
        
        # Load existing .env file
        load_dotenv(env_path)
        
        # Update the values
        set_key(env_path, 'CRYPTOMUS_MERCHANT_ID', merchant_id)
        set_key(env_path, 'CRYPTOMUS_API_KEY', api_key)
        
        # Reload the environment variables
        load_dotenv(env_path)
        
        bot.reply_to(
            message,
            "✅ Payment credentials have been updated successfully!",
            reply_markup=create_main_markup(is_admin=True)
        )
    except Exception as e:
        bot.reply_to(
            message,
            f"❌ Error updating payment credentials: {str(e)}",
            reply_markup=create_main_markup(is_admin=True)
        ) 
