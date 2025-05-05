import os
import json
from telebot import types
from utils.command import bot

# Define available languages
LANGUAGES = {
    'en': 'English 🇺🇸',
    'fa': 'فارسی 🇮🇷'
}

# Path to language preferences file
LANGUAGE_FILE = "/etc/dijiq/core/scripts/telegrambot/user_languages.json"

def create_language_selection_markup():
    """Create a keyboard markup for language selection"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    for lang_code, lang_name in LANGUAGES.items():
        markup.add(types.InlineKeyboardButton(
            lang_name, 
            callback_data=f"set_lang:{lang_code}"
        ))
    
    return markup

def get_user_language(user_id):
    """Get the language preference for a user
    
    Args:
        user_id (int): Telegram user ID
        
    Returns:
        str: Language code (default: 'en')
    """
    try:
        if os.path.exists(LANGUAGE_FILE):
            with open(LANGUAGE_FILE, 'r') as f:
                languages = json.load(f)
                return languages.get(str(user_id), 'en')
        return 'en'  # Default language
    except Exception as e:
        print(f"Error reading language file: {str(e)}")
        return 'en'  # Default to English on error

def save_user_language(user_id, lang_code):
    """Save a user's language preference
    
    Args:
        user_id (int): Telegram user ID
        lang_code (str): Language code to save
    """
    try:
        languages = {}
        if os.path.exists(LANGUAGE_FILE):
            with open(LANGUAGE_FILE, 'r') as f:
                try:
                    languages = json.load(f)
                except:
                    languages = {}
        
        # Ensure the directory exists
        os.makedirs(os.path.dirname(LANGUAGE_FILE), exist_ok=True)
        
        # Update and save
        languages[str(user_id)] = lang_code
        with open(LANGUAGE_FILE, 'w') as f:
            json.dump(languages, f)
            
        return True
    except Exception as e:
        print(f"Error saving language preference: {str(e)}")
        return False

def show_language_selection(chat_id, message_text="Please select your language / لطفا زبان خود را انتخاب کنید"):
    """Show language selection keyboard to the user
    
    Args:
        chat_id (int): Telegram chat ID
        message_text (str): Optional custom message text
    """
    markup = create_language_selection_markup()
    bot.send_message(
        chat_id,
        message_text,
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('set_lang:'))
def handle_language_selection(call):
    """Handle language selection callback"""
    lang_code = call.data.split(':')[1]
    user_id = call.from_user.id
    
    if lang_code in LANGUAGES:
        # Save user's language preference
        save_user_language(user_id, lang_code)
        
        # Answer the callback query
        bot.answer_callback_query(call.id, f"Language set to {LANGUAGES[lang_code]}")
        
        # Update the message
        if lang_code == 'en':
            success_message = "✅ Language set to English!"
        elif lang_code == 'fa':
            success_message = "✅ زبان به فارسی تغییر یافت!"
        
        try:
            bot.edit_message_text(
                success_message,
                chat_id=call.message.chat.id,
                message_id=call.message.message_id
            )
        except:
            pass
        
        # Show main menu with newly selected language
        from utils.common import create_main_markup, send_welcome
        send_welcome(call.message, restart=True)