from telebot import types
from utils import *
import threading
import time
from .utils.language import get_text, set_user_language, get_user_language, LANGUAGES

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id # Get user_id
    lang_code = get_user_language(user_id) # Get lang_code for welcome message
    admin_status = is_admin(user_id) # Assuming is_admin function exists and checks the user's admin status

    markup = create_main_markup(user_id=user_id, is_admin=admin_status) # Pass user_id
    welcome_message_key = "welcome_admin" if admin_status else "welcome_user" # Assuming you might want different welcome messages

    # Fallback to generic welcome if specific keys are not present
    # Or, ensure "welcome_admin" and "welcome_user" are in your language files.
    # For now, using the existing "welcome" key for both, or specific admin welcome.
    if admin_status:
        # Assuming admin dashboard might have a fixed language or its own i18n
        bot.reply_to(message, "Welcome to the Admin Dashboard!", reply_markup=markup)
    else:
        bot.reply_to(message, get_text(lang_code, "welcome"), reply_markup=markup)

@bot.message_handler(func=lambda message: get_text(get_user_language(message.from_user.id), "language") in message.text)
def handle_language_selection(message):
    user_id = message.from_user.id
    lang_code = get_user_language(user_id)
    markup = types.InlineKeyboardMarkup()
    for code, lang_data in LANGUAGES.items():
        lang_name = lang_data.get("language_name", code.upper())
        markup.add(types.InlineKeyboardButton(lang_name, callback_data=f"set_lang_{code}"))
    bot.send_message(message.chat.id, get_text(lang_code, "select_language"), reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("set_lang_"))
def callback_set_language(call):
    user_id = call.from_user.id
    lang_code = call.data.split("_")[2]
    set_user_language(user_id, lang_code)
    
    lang_name_display = LANGUAGES.get(lang_code, {}).get("language_name", lang_code.upper())
    bot.answer_callback_query(call.id, get_text(lang_code, "language_set_to").format(lang_name=lang_name_display))
    
    admin_status = is_admin(user_id) # Check admin status
    main_markup = create_main_markup(user_id=user_id, is_admin=admin_status) # Pass user_id and admin_status
    
    # Resend welcome message in the new language
    welcome_message_key = "welcome_admin" if admin_status else "welcome"
    if admin_status:
        # Assuming admin dashboard might have a fixed language or its own i18n
        bot.send_message(call.message.chat.id, "Admin dashboard language updated (if applicable).", reply_markup=main_markup)
    else:
        bot.send_message(call.message.chat.id, get_text(lang_code, "welcome"), reply_markup=main_markup)

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
