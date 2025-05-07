from telebot import types
from utils import *
from utils.language_pack import get_string, LANGUAGES # Import language pack
import threading
import time

# In-memory store for user language preferences
user_languages = {}

def get_user_lang(user_id):
    return user_languages.get(user_id, 'en') # Default to English

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    lang = get_user_lang(user_id)
    if is_admin(user_id):
        markup = create_main_markup(is_admin=True) # Assuming admin menu doesn't need i18n for now
        bot.reply_to(message, "Welcome to the Admin Dashboard!", reply_markup=markup)
    else:
        markup = create_main_markup(is_admin=False)
        # Update main menu buttons to use translated strings
        markup.keyboard[0][0] = get_string(lang, 'my_configs')
        markup.keyboard[0][1] = get_string(lang, 'purchase_plan')
        markup.keyboard[1][0] = get_string(lang, 'downloads')
        markup.keyboard[1][1] = get_string(lang, 'test_config')
        markup.keyboard[2][0] = get_string(lang, 'support')
        markup.keyboard[2][1] = get_string(lang, 'language')
        bot.reply_to(message, get_string(lang, 'welcome'), reply_markup=markup)

@bot.message_handler(func=lambda message: get_string(get_user_lang(message.from_user.id), 'language') in message.text)
def handle_language_selection(message):
    user_id = message.from_user.id
    lang = get_user_lang(user_id)
    markup = types.InlineKeyboardMarkup()
    for lang_code, lang_data in LANGUAGES.items():
        # Assuming each language pack has a 'language_name' key like "English" or "فارسی"
        # For now, using the lang_code as a placeholder if 'language_name' isn't there
        button_text = lang_data.get('language_name', lang_code.upper())
        markup.add(types.InlineKeyboardButton(text=button_text, callback_data=f"set_lang_{lang_code}"))
    bot.reply_to(message, get_string(lang, 'select_language'), reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('set_lang_'))
def callback_set_language(call):
    user_id = call.from_user.id
    lang_code = call.data.split('_')[2]
    user_languages[user_id] = lang_code
    lang = get_user_lang(user_id)

    bot.answer_callback_query(call.id, get_string(lang, 'language_changed'))
    # Send a new welcome message with the updated language and menu
    if is_admin(user_id):
        markup = create_main_markup(is_admin=True)
        bot.send_message(call.message.chat.id, "Welcome to the Admin Dashboard!", reply_markup=markup) # Admin welcome
    else:
        markup = create_main_markup(is_admin=False)
        markup.keyboard[0][0] = get_string(lang, 'my_configs')
        markup.keyboard[0][1] = get_string(lang, 'purchase_plan')
        markup.keyboard[1][0] = get_string(lang, 'downloads')
        markup.keyboard[1][1] = get_string(lang, 'test_config')
        markup.keyboard[2][0] = get_string(lang, 'support')
        markup.keyboard[2][1] = get_string(lang, 'language')
        bot.send_message(call.message.chat.id, get_string(lang, 'welcome'), reply_markup=markup)

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
