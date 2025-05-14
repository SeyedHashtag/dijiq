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
        "purchase_plan": "💰 pay with crypto",
        "downloads": "⬇️ Downloads",
        "test_config": "🎁 Test Config",
        "support": "📞 Support",
        "language": "🌐 Language/زبان"
    },
    "fa": {
        "my_configs": "📱 پیکربندی‌های من",
        "purchase_plan": "💰 پرداخت با رمزارز",
        "downloads": "⬇️ دانلودها",
        "test_config": "🎁 پیکربندی آزمایشی",
        "support": "📞 پشتیبانی",
        "language": "🌐 Language/زبان"
    },
    "tk": {
        "my_configs": "📱 Meniň sazlamalarym",
        "purchase_plan": "💰 Kripto bilen töle",
        "downloads": "⬇️ Ýüklemeler",
        "test_config": "🎁 Synag sazlamalary",
        "support": "📞 Goldaw",
        "language": "🌐 Language/Dil"
    }
}

# Messages translations
MESSAGE_TRANSLATIONS = {
    "en": {
        "select_platform": "🔴 **Important: Select your actual country in the software.",
        "no_active_configs": "❌ You don't have any active configurations.\n\nPlease use the '🎁 Test Config' button to get a free test config or the '💰 Purchase Plan' button to buy a subscription.",
        "test_config_used": "⚠️ You have already used your free test config. Please purchase a plan for continued service.",
        "select_plan": "📱 Select a plan to purchase:"
    },
    "fa": {
        "select_platform": "🔴 **مهم: در نرم افزار، کشور واقعی خودتان را انتخاب کنید.",
        "no_active_configs": "❌ شما هیچ پیکربندی فعالی ندارید.\n\nلطفاً از دکمه '🎁 پیکربندی آزمایشی' برای دریافت پیکربندی آزمایشی رایگان یا دکمه '💰 پرداخت با رمزارز' برای خرید اشتراک استفاده کنید.",
        "test_config_used": "⚠️ شما قبلاً از پیکربندی آزمایشی رایگان خود استفاده کرده‌اید. لطفاً برای ادامه خدمات، یک اشتراک خریداری کنید.",
        "select_plan": "📱 یک طرح برای خرید انتخاب کنید:"
    },
    "tk": {
        "select_platform": "🔴 ** Möhüm: Programma üpjünçiliginde hakyky ýurduňyzy saýlaň.",
        "no_active_configs": "❌ Siziň işjeň sazlamalaňyz ýok.\n\nMugt synag sazlamasyny almak üçin '🎁 Synag sazlamalary' düwmesini ýa-da abunalyk satyn almak üçin '💰 Kripto bilen töle' düwmesini ulanyň.",
        "test_config_used": "⚠️ Siz eýýäm mugt synag sazlamaňyzy ulanypsyňyz. Hyzmaty dowam etdirmek üçin meýilnama satyn alyň.",
        "select_plan": "📱 Satyn almak üçin meýilnama saýlaň:"
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