from telebot import types
from utils.command import *
from utils.common import create_main_markup
from utils.test_mode import toggle_test_mode, load_test_mode

@bot.message_handler(func=lambda message: is_admin(message.from_user.id) and message.text == '🔧 Payment Test')
def handle_test_mode(message):
    new_state = toggle_test_mode()
    status = "✅ ENABLED" if new_state else "❌ DISABLED"
    bot.reply_to(
        message,
        f"Payment Test Mode: {status}",
        reply_markup=create_main_markup(is_admin=True)
    ) 
