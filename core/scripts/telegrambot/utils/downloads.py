import os
from telebot import types
from utils.command import bot
from utils.translations import BUTTON_TRANSLATIONS, get_message_text
from utils.language import get_user_language

# Download links for different platforms
DOWNLOAD_LINKS = {
    "hiddify": {
        "ios": "https://apps.apple.com/us/app/hiddify-proxy-vpn/id6596777532",
        "android": "https://github.com/hiddify/hiddify-next/releases/download/v2.0.5/Hiddify-Android-arm64.apk",
        "windows": "https://github.com/hiddify/hiddify-next/releases/download/v2.0.5/Hiddify-Windows-Setup-x64.exe"
    },
    "karing": {
        "ios": "https://apps.apple.com/ca/app/karing/id6472431552",
        "android": "https://github.com/KaringX/karing/releases/download/v1.1.2.606/karing_1.1.2.606_android_arm64-v8a.apk",
        "windows": "https://github.com/KaringX/karing/releases/download/v1.1.2.606/karing_1.1.2.606_windows_x64.exe"
    },
    "v2ray": {
        "android": "https://github.com/2dust/v2rayNG/releases/download/1.10.2/v2rayNG_1.10.2_arm64-v8a.apk",
        "windows": "https://github.com/2dust/v2rayN/releases/download/7.12.3/v2rayN-windows-64.zip"
    }
}

@bot.message_handler(func=lambda message: any(
    message.text == translations["downloads"] 
    for translations in BUTTON_TRANSLATIONS.values()
))
def downloads(message):
    """Handle the Downloads button click"""
    user_id = message.from_user.id
    language = get_user_language(user_id)

    # Dynamically determine available platforms
    available_platforms = set()
    for app_links in DOWNLOAD_LINKS.values():
        available_platforms.update(app_links.keys())
    platform_buttons = []
    if "ios" in available_platforms:
        platform_buttons.append(types.InlineKeyboardButton("📱 iOS", callback_data="download:ios"))
    if "android" in available_platforms:
        platform_buttons.append(types.InlineKeyboardButton("📱 Android", callback_data="download:android"))
    if "windows" in available_platforms:
        platform_buttons.append(types.InlineKeyboardButton("💻 Windows", callback_data="download:windows"))

    markup = types.InlineKeyboardMarkup(row_width=1)
    for btn in platform_buttons:
        markup.add(btn)

    bot.reply_to(
        message,
        get_message_text(language, "select_platform"),
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('download:'))
def handle_download_selection(call):
    """Handle the platform selection for downloads"""
    try:
        bot.answer_callback_query(call.id)
        data_parts = call.data.split(':')
        action = data_parts[1]
        user_id = call.from_user.id
        language = get_user_language(user_id)
        
        # Handle platform selection (iOS, Android, Windows)
        if action in ["ios", "android", "windows"]:
            platform = action
            # Show app selection menu (only apps that have this platform)
            markup = types.InlineKeyboardMarkup(row_width=1)
            for app in DOWNLOAD_LINKS:
                if platform in DOWNLOAD_LINKS[app]:
                    app_name = app.capitalize()
                    markup.add(types.InlineKeyboardButton(app_name, callback_data=f"download:app:{app}:{platform}"))
            markup.add(types.InlineKeyboardButton("◀️ Back to Platforms", callback_data="download:back"))
            
            # Create platform-specific title
            if platform == "ios":
                title = "📱 iOS - Select App"
            elif platform == "android":
                title = "📱 Android - Select App"
            else:
                title = "💻 Windows - Select App"
                
            bot.edit_message_text(
                title,
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=markup
            )
            
        # Handle app selection (Karing or Hiddify or v2ray)
        elif action == "app" and len(data_parts) == 4:
            app = data_parts[2]  # karing or hiddify or v2ray
            platform = data_parts[3]  # ios, android, windows
            
            if app in DOWNLOAD_LINKS and platform in DOWNLOAD_LINKS[app]:
                download_url = DOWNLOAD_LINKS[app][platform]
                app_name = app.capitalize()
                
                # Create app & platform-specific messages
                if platform == "ios":
                    message = (
                        f"📱 **iOS {app_name} Download**\n\n"
                        f"Download {app_name} from the App Store:\n\n"
                        f"[Download for iOS]({download_url})\n\n"
                        "After installation, use your subscription link or QR code to configure the app."
                    )
                elif platform == "android":
                    message = (
                        f"📱 **Android {app_name} Download**\n\n"
                        f"Download {app_name} APK directly:\n\n"
                        f"[Download for Android]({download_url})\n\n"
                        "After installation, allow installation from unknown sources if prompted, "
                        "then use your subscription link or QR code to configure the app."
                    )
                elif platform == "windows":
                    message = (
                        f"💻 **Windows {app_name} Download**\n\n"
                        f"Download {app_name} for Windows:\n\n"
                        f"[Download for Windows]({download_url})\n\n"
                        "After installation, use your subscription link or QR code to configure the app."
                    )
                
                # Create markup with direct download link
                markup = types.InlineKeyboardMarkup()
                markup.add(
                    types.InlineKeyboardButton("🔗 Direct Download Link", url=download_url),
                    types.InlineKeyboardButton("◀️ Back to App Selection", callback_data=f"download:{platform}"),
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
                
        # Handle back button to return to platform selection
        elif action == "back":
            # Dynamically determine available platforms for back button
            available_platforms = set()
            for app_links in DOWNLOAD_LINKS.values():
                available_platforms.update(app_links.keys())
            platform_buttons = []
            if "ios" in available_platforms:
                platform_buttons.append(types.InlineKeyboardButton("📱 iOS", callback_data="download:ios"))
            if "android" in available_platforms:
                platform_buttons.append(types.InlineKeyboardButton("📱 Android", callback_data="download:android"))
            if "windows" in available_platforms:
                platform_buttons.append(types.InlineKeyboardButton("💻 Windows", callback_data="download:windows"))
            markup = types.InlineKeyboardMarkup(row_width=1)
            for btn in platform_buttons:
                markup.add(btn)
            bot.edit_message_text(
                get_message_text(language, "select_platform"),
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=markup
            )
    except Exception as e:
        bot.answer_callback_query(call.id, text=f"Error: {str(e)}")