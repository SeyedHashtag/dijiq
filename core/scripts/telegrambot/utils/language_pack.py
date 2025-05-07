\
LANGUAGES = {
    "en": {
        "welcome": "Welcome!",
        "main_menu": "Main Menu",
        "my_configs": "📱 My Configs",
        "purchase_plan": "💰 Purchase Plan",
        "downloads": "⬇️ Downloads",
        "test_config": "🎁 Test Config",
        "support": "📞 Support",
        "language": "🌐 Language",
        "select_language": "Please select your language:",
        "language_changed": "Language changed to {lang_name}.",
        # Add other strings here
    },
    "fa": {
        "welcome": "خوش آمدید!",
        "main_menu": "منوی اصلی",
        "my_configs": "📱 تنظیمات من",
        "purchase_plan": "💰 خرید طرح",
        "downloads": "⬇️ دانلودها",
        "test_config": "🎁 تنظیمات تست",
        "support": "📞 پشتیبانی",
        "language": "🌐 زبان",
        "select_language": "لطفا زبان خود را انتخاب کنید:",
        "language_changed": "زبان به {lang_name} تغییر یافت.",
        # Add other strings here
    }
}

DEFAULT_LANG = "en"
USER_LANGUAGES = {} # In a real bot, this would be stored in a database

def get_string(key, lang=None, user_id=None):
    """
    Gets a string in the specified language.
    If user_id is provided, it tries to get the user's preferred language.
    Falls back to lang, then DEFAULT_LANG.
    """
    resolved_lang = DEFAULT_LANG
    if user_id and user_id in USER_LANGUAGES:
        resolved_lang = USER_LANGUAGES[user_id]
    elif lang:
        resolved_lang = lang

    return LANGUAGES.get(resolved_lang, {}).get(key, LANGUAGES[DEFAULT_LANG].get(key, key))

def set_user_language(user_id, lang_code):
    """Sets the user's preferred language."""
    if lang_code in LANGUAGES:
        USER_LANGUAGES[user_id] = lang_code
        return True
    return False

def get_available_languages():
    """Returns a dictionary of available language codes and their native names."""
    return {"en": "English", "fa": "فارسی (Persian)"}

