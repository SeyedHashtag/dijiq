from typing import Dict

# Available languages
LANGUAGES = {
    "en": "English 🇬🇧",
    "fa": "Persian 🇮🇷"
}

# Default language
DEFAULT_LANGUAGE = "en"

# Button translations for non-admin menu
BUTTON_TRANSLATIONS = {
    "en": {
        "my_configs": "📱 My Configs",
        "purchase_plan": "💰 Purchase Plan",
        "downloads": "⬇️ Downloads",
        "test_config": "🎁 Test Config",
        "support": "📞 Support",
        "language": "🌐 Language/زبان"
    },
    "fa": {
        "my_configs": "📱 پیکربندی‌های من",
        "purchase_plan": "💰 خرید با رمزارز",
        "downloads": "⬇️ دانلودها",
        "test_config": "🎁 پیکربندی آزمایشی",
        "support": "📞 پشتیبانی",
        "language": "🌐 زبان"
    }
}

# Messages translations
MESSAGE_TRANSLATIONS = {
    "en": {
        "select_platform": "📥 Select your platform to download the VPN client:"
    },
    "fa": {
        "select_platform": "📥 برای دانلود برنامه VPN، سیستم عامل خود را انتخاب کنید:"
    }
}

def get_button_text(language_code: str, button_key: str) -> str:
    """Get the translated text for a button key in the specified language.
    
    Args:
        language_code: The language code (e.g., 'en', 'fa')
        button_key: The key for the button text to translate
        
    Returns:
        The translated button text, or the English version if translation not found
    """
    if language_code not in BUTTON_TRANSLATIONS:
        language_code = DEFAULT_LANGUAGE
        
    translations = BUTTON_TRANSLATIONS[language_code]
    return translations.get(button_key, BUTTON_TRANSLATIONS[DEFAULT_LANGUAGE].get(button_key, ""))

def get_message_text(language_code: str, message_key: str) -> str:
    """Get the translated text for a message key in the specified language.
    
    Args:
        language_code: The language code (e.g., 'en', 'fa')
        message_key: The key for the message text to translate
        
    Returns:
        The translated message text, or the English version if translation not found
    """
    if language_code not in MESSAGE_TRANSLATIONS:
        language_code = DEFAULT_LANGUAGE
        
    translations = MESSAGE_TRANSLATIONS[language_code]
    return translations.get(message_key, MESSAGE_TRANSLATIONS[DEFAULT_LANGUAGE].get(message_key, ""))

# These functions will be overridden by the implementations in language.py
# They're provided as fallbacks
def get_user_language(user_id: int) -> str:
    """Get the language preference for a user."""
    return DEFAULT_LANGUAGE

def set_user_language(user_id: int, language_code: str) -> None:
    """Set the language preference for a user."""
    pass