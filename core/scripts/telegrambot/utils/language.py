\
LANGUAGES = {
    "en": {
        "language_name": "English", # Added
        "welcome": "Welcome!",
        "my_configs": "📱 My Configs",
        "purchase_plan": "💰 Purchase Plan",
        "downloads": "⬇️ Downloads",
        "test_config": "🎁 Test Config",
        "support": "📞 Support",
        "language": "🌐 Language",
        "select_language": "Please select your language:",
        "language_set_to": "Language set to {lang_name}.",
        # Add other translations here
    },
    "fa": {
        "language_name": "فارسی", # Added
        "welcome": "خوش آمدید!",
        "my_configs": "📱 تنظیمات من",
        "purchase_plan": "💰 خرید طرح",
        "downloads": "⬇️ دانلودها",
        "test_config": "🎁 تنظیمات تست",
        "support": "📞 پشتیبانی",
        "language": "🌐 زبان",
        "select_language": "لطفا زبان خود را انتخاب کنید:",
        "language_set_to": "زبان به {lang_name} تغییر یافت.",
        # Add other translations here
    }
}

def get_text(lang_code, key):
    """Retrieves text for a given key in the specified language."""
    return LANGUAGES.get(lang_code, LANGUAGES["en"]).get(key, f"Missing translation for {key}")

# Store user language preferences (in a real bot, this would be a database)
USER_LANGUAGES = {}

def set_user_language(user_id, lang_code):
    """Sets the language for a given user."""
    USER_LANGUAGES[user_id] = lang_code

def get_user_language(user_id):
    """Gets the language for a given user, defaults to English."""
    return USER_LANGUAGES.get(user_id, "en")
