import os
from telebot import types
from utils.command import bot
from utils.translations import BUTTON_TRANSLATIONS

# Download links for different platforms
DOWNLOAD_LINKS = {
    "ios": "https://apps.apple.com/ca/app/karing/id6472431552",
    "android": "https://github.com/KaringX/karing/releases/download/v1.1.2.606/karing_1.1.2.606_android_arm64-v8a.apk",
    "windows": "https://github.com/KaringX/karing/releases/download/v1.1.2.606/karing_1.1.2.606_windows_x64.exe"
}

@bot.message_handler(func=lambda message: any(
    message.text == translations["downloads"] 
    for translations in BUTTON_TRANSLATIONS.values()
))
def downloads(message):
    """Handle the Downloads button click"""
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    # Add buttons for each platform
    markup.add(
        types.InlineKeyboardButton("📱 iOS", callback_data="download:ios"),
        types.InlineKeyboardButton("📱 Android", callback_data="download:android"),
        types.InlineKeyboardButton("💻 Windows", callback_data="download:windows")
    )
    
    bot.reply_to(
        message,
        "📥 Select your platform to download the VPN client:",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('download:'))
def handle_download_selection(call):
    """Handle the platform selection for downloads"""
    try:
        bot.answer_callback_query(call.id)
        platform = call.data.split(':')[1]
        
        if platform in DOWNLOAD_LINKS:
            download_url = DOWNLOAD_LINKS[platform]
            
            # Create platform-specific messages
            if platform == "ios":
                message = (
                    "📱 **iOS Download**\n\n"
                    "Download Karing from the App Store:\n\n"
                    f"[Download for iOS]({download_url})\n\n"
                    "After installation, use your subscription link or QR code to configure the app."
                )
            elif platform == "android":
                message = (
                    "📱 **Android Download**\n\n"
                    "Download Karing APK directly:\n\n"
                    f"[Download for Android]({download_url})\n\n"
                    "After installation, allow installation from unknown sources if prompted, "
                    "then use your subscription link or QR code to configure the app."
                )
            elif platform == "windows":
                message = (
                    "💻 **Windows Download**\n\n"
                    "Download Karing for Windows:\n\n"
                    f"[Download for Windows]({download_url})\n\n"
                    "After installation, use your subscription link or QR code to configure the app."
                )
            
            # Create markup with direct download link
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton("🔗 Direct Download Link", url=download_url),
                types.InlineKeyboardButton("◀️ Back to Platforms", callback_data="download:back")
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
                types.InlineKeyboardButton("📱 iOS", callback_data="download:ios"),
                types.InlineKeyboardButton("📱 Android", callback_data="download:android"),
                types.InlineKeyboardButton("💻 Windows", callback_data="download:windows")
            )
            
            bot.edit_message_text(
                "📥 Select your platform to download the VPN client:",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=markup
            )
    except Exception as e:
        bot.answer_callback_query(call.id, text=f"Error: {str(e)}")