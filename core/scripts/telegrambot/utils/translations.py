from typing import Dict

# Available languages
LANGUAGES = {
    "en": "English 🇬🇧",
    "fa": "Persian 🇮🇷",
    "tk": "Turkmen 🇹🇲"
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
    },
    "tk": {
        "my_configs": "📱 Meniň sazlamalarym",
        "purchase_plan": "💰 Töleg meýilnamasy",
        "downloads": "⬇️ Ýüklemeler",
        "test_config": "🎁 Synag sazlamalary",
        "support": "📞 Goldaw",
        "language": "🌐 Dil"
    }
}

# Messages translations
MESSAGE_TRANSLATIONS = {
    "en": {
        "select_platform": "🔴 **Important: Select your actual country in the software."
    },
    "fa": {
        "select_platform": "🔴 **مهم: در نرم افزار، کشور واقعی خودتان را انتخاب کنید."
    },
    "tk": {
        "select_platform": "🔴 ** Möhüm: Programma üpjünçiliginde hakyky ýurduňyzy saýlaň."
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