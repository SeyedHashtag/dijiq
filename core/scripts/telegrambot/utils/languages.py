from telebot import types
import json
import os

# Language settings
LANGUAGES = {
    '🇺🇸 English': 'en',
    '🇮🇷 فارسی': 'fa',
    '🇹🇲 Türkmençe': 'tk',
    '🇸🇦 العربية': 'ar',
    '🇷🇺 Русский': 'ru'
}

TRANSLATIONS = {
    'en': {
        'welcome': "Welcome to our VPN Service! 🌐\n\nHere you can:\n📱 View your configs\n💰 Purchase new plans\n⬇️ Download our apps\n📞 Get support\n\nPlease use the menu below to get started!",
        'select_language': "Please select your language:",
        'language_selected': "Language set to English!",
        'my_configs': "📱 My Configs",
        'purchase_plan': "💰 Purchase Plan",
        'downloads': "⬇️ Downloads",
        'support': "📞 Support"
    },
    'fa': {
        'welcome': "به سرویس VPN ما خوش آمدید! 🌐\n\nدر اینجا می‌توانید:\n📱 مشاهده پیکربندی‌ها\n💰 خرید پلن جدید\n⬇️ دانلود اپلیکیشن‌ها\n📞 پشتیبانی\n\nلطفاً از منوی زیر شروع کنید!",
        'select_language': "لطفاً زبان خود را انتخاب کنید:",
        'language_selected': "زبان به فارسی تغییر کرد!",
        'my_configs': "📱 پیکربندی‌های من",
        'purchase_plan': "💰 خرید پلن",
        'downloads': "⬇️ دانلود‌ها",
        'support': "📞 پشتیبانی"
    },
    'tk': {
        'welcome': "VPN Hyzmatymyza hoş geldiňiz! 🌐\n\nBu ýerde siz:\n📱 Konfigurasiýalaryňyzy görüp bilersiňiz\n💰 Täze meýilnama satyn alyp bilersiňiz\n⬇️ Programmalarymyzy ýükläp bilersiňiz\n📞 Goldaw alyp bilersiňiz\n\nBaşlamak üçin aşakdaky menýuny ulanyň!",
        'select_language': "Diliňizi saýlaň:",
        'language_selected': "Dil türkmençä üýtgedildi!",
        'my_configs': "📱 Meniň konfigurasiýalarym",
        'purchase_plan': "💰 Meýilnama satyn al",
        'downloads': "⬇️ Ýüklemeler",
        'support': "📞 Goldaw"
    },
    'ar': {
        'welcome': "مرحباً بك في خدمة VPN! 🌐\n\nهنا يمكنك:\n📱 عرض الإعدادات\n💰 شراء باقات جديدة\n⬇️ تحميل تطبيقاتنا\n📞 الدعم الفني\n\nيرجى استخدام القائمة أدناه للبدء!",
        'select_language': "الرجاء اخ��يار لغتك:",
        'language_selected': "تم تغيير اللغة إلى العربية!",
        'my_configs': "📱 إعداداتي",
        'purchase_plan': "💰 شراء باقة",
        'downloads': "⬇️ التحميلات",
        'support': "📞 الدعم"
    },
    'ru': {
        'welcome': "Добро пожаловать в наш VPN сервис! 🌐\n\nЗдесь вы можете:\n📱 Просмотреть ваши конфигурации\n💰 Купить новые планы\n⬇️ Скачать наши приложения\n📞 Получить поддержку\n\nИспользуйте меню ниже, чтобы начать!",
        'select_language': "Пожалуйста, выберите ваш язык:",
        'language_selected': "Язык изменен на русский!",
        'my_configs': "📱 Мои конфигурации",
        'purchase_plan': "💰 Купить план",
        'downloads': "⬇️ Загрузки",
        'support': "📞 Поддержка"
    }
}

# File to store user language preferences
LANGUAGE_FILE = '/etc/hysteria/core/scripts/telegrambot/user_languages.json'

class LanguageManager:
    def __init__(self):
        self.user_languages = self.load_user_languages()

    def load_user_languages(self):
        """Load user language preferences from file"""
        if os.path.exists(LANGUAGE_FILE):
            try:
                with open(LANGUAGE_FILE, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def save_user_languages(self):
        """Save user language preferences to file"""
        try:
            os.makedirs(os.path.dirname(LANGUAGE_FILE), exist_ok=True)
            with open(LANGUAGE_FILE, 'w') as f:
                json.dump(self.user_languages, f)
        except Exception as e:
            print(f"Error saving language preferences: {str(e)}")

    def get_user_language(self, user_id):
        """Get language for a user"""
        return self.user_languages.get(str(user_id), 'en')

    def set_user_language(self, user_id, lang_code):
        """Set language for a user"""
        self.user_languages[str(user_id)] = lang_code
        self.save_user_languages()

    def get_text(self, lang_code, key):
        """Get translated text"""
        return TRANSLATIONS.get(lang_code, TRANSLATIONS['en']).get(key, TRANSLATIONS['en'][key])

    def create_language_markup(self):
        """Create language selection keyboard"""
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        for lang in LANGUAGES.keys():
            markup.add(types.KeyboardButton(lang))
        return markup

    def create_menu_markup(self, lang_code):
        """Create menu keyboard in specified language"""
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row(
            TRANSLATIONS[lang_code]['my_configs'],
            TRANSLATIONS[lang_code]['purchase_plan']
        )
        markup.row(
            TRANSLATIONS[lang_code]['downloads'],
            TRANSLATIONS[lang_code]['support']
        )
        return markup

    def get_language_code(self, language_text):
        """Get language code from button text"""
        return LANGUAGES.get(language_text, 'en') 
