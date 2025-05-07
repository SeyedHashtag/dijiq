from telebot import types
from utils.command import bot
from utils.languages import get_text, get_user_language, set_user_language
from utils.common import create_main_markup

@bot.message_handler(func=lambda message: message.text == "🌐 Language" or message.text == "🌐 زبان")
def language_selection(message):
    """Handle language selection button"""
    user_id = message.from_user.id
    lang_code = get_user_language(user_id)
    
    # Create inline keyboard for language selection
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    # Add language buttons
    btn_en = types.InlineKeyboardButton(
        get_text("language_en", lang_code), 
        callback_data="lang:en"
    )
    btn_fa = types.InlineKeyboardButton(
        get_text("language_fa", lang_code),
        callback_data="lang:fa"
    )
    
    markup.add(btn_en, btn_fa)
    
    # Send language selection message
    bot.reply_to(
        message,
        get_text("language_select", lang_code),
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("lang:"))
def handle_language_callback(call):
    """Handle language selection callback"""
    user_id = call.from_user.id
    new_lang = call.data.split(":")[1]
    
    # Set user's language preference
    set_user_language(user_id, new_lang)
    
    # Confirm language change
    bot.answer_callback_query(call.id)
    
    # Update the message
    bot.edit_message_text(
        get_text("language_changed", new_lang),
        chat_id=call.message.chat.id,
        message_id=call.message.message_id
    )
    
    # Send updated main menu in the new language
    bot.send_message(
        call.message.chat.id,
        get_text("welcome_message", new_lang),
        reply_markup=create_main_markup(
            is_admin=call.message.chat.id in bot.admin_ids,
            lang_code=new_lang
        )
    )