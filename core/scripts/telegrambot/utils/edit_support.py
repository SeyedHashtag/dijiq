import json
import os
from telebot import types
from utils.command import bot, is_admin
from utils.common import create_main_markup

SUPPORT_FILE = '/etc/dijiq/core/scripts/telegrambot/support_info.json'

def load_support_info():
    try:
        if os.path.exists(SUPPORT_FILE):
            with open(SUPPORT_FILE, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    return {
        "text": "Need help? Contact our support:\n\n"
               "📱 Telegram: @your_support_username\n"
               "⏰ Working hours: 24/7\n"
               "Thank you!"
    }

def save_support_info(text):
    os.makedirs(os.path.dirname(SUPPORT_FILE), exist_ok=True)
    with open(SUPPORT_FILE, 'w') as f:
        json.dump({"text": text}, f, indent=4)

def get_support_text():
    info = load_support_info()
    return info['text']

@bot.message_handler(func=lambda message: is_admin(message.from_user.id) and message.text == '📞 Edit Support')
def edit_support(message):
    current_text = get_support_text()
    msg = bot.reply_to(
        message,
        f"Current support text:\n\n{current_text}\n\n"
        "Enter the new support text you want to display to users:",
        reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add(types.KeyboardButton("❌ Cancel"))
    )
    bot.register_next_step_handler(msg, process_support_text)

def process_support_text(message):
    if message.text == "❌ Cancel":
        bot.reply_to(message, "Operation canceled.", reply_markup=create_main_markup(is_admin=True))
        return
    
    new_text = message.text.strip()
    save_support_info(new_text)
    
    bot.reply_to(
        message,
        "✅ Support text updated successfully!",
        reply_markup=create_main_markup(is_admin=True)
    )

# Handler for regular users clicking on the Support button
@bot.message_handler(func=lambda message: message.text == '📞 Support')
def show_support(message):
    support_text = get_support_text()
    bot.reply_to(
        message,
        support_text,
        parse_mode="Markdown"
    )