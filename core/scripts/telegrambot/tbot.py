from telebot import types
from utils import *
from utils.languages import get_text, get_user_language, set_user_language
import threading
import time

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    
    # Get or initialize the user's language preference
    lang_code = get_user_language(user_id)
    
    if is_admin(user_id):
        # Admin menu remains in English
        markup = create_main_markup(is_admin=True)
        bot.reply_to(message, "Welcome to the Admin Dashboard!", reply_markup=markup)
    else:
        # User menu in their preferred language
        markup = create_main_markup(is_admin=False, lang_code=lang_code)
        bot.reply_to(
            message, 
            get_text("welcome_message", lang_code),
            reply_markup=markup
        )

def monitoring_thread():
    while True:
        monitor_system_resources()
        time.sleep(60)

if __name__ == '__main__':
    monitor_thread = threading.Thread(target=monitoring_thread, daemon=True)
    monitor_thread.start()
    version_thread = threading.Thread(target=version_monitoring, daemon=True)
    version_thread.start()
    bot.polling(none_stop=True)
