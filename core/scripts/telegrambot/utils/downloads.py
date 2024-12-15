from telebot import types
from utils.command import bot
from utils.language import get_text, get_user_language

DOWNLOAD_LINKS = {
    'android_store': 'https://play.google.com/store/apps/details?id=app.hiddify.com',
    'android_direct': 'https://github.com/hiddify/hiddify-next/releases/download/v2.5.7/Hiddify-Android-arm64.apk',
    'ios': 'https://apps.apple.com/us/app/hiddify-proxy-vpn/id6596777532',
    'windows': 'https://github.com/hiddify/hiddify-next/releases/download/v2.5.7/Hiddify-Windows-Setup-x64.exe',
    'other': 'https://github.com/hiddify/hiddify-app/releases/tag/v2.5.7'
}

def create_downloads_markup(user_id):
    """Create markup for download options"""
    language = get_user_language(user_id)
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton(
            get_text(language, "android_store"),
            url=DOWNLOAD_LINKS['android_store']
        ),
        types.InlineKeyboardButton(
            get_text(language, "android_direct"),
            url=DOWNLOAD_LINKS['android_direct']
        ),
        types.InlineKeyboardButton(
            get_text(language, "ios"),
            url=DOWNLOAD_LINKS['ios']
        ),
        types.InlineKeyboardButton(
            get_text(language, "windows"),
            url=DOWNLOAD_LINKS['windows']
        ),
        types.InlineKeyboardButton(
            get_text(language, "other_platforms"),
            url=DOWNLOAD_LINKS['other']
        )
    )
    return markup

def show_downloads(message):
    """Show download options"""
    language = get_user_language(message.from_user.id)
    markup = create_downloads_markup(message.from_user.id)
    
    bot.reply_to(
        message,
        get_text(language, "download_links"),
        reply_markup=markup,
        parse_mode="Markdown",
        disable_web_page_preview=True
    ) 
