from telebot import types
import json
import os

# Language emojis
LANGUAGE_EMOJIS = {
    'en': '🇺🇸 English',
    'fa': '🇮🇷 فارسی',
    'tk': '🇹🇲 Türkmençe',
    'hi': '🇮🇳 हिंदी',
    'ar': '🇸🇦 العربية',
    'ru': '🇷🇺 Русский'
}

# Translations for all supported languages
TRANSLATIONS = {
    'en': {
        'welcome': "Welcome to our VPN Service! 🌐\n\nHere you can:\n📱 View your configs\n💰 Purchase new plans\n⬇️ Download our apps\n📞 Get support\n\nPlease use the menu below to get started!",
        'select_language': "Please select your language:",
        'language_selected': "Language set to English!",
        'my_configs': "📱 My Configs",
        'purchase_plan': "💰 Purchase Plan",
        'downloads': "⬇️ Downloads",
        'support': "📞 Support",
        'no_configs': "You don't have any active configs. Use the Purchase Plan button to buy one!",
        'select_plan': "Please select a plan:",
        'download_apps': "Download our apps for different platforms:",
        'support_message': "If you need help, please describe your issue and we'll respond as soon as possible."
    },
    'fa': {
        'welcome': "به سرویس VPN ما خوش آمدید! 🌐\n\nدر اینجا می‌توانید:\n📱 مشاهده پیکربندی‌ها\n💰 خرید پلن جدید\n⬇️ دانلود اپلیکیشن‌ها\n📞 پشتیبانی\n\nلطفاً از منوی زیر شروع کنید!",
        'select_language': "لطفاً زبان خود را انتخاب کنید:",
        'language_selected': "زبان به فارسی تغییر کرد!",
        'my_configs': "📱 پیکربندی‌های من",
        'purchase_plan': "💰 خرید پلن",
        'downloads': "⬇️ دانلود‌ها",
        'support': "📞 پشتیبانی",
        'no_configs': "شما هیچ پیکربندی فعالی ندارید. از دکمه خرید پلن برای خرید استفاده کنید!",
        'select_plan': "لطفاً یک پلن انتخاب کنید:",
        'download_apps': "دانلود اپلیکیشن‌های ما برای پلتفرم‌های مختلف:",
        'support_message': "اگر به کمک نیاز دارید، لطفاً مشکل خود را توضیح دهید و ما در اسرع وقت پاسخ خواهیم داد."
    },
    'tk': {
        'welcome': "VPN Hyzmatymyza hoş geldiňiz! 🌐\n\nBu ýerde siz:\n📱 Konfigurasiýalaryňyzy görüp bilersiňiz\n💰 Täze meýilnama satyn alyp bilersiňiz\n⬇️ Programmalarymyzy ýükläp bilersiňiz\n📞 Goldaw alyp bilersiňiz\n\nBaşlamak üçin aşakdaky menýuny ulanyň!",
        'select_language': "Diliňizi saýlaň:",
        'language_selected': "Dil türkmençä üýtgedildi!",
        'my_configs': "📱 Meniň konfigurasiýalarym",
        'purchase_plan': "💰 Meýilnama satyn al",
        'downloads': "⬇️ Ýüklemeler",
        'support': "📞 Goldaw",
        'no_configs': "Siziň işjeň konfigurasiýaňyz ýok. Satyn almak üçin Meýilnama satyn al düwmesini ulanyň!",
        'select_plan': "Meýilnama saýlaň:",
        'download_apps': "Dürli platformalar üçin programmalarymyzy ýükläň:",
        'support_message': "Kömek gerek bolsa, meseläňizi düşündiriň we biz mümkin bolan tiz wagtda jogap bereris."
    },
    'hi': {
        'welcome': "हमारी VPN सेवा में आपका स्वागत है! 🌐\n\nयहाँ आप:\n📱 अपने कॉन्फ़िगर देख सकते हैं\n💰 नई योजनाएँ खरीद सकते हैं\n⬇️ हमारी ऐप्स डाउनलोड कर सकते हैं\n📞 सहायता प्राप्त कर सकते हैं\n\nशुरू करने के लिए नीचे दिए मेनू का उपयोग करें!",
        'select_language': "कृपया अपनी भाषा चुनें:",
        'language_selected': "भाषा हिंदी में सेट की गई!",
        'my_configs': "📱 मेरे कॉन्फ़िगर",
        'purchase_plan': "💰 योजना खरीदें",
        'downloads': "⬇️ डाउनलोड",
        'support': "📞 सहायता",
        'no_configs': "आपके पास कोई सक्रिय कॉन्फ़िगर नहीं है। खरीदने के लिए योजना खरीदें बटन का उपयोग करें!",
        'select_plan': "कृपया एक योजना चुनें:",
        'download_apps': "विभिन्न प्लेटफ़ॉर्म के लिए हमारी ऐप्स डाउनलोड करें:",
        'support_message': "यदि आपको सहायता की आवश्यकता है, तो कृपया अपनी समस्या बताएं और हम जल्द स�� जल्द जवाब देंगे।"
    },
    'ar': {
        'welcome': "مرحباً بك في خدمة VPN! 🌐\n\nهنا يمكنك:\n📱 عرض الإعدادات\n💰 شراء باقات جديدة\n⬇️ تحميل تطبيقاتنا\n📞 الدعم الفني\n\nيرجى استخدام القائمة أدناه للبدء!",
        'select_language': "الرجاء اختيار لغتك:",
        'language_selected': "تم تغيير اللغة إلى العربية!",
        'my_configs': "📱 إعداداتي",
        'purchase_plan': "💰 شراء باقة",
        'downloads': "⬇️ التحميلات",
        'support': "📞 الدعم",
        'no_configs': "ليس لديك أي إعدادات نشطة. استخدم زر شراء باقة للشراء!",
        'select_plan': "الرجاء اختيار باقة:",
        'download_apps': "حمل تطبيقاتنا لمختلف المنصات:",
        'support_message': "إذا كنت بحاجة إلى مساعدة، يرجى وصف مشكلتك وسنرد في أقرب وقت ممكن."
    },
    'ru': {
        'welcome': "Добро пожаловать в наш VPN сервис! 🌐\n\nЗдесь вы можете:\n📱 Просмотреть ваши конфигурации\n💰 Купить нов��е планы\n⬇️ Скачать наши приложения\n📞 Получить поддержку\n\nИспользуйте меню ниже, чтобы начать!",
        'select_language': "Пожалуйста, выберите ваш язык:",
        'language_selected': "Язык изменен на русский!",
        'my_configs': "📱 Мои конфигурации",
        'purchase_plan': "💰 Купить план",
        'downloads': "⬇️ Загрузки",
        'support': "📞 Поддержка",
        'no_configs': "У вас нет активных конфигураций. Используйте кнопку Купить план, чтобы приобрести!",
        'select_plan': "Пожалуйста, выберите план:",
        'download_apps': "Скачайте наши приложения для разных платформ:",
        'support_message': "Если вам нужна помощь, опишите вашу проблему, и мы ответим как можно скорее."
    }
}

def create_language_markup():
    """Create keyboard markup for language selection"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = [types.KeyboardButton(emoji_name) for emoji_name in LANGUAGE_EMOJIS.values()]
    markup.add(*buttons)
    return markup

def get_language_code(selected_language):
    """Get language code from selected language button text"""
    for code, emoji_name in LANGUAGE_EMOJIS.items():
        if emoji_name == selected_language:
            return code
    return 'en'  # Default to English if not found

def get_text(lang_code, key):
    """Get translated text for a given key and language"""
    try:
        return TRANSLATIONS[lang_code][key]
    except KeyError:
        # Fallback to English if translation not found
        return TRANSLATIONS['en'][key]

# User language preferences storage
USER_LANGUAGES_FILE = 'user_languages.json'

def load_user_languages():
    """Load user language preferences from file"""
    if os.path.exists(USER_LANGUAGES_FILE):
        try:
            with open(USER_LANGUAGES_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_user_languages(user_languages):
    """Save user language preferences to file"""
    with open(USER_LANGUAGES_FILE, 'w') as f:
        json.dump(user_languages, f)

def get_user_language(user_id):
    """Get language preference for a user"""
    user_languages = load_user_languages()
    return user_languages.get(str(user_id), 'en')

def set_user_language(user_id, lang_code):
    """Set language preference for a user"""
    user_languages = load_user_languages()
    user_languages[str(user_id)] = lang_code
    save_user_languages(user_languages)

def create_client_markup(lang_code):
    """Create client menu markup with translated buttons"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(
        get_text(lang_code, 'my_configs'),
        get_text(lang_code, 'purchase_plan')
    )
    markup.row(
        get_text(lang_code, 'downloads'),
        get_text(lang_code, 'support')
    )
    return markup 
