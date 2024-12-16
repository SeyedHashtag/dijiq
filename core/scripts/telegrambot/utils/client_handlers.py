from telebot import types
from utils.languages import *
from utils.client import *
from utils.common import create_main_markup, create_purchase_markup, create_downloads_markup
from utils.command import bot, is_admin

class ClientHandlers:
    def __init__(self, bot_instance):
        self.bot = bot_instance

    def handle_client_start(self, message):
        """Handle /start command for regular users"""
        user_lang = get_user_language(message.from_user.id)
        if not user_lang:
            markup = create_language_markup()
            self.bot.reply_to(
                message,
                "Please select your language:\n\nلطفاً زبان خود را انتخاب کنید:\nDiliňizi saýlaň:\nकृपया अपनी भाषा चुनें:\nالرجاء اختيار لغتك:\nПожалуйста, выберите ваш язык:",
                reply_markup=markup
            )
            return
        
        markup = create_client_markup(user_lang)
        welcome_text = get_text(user_lang, 'welcome')
        self.bot.reply_to(message, welcome_text, reply_markup=markup)

    def handle_language_selection(self, message):
        """Handle language selection from the language menu"""
        if is_admin(message.from_user.id):
            return
        
        lang_code = get_language_code(message.text)
        set_user_language(message.from_user.id, lang_code)
        
        # Show confirmation and main menu in selected language
        markup = create_client_markup(lang_code)
        self.bot.reply_to(
            message,
            get_text(lang_code, 'language_selected'),
            reply_markup=markup
        )
        
        # Send welcome message in selected language
        self.bot.send_message(
            message.chat.id,
            get_text(lang_code, 'welcome')
        )

    def handle_client_menu(self, message):
        """Handle client menu button clicks"""
        user_lang = get_user_language(message.from_user.id)
        
        if message.text == get_text(user_lang, 'my_configs'):
            show_user_configs(message)
        elif message.text == get_text(user_lang, 'purchase_plan'):
            show_purchase_menu(message)
        elif message.text == get_text(user_lang, 'downloads'):
            show_downloads(message)
        elif message.text == get_text(user_lang, 'support'):
            show_support(message)

    def register_handlers(self):
        """Register all client-related message handlers"""
        
        # Language selection handler
        self.bot.register_message_handler(
            self.handle_language_selection,
            func=lambda message: message.text in [emoji for emoji in LANGUAGE_EMOJIS.values()]
        )
        
        # Client menu handlers
        self.bot.register_message_handler(
            self.handle_client_menu,
            func=lambda message: not is_admin(message.from_user.id) and message.text in [
                get_text(get_user_language(message.from_user.id), 'my_configs'),
                get_text(get_user_language(message.from_user.id), 'purchase_plan'),
                get_text(get_user_language(message.from_user.id), 'downloads'),
                get_text(get_user_language(message.from_user.id), 'support')
            ]
        )
