"""
Language management for the Telegram bot.
This module handles language selection, storage, and retrieval.
"""

import json
import os
import threading
from telebot import types
from utils.translations import LANGUAGES, TRANSLATIONS
from utils.command import bot

# File to store user language preferences
LANGUAGE_FILE = 'user_languages.json'
DEFAULT_LANGUAGE = 'en'

# Thread lock for file operations
file_lock = threading.Lock()

def load_language_preferences():
    """Load user language preferences from file."""
    try:
        if not os.path.exists(LANGUAGE_FILE):
            return {}
        
        with file_lock:
            with open(LANGUAGE_FILE, 'r') as file:
                return json.load(file)
    except Exception as e:
        print(f"Error loading language preferences: {str(e)}")
        return {}

def save_language_preference(user_id, language_code):
    """Save user language preference to file."""
    try:
        user_id_str = str(user_id)
        preferences = load_language_preferences()
        
        with file_lock:
            preferences[user_id_str] = language_code
            with open(LANGUAGE_FILE, 'w') as file:
                json.dump(preferences, file)
    except Exception as e:
        print(f"Error saving language preference: {str(e)}")

def get_user_language(user_id):
    """Get user's preferred language code."""
    preferences = load_language_preferences()
    user_id_str = str(user_id)
    return preferences.get(user_id_str, DEFAULT_LANGUAGE)

def get_text(key, user_id, **kwargs):
    """Get translated text for a given key and user."""
    language = get_user_language(user_id)
    
    # If the language doesn't exist, fall back to default
    if language not in LANGUAGES:
        language = DEFAULT_LANGUAGE
    
    # If the key doesn't exist, return the key itself
    if key not in TRANSLATIONS:
        return key
    
    # If the language is not available for this key, fall back to default
    if language not in TRANSLATIONS[key]:
        text = TRANSLATIONS[key].get(DEFAULT_LANGUAGE, key)
    else:
        text = TRANSLATIONS[key][language]
    
    # Format with any provided parameters
    if kwargs:
        try:
            return text.format(*kwargs.values())
        except:
            return text
    
    return text

def create_language_keyboard():
    """Create a keyboard for language selection."""
    markup = types.InlineKeyboardMarkup()
    
    for code, name in LANGUAGES.items():
        markup.add(types.InlineKeyboardButton(name, callback_data=f"lang:{code}"))
    
    return markup

def update_client_menu(user_language):
    """Get the translated client menu items."""
    return {
        'my_configs': get_text('my_configs', user_language),
        'purchase_plan': get_text('purchase_plan', user_language),
        'downloads': get_text('downloads', user_language),
        'test_config': get_text('test_config', user_language),
        'support': get_text('support', user_language),
        'language': get_text('language', user_language),
    }

@bot.callback_query_handler(func=lambda call: call.data.startswith('lang:'))
def handle_language_selection(call):
    """Handle language selection callback."""
    language_code = call.data.split(':')[1]
    user_id = call.from_user.id
    
    # Save user's language preference
    save_language_preference(user_id, language_code)
    
    # Send confirmation message
    bot.answer_callback_query(call.id)
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=get_text('language_set', user_id)
    )