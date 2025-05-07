import os
import json
from telebot import types
from utils.command import bot
from utils.common import create_main_markup
from utils.translations import LANGUAGES, BUTTON_TRANSLATIONS

# Path to store user language preferences
LANGUAGE_PREFS_FILE = '/etc/dijiq/core/scripts/telegrambot/user_languages.json'

def load_user_languages():
    """Load user language preferences from file"""
    if os.path.exists(LANGUAGE_PREFS_FILE):
        try:
            with open(LANGUAGE_PREFS_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_user_languages(languages_data):
    """Save user language preferences to file"""
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(LANGUAGE_PREFS_FILE), exist_ok=True)
        with open(LANGUAGE_PREFS_FILE, 'w') as f:
            json.dump(languages_data, f, indent=2)
    except Exception as e:
        print(f"Error saving language preferences: {e}")

def get_user_language(user_id):
    """Get the language preference for a user"""
    user_id_str = str(user_id)
    languages = load_user_languages()
    return languages.get(user_id_str, "en")

def set_user_language(user_id, language_code):
    """Set the language preference for a user"""
    user_id_str = str(user_id)
    languages = load_user_languages()
    languages[user_id_str] = language_code
    save_user_languages(languages)

@bot.message_handler(func=lambda message: any(
    message.text == translations["language"] 
    for translations in BUTTON_TRANSLATIONS.values()
))
def language_selection(message):
    """Display language selection menu"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    # Create buttons for each available language
    language_buttons = []
    for code, name in LANGUAGES.items():
        language_buttons.append(types.InlineKeyboardButton(name, callback_data=f"lang:{code}"))
    
    markup.add(*language_buttons)
    
    bot.reply_to(
        message,
        "🌐 Select your language / زبان خود را انتخاب کنید:",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('lang:'))
def handle_language_selection(call):
    """Handle language selection from the inline keyboard"""
    language_code = call.data.split(':')[1]
    user_id = call.from_user.id
    
    # Save user's language preference
    set_user_language(user_id, language_code)
    
    # Get language name for the selected code
    language_name = LANGUAGES.get(language_code, "Unknown")
    
    # Update the message to indicate selected language
    bot.edit_message_text(
        f"✅ Language set to {language_name}",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id
    )
    
    # Update the main menu with the new language
    bot.send_message(
        call.message.chat.id,
        f"✅ Your language has been set to {language_name}",
        reply_markup=create_main_markup(is_admin=False, user_id=user_id)
    )