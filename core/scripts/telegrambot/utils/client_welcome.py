from telebot import types
from utils.command import bot, is_admin
from utils.languages import LanguageManager, LANGUAGES, TRANSLATIONS
from utils.client import show_my_configs, show_purchase_options, show_downloads, show_support
from utils.spam_protection import spam_protection

# Initialize language manager
lang_manager = LanguageManager()

def handle_start(message):
    """Handle /start command for regular users"""
    if str(message.from_user.id) not in lang_manager.user_languages:
        markup = lang_manager.create_language_markup()
        bot.reply_to(
            message,
            "Please select your language:\n\nلطفاً زبان خود را انتخاب کنید:\nDiliňizi saýlaň:\nالرجاء اختيار لغتك:\nПожалуйста, выберите ваш язык:",
            reply_markup=markup
        )
        return

    # If language is already set, show the main menu
    lang_code = lang_manager.get_user_language(message.from_user.id)
    markup = lang_manager.create_menu_markup(lang_code)
    bot.reply_to(
        message,
        lang_manager.get_text(lang_code, 'welcome'),
        reply_markup=markup
    )

def handle_language_selection(message):
    """Handle language selection from the language menu"""
    if is_admin(message.from_user.id):
        return

    if not spam_protection.can_send_message(message.from_user.id):
        bot.reply_to(message, "⚠️ You are sending messages too quickly. Please wait a moment and try again.")
        return

    lang_code = LANGUAGES.get(message.text)
    if not lang_code:
        return

    lang_manager.set_user_language(message.from_user.id, lang_code)
    
    # Show confirmation and main menu
    markup = lang_manager.create_menu_markup(lang_code)
    bot.reply_to(
        message,
        lang_manager.get_text(lang_code, 'language_selected'),
        reply_markup=markup
    )
    
    # Send welcome message
    bot.send_message(
        message.chat.id,
        lang_manager.get_text(lang_code, 'welcome')
    )

def handle_client_menu(message):
    """Handle client menu button clicks"""
    if is_admin(message.from_user.id):
        return

    if not spam_protection.can_send_message(message.from_user.id):
        bot.reply_to(message, "⚠️ You are sending messages too quickly. Please wait a moment and try again.")
        return
        
    user_lang = lang_manager.get_user_language(message.from_user.id)
    
    # Get all possible menu items for all languages
    menu_items = {
        'my_configs': [lang['my_configs'] for lang in TRANSLATIONS.values()],
        'purchase_plan': [lang['purchase_plan'] for lang in TRANSLATIONS.values()],
        'downloads': [lang['downloads'] for lang in TRANSLATIONS.values()],
        'support': [lang['support'] for lang in TRANSLATIONS.values()]
    }
    
    # Check which menu item was clicked
    if message.text in menu_items['my_configs']:
        show_my_configs(message)
    elif message.text in menu_items['purchase_plan']:
        show_purchase_options(message)
    elif message.text in menu_items['downloads']:
        show_downloads(message)
    elif message.text in menu_items['support']:
        show_support(message)

def register_handlers():
    """Register all client-related message handlers"""
    
    # Language selection handler
    bot.register_message_handler(
        handle_language_selection,
        func=lambda message: not is_admin(message.from_user.id) and message.text in LANGUAGES.keys()
    )
    
    # Client menu handlers - collect all possible menu items in all languages
    all_menu_items = []
    for lang in TRANSLATIONS.values():
        all_menu_items.extend([
            lang['my_configs'],
            lang['purchase_plan'],
            lang['downloads'],
            lang['support']
        ])
    
    # Register the menu handler
    bot.register_message_handler(
        handle_client_menu,
        func=lambda message: not is_admin(message.from_user.id) and message.text in all_menu_items
    ) 
