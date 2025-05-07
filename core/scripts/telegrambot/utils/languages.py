"""
Language module for the Telegram bot.
This module contains language packs for different languages.
"""

# Dictionary of language packs
LANGUAGES = {
    "en": {
        # Common messages
        "welcome_message": "Welcome to Dijiq VPN bot! Please select an option from the menu below.",
        "operation_canceled": "Operation canceled.",
        
        # Button labels
        "btn_purchase_plan": "💰 Purchase Plan",
        "btn_my_configs": "📱 My Configs",
        "btn_downloads": "⬇️ Downloads",
        "btn_test_config": "🎁 Test Config",
        "btn_language": "🌐 Language",
        "btn_support": "📞 Support",
        "btn_back": "◀️ Back",
        "btn_cancel": "❌ Cancel",
        
        # Download screen
        "download_select_platform": "📥 Select your platform to download the VPN client:",
        "download_ios": "📱 iOS",
        "download_android": "📱 Android",
        "download_windows": "💻 Windows",
        "download_ios_message": "📱 **iOS Download**\n\nDownload Karing from the App Store:\n\n[Download for iOS]({url})\n\nAfter installation, use your subscription link or QR code to configure the app.",
        "download_android_message": "📱 **Android Download**\n\nDownload Karing APK directly:\n\n[Download for Android]({url})\n\nAfter installation, allow installation from unknown sources if prompted, then use your subscription link or QR code to configure the app.",
        "download_windows_message": "💻 **Windows Download**\n\nDownload Karing for Windows:\n\n[Download for Windows]({url})\n\nAfter installation, use your subscription link or QR code to configure the app.",
        "download_direct_link": "🔗 Direct Download Link",
        "download_back_to_platforms": "◀️ Back to Platforms",
        
        # My Configs screen
        "my_configs_error_api": "⚠️ Error connecting to API. Please try again later.",
        "my_configs_no_configs": "❌ You don't have any active configurations.\n\nPlease use the '🎁 Test Config' button to get a free test config or the '💰 Purchase Plan' button to buy a subscription.",
        "my_configs_select": "📱 Select a configuration to view:",
        "my_configs_expired": "❌ **Your configuration has expired!**\n{details}\n\nPlease use the '💰 Purchase Plan' button to buy a new subscription.",
        "my_configs_error_url": "⚠️ Error: Could not generate subscription URL for '{username}'. Please contact support.",
        
        # Language selection
        "language_select": "🌐 Select your preferred language:",
        "language_en": "🇺🇸 English",
        "language_fa": "🇮🇷 Persian (فارسی)",
        "language_changed": "✅ Language changed to English.",
        
        # Test Config screen
        "test_config_success": "✅ Your test configuration has been created successfully! Here are the details:",
        "test_config_error": "❌ Failed to create test configuration. Please try again later.",
        
        # Support screen
        "support_message": "📞 Need help? Contact our support team:\n\n{support_info}\n\nPlease include your username in your message for faster assistance.",
    },
    
    "fa": {
        # Common messages
        "welcome_message": "به ربات Dijiq VPN خوش آمدید! لطفا یک گزینه را از منو زیر انتخاب کنید.",
        "operation_canceled": "عملیات لغو شد.",
        
        # Button labels
        "btn_purchase_plan": "💰 خرید پلن",
        "btn_my_configs": "📱 پیکربندی‌های من",
        "btn_downloads": "⬇️ دانلودها",
        "btn_test_config": "🎁 پیکربندی آزمایشی",
        "btn_language": "🌐 زبان",
        "btn_support": "📞 پشتیبانی",
        "btn_back": "◀️ بازگشت",
        "btn_cancel": "❌ لغو",
        
        # Download screen
        "download_select_platform": "📥 پلتفرم خود را برای دانلود کلاینت VPN انتخاب کنید:",
        "download_ios": "📱 آیفون",
        "download_android": "📱 اندروید",
        "download_windows": "💻 ویندوز",
        "download_ios_message": "📱 **دانلود برای آیفون**\n\nاپلیکیشن Karing را از اپ استور دانلود کنید:\n\n[دانلود برای آیفون]({url})\n\nپس از نصب، از لینک اشتراک یا کد QR خود برای پیکربندی برنامه استفاده کنید.",
        "download_android_message": "📱 **دانلود برای اندروید**\n\nفایل APK اپلیکیشن Karing را مستقیما دانلود کنید:\n\n[دانلود برای اندروید]({url})\n\nپس از نصب، در صورت درخواست، اجازه نصب از منابع ناشناس را بدهید. سپس از لینک اشتراک یا کد QR خود برای پیکربندی برنامه استفاده کنید.",
        "download_windows_message": "💻 **دانلود برای ویندوز**\n\nاپلیکیشن Karing را برای ویندوز دانلود کنید:\n\n[دانلود برای ویندوز]({url})\n\nپس از نصب، از لینک اشتراک یا کد QR خود برای پیکربندی برنامه استفاده کنید.",
        "download_direct_link": "🔗 لینک مستقیم دانلود",
        "download_back_to_platforms": "◀️ بازگشت به پلتفرم‌ها",
        
        # My Configs screen
        "my_configs_error_api": "⚠️ خطا در اتصال به API. لطفا بعدا دوباره امتحان کنید.",
        "my_configs_no_configs": "❌ شما هیچ پیکربندی فعالی ندارید.\n\nلطفا از دکمه '🎁 پیکربندی آزمایشی' برای دریافت یک پیکربندی آزمایشی رایگان یا از دکمه '💰 خرید پلن' برای خرید اشتراک استفاده کنید.",
        "my_configs_select": "📱 یک پیکربندی را برای مشاهده انتخاب کنید:",
        "my_configs_expired": "❌ **پیکربندی شما منقضی شده است!**\n{details}\n\nلطفا از دکمه '💰 خرید پلن' برای خرید اشتراک جدید استفاده کنید.",
        "my_configs_error_url": "⚠️ خطا: تولید URL اشتراک برای '{username}' امکان‌پذیر نیست. لطفا با پشتیبانی تماس بگیرید.",
        
        # Language selection
        "language_select": "🌐 زبان مورد نظر خود را انتخاب کنید:",
        "language_en": "🇺🇸 انگلیسی (English)",
        "language_fa": "🇮🇷 فارسی",
        "language_changed": "✅ زبان به فارسی تغییر کرد.",
        
        # Test Config screen
        "test_config_success": "✅ پیکربندی آزمایشی شما با موفقیت ایجاد شد! جزئیات آن:",
        "test_config_error": "❌ ایجاد پیکربندی آزمایشی ناموفق بود. لطفا بعدا دوباره امتحان کنید.",
        
        # Support screen
        "support_message": "📞 به کمک نیاز دارید؟ با تیم پشتیبانی ما تماس بگیرید:\n\n{support_info}\n\nلطفا برای کمک سریع‌تر، نام کاربری خود را در پیام خود ذکر کنید.",
    }
}

# Default language
DEFAULT_LANGUAGE = "en"

# User language preferences - dictionary to store user language preferences: {user_id: language_code}
user_preferences = {}

def get_text(key, lang_code="en"):
    """
    Get a text string in the specified language.
    
    Args:
        key (str): The text key to retrieve
        lang_code (str): The language code ('en' or 'fa')
        
    Returns:
        str: The localized text
    """
    # Use default language if the requested language is not available
    if lang_code not in LANGUAGES:
        lang_code = DEFAULT_LANGUAGE
        
    # Return the text or the key itself if text is not found
    return LANGUAGES[lang_code].get(key, key)

def get_user_language(user_id):
    """
    Get the language preference for a user.
    
    Args:
        user_id (int): Telegram user ID
        
    Returns:
        str: Language code ('en' or 'fa')
    """
    return user_preferences.get(user_id, DEFAULT_LANGUAGE)

def set_user_language(user_id, lang_code):
    """
    Set the language preference for a user.
    
    Args:
        user_id (int): Telegram user ID
        lang_code (str): Language code ('en' or 'fa')
    """
    user_preferences[user_id] = lang_code