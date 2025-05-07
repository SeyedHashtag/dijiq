from telebot import types
from utils import *
from utils import language_pack # Import the new language_pack
import threading
import time

@bot.message_handler(func=lambda message: language_pack.get_string("language", user_id=message.from_user.id) in message.text)
def handle_language_selection(message):
    user_id = message.from_user.id
    markup = types.InlineKeyboardMarkup()
    available_langs = language_pack.get_available_languages()
    for lang_code, lang_name in available_langs.items():
        markup.add(types.InlineKeyboardButton(lang_name, callback_data=f"set_lang_{lang_code}"))
    bot.reply_to(message, language_pack.get_string("select_language", user_id=user_id), reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('set_lang_'))
def callback_set_language(call):
    user_id = call.from_user.id
    lang_code = call.data.split('_')[-1]
    available_langs = language_pack.get_available_languages()
    if language_pack.set_user_language(user_id, lang_code):
        lang_name = available_langs.get(lang_code, lang_code)
        bot.answer_callback_query(call.id, language_pack.get_string("language_changed", user_id=user_id).format(lang_name=lang_name))
        # Update the main menu with the new language
        if is_admin(user_id):
            markup = create_main_markup(is_admin=True)
            bot.send_message(user_id, language_pack.get_string("main_menu", user_id=user_id), reply_markup=markup)
        else:
            markup = create_main_markup(is_admin=False)
            bot.send_message(user_id, language_pack.get_string("main_menu", user_id=user_id), reply_markup=markup)
    else:
        bot.answer_callback_query(call.id, "Error changing language.")

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id # Get user_id
    if is_admin(user_id):
        markup = create_main_markup(is_admin=True)
        # Use get_string for localization
        bot.reply_to(message, language_pack.get_string("welcome", user_id=user_id) + " Admin!", reply_markup=markup)
    else:
        markup = create_main_markup(is_admin=False)
        # Use get_string for localization
        bot.reply_to(message, language_pack.get_string("welcome", user_id=user_id), reply_markup=markup)

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
