"""
Language selection functionality for the Telegram bot.
This module handles the language selection commands and callbacks.
"""

from telebot import types
from utils.command import bot, is_admin
from utils.common import create_main_markup
from utils.language import create_language_keyboard, get_text, get_user_language, save_language_preference

# Handler for the language button
@bot.message_handler(func=lambda message: not is_admin(message.from_user.id) and message.text == get_text('language', message.from_user.id))
def show_language_options(message):
    """Handle language button click for clients"""
    user_id = message.from_user.id
    keyboard = create_language_keyboard()
    bot.send_message(
        message.chat.id,
        get_text('select_language', user_id),
        reply_markup=keyboard
    )

# Callback for language selection
@bot.callback_query_handler(func=lambda call: call.data.startswith('lang:'))
def language_callback(call):
    """Handle language selection via inline buttons"""
    language_code = call.data.split(':')[1]
    user_id = call.from_user.id
    
    # Save user's language preference
    save_language_preference(user_id, language_code)
    
    # Send confirmation message
    bot.answer_callback_query(call.id)
    bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)
    
    # Show main menu with translated buttons
    markup = create_main_markup(is_admin=False, user_id=user_id)
    bot.send_message(
        call.message.chat.id,
        get_text('language_set', user_id),
        reply_markup=markup
    )