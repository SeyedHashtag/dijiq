from telebot import types
from utils.command import bot
from utils.languages import get_text, get_user_language

# Download links for different platforms
DOWNLOAD_LINKS = {
    "ios": "https://apps.apple.com/ca/app/karing/id6472431552",
    "android": "https://github.com/KaringX/karing/releases/download/v1.1.2.606/karing_1.1.2.606_android_arm64-v8a.apk",
    "windows": "https://github.com/KaringX/karing/releases/download/v1.1.2.606/karing_1.1.2.606_windows_x64.exe"
}

@bot.message_handler(func=lambda message: message.text == '⬇️ Downloads' or message.text == '⬇️ دانلودها')
def downloads(message):
    """Handle the Downloads button click"""
    user_id = message.from_user.id
    lang_code = get_user_language(user_id)
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    # Add buttons for each platform with localized text
    markup.add(
        types.InlineKeyboardButton(get_text("download_ios", lang_code), callback_data="download:ios"),
        types.InlineKeyboardButton(get_text("download_android", lang_code), callback_data="download:android"),
        types.InlineKeyboardButton(get_text("download_windows", lang_code), callback_data="download:windows")
    )
    
    bot.reply_to(
        message,
        get_text("download_select_platform", lang_code),
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('download:'))
def handle_download_selection(call):
    """Handle the platform selection for downloads"""
    try:
        user_id = call.from_user.id
        lang_code = get_user_language(user_id)
        
        bot.answer_callback_query(call.id)
        platform = call.data.split(':')[1]
        
        if platform in DOWNLOAD_LINKS:
            download_url = DOWNLOAD_LINKS[platform]
            
            # Create platform-specific messages using templates from language pack
            if platform == "ios":
                message = get_text("download_ios_message", lang_code).format(url=download_url)
            elif platform == "android":
                message = get_text("download_android_message", lang_code).format(url=download_url)
            elif platform == "windows":
                message = get_text("download_windows_message", lang_code).format(url=download_url)
            
            # Create markup with direct download link
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton(
                    get_text("download_direct_link", lang_code), 
                    url=download_url
                ),
                types.InlineKeyboardButton(
                    get_text("download_back_to_platforms", lang_code), 
                    callback_data="download:back"
                )
            )
            
            bot.edit_message_text(
                message,
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=markup,
                parse_mode="Markdown",
                disable_web_page_preview=False
            )
        elif platform == "back":
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                types.InlineKeyboardButton(get_text("download_ios", lang_code), callback_data="download:ios"),
                types.InlineKeyboardButton(get_text("download_android", lang_code), callback_data="download:android"),
                types.InlineKeyboardButton(get_text("download_windows", lang_code), callback_data="download:windows")
            )
            
            bot.edit_message_text(
                get_text("download_select_platform", lang_code),
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=markup
            )
    except Exception as e:
        bot.answer_callback_query(call.id, text=f"Error: {str(e)}")