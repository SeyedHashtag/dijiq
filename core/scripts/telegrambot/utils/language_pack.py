# Language pack for the Telegram bot

LANGUAGES = {
    "en": {
        "language_name": "English", # Added for button display
        "welcome": "Welcome!",
        "my_configs": "📱 My Configs",
        "purchase_plan": "💰 Purchase Plan",
        "downloads": "⬇️ Downloads",
        "test_config": "🎁 Test Config",
        "support": "📞 Support",
        "language": "🌐 Language",
        "select_language": "Please select your language:",
        "language_changed": "Language changed to English.",
        # Add other strings here
    },
    "fa": {
        "language_name": "فارسی", # Added for button display
        "welcome": "خوش آمدید!",
        "my_configs": "📱 تنظیمات من",
        "purchase_plan": "💰 خرید طرح",
        "downloads": "⬇️ دانلودها",
        "test_config": "🎁 تنظیمات تست",
        "support": "📞 پشتیبانی",
        "language": "🌐 زبان",
        "select_language": "لطفا زبان خود را انتخاب کنید:",
        "language_changed": "زبان به فارسی تغییر یافت.",
        # Add other strings here
    }
}

def get_string(lang_code, key):
    """
    Retrieves a string in the specified language.
    Defaults to English if the string is not found in the target language.
    """
    return LANGUAGES.get(lang_code, {}).get(key, LANGUAGES.get("en", {}).get(key, key))

