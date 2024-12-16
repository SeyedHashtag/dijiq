import json
import os
from telebot import types
from utils.command import *
from utils.common import create_main_markup

SUPPORT_FILE = '/etc/hysteria/core/scripts/telegrambot/support_info.json'

def load_support_info():
    try:
        if os.path.exists(SUPPORT_FILE):
            with open(SUPPORT_FILE, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    return {
        "telegram": "@your_support_username",
        "email": "support@yourdomain.com",
        "hours": "24/7"
    }

def save_support_info(info):
    os.makedirs(os.path.dirname(SUPPORT_FILE), exist_ok=True)
    with open(SUPPORT_FILE, 'w') as f:
        json.dump(info, f, indent=4)

def get_support_text():
    info = load_support_info()
    return (
        "Need help? Contact our support:\n\n"
        f"📱 Telegram: {info['telegram']}\n"
        f"📧 Email: {info['email']}\n"
        f"⏰ Working hours: {info['hours']}"
    )

@bot.message_handler(func=lambda message: is_admin(message.from_user.id) and message.text == '📞 Edit Support')
def edit_support(message):
    info = load_support_info()
    msg = bot.reply_to(
        message,
        "Current Support Information:\n\n"
        f"Telegram: {info['telegram']}\n"
        f"Email: {info['email']}\n"
        f"Hours: {info['hours']}\n\n"
        "Enter new Telegram username:"
    )
    bot.register_next_step_handler(msg, process_telegram)

def process_telegram(message):
    if message.text == "❌ Cancel":
        bot.reply_to(message, "Operation canceled.", reply_markup=create_main_markup(is_admin=True))
        return
    
    telegram = message.text.strip()
    msg = bot.reply_to(message, "Enter support email:")
    bot.register_next_step_handler(msg, process_email, telegram)

def process_email(message, telegram):
    if message.text == "❌ Cancel":
        bot.reply_to(message, "Operation canceled.", reply_markup=create_main_markup(is_admin=True))
        return
    
    email = message.text.strip()
    msg = bot.reply_to(message, "Enter working hours:")
    bot.register_next_step_handler(msg, process_hours, telegram, email)

def process_hours(message, telegram, email):
    if message.text == "❌ Cancel":
        bot.reply_to(message, "Operation canceled.", reply_markup=create_main_markup(is_admin=True))
        return
    
    hours = message.text.strip()
    
    # Save new support info
    info = {
        "telegram": telegram,
        "email": email,
        "hours": hours
    }
    save_support_info(info)
    
    bot.reply_to(
        message,
        "✅ Support information updated successfully!",
        reply_markup=create_main_markup(is_admin=True)
    ) 
