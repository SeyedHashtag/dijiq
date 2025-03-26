from telegram import Update, ParseMode
from telegram.ext import CallbackContext, CommandHandler, MessageHandler, Filters
from src.utils.config import is_admin
from src.utils.languages import LanguageManager, LANGUAGES
from src.bot.keyboards import get_main_menu_keyboard

# Initialize language manager
lang_manager = LanguageManager()

def handle_start(update: Update, context: CallbackContext) -> None:
    """Handle /start command for regular users"""
    if str(update.effective_user.id) not in lang_manager.user_languages:
        markup = lang_manager.create_language_markup()
        update.message.reply_text(
            "Please select your language:\n\nلطفاً زبان خود را انتخاب کنید:\nDiliňizi saýlaň:\nالرجاء اختيار لغتك:\nПожалуйста, выберите ваш язык:",
            reply_markup=markup
        )
        return

    # If language is already set, show the main menu
    lang_code = lang_manager.get_user_language(update.effective_user.id)
    markup = lang_manager.create_menu_markup(lang_code)
    update.message.reply_text(
        lang_manager.get_text(lang_code, 'welcome'),
        reply_markup=markup
    )

def handle_language_selection(update: Update, context: CallbackContext) -> None:
    """Handle language selection from the language menu"""
    if is_admin(update.effective_user.id):
        return

    lang_code = LANGUAGES.get(update.message.text)
    if not lang_code:
        return

    lang_manager.set_user_language(update.effective_user.id, lang_code)
    
    # Show confirmation and main menu
    markup = lang_manager.create_menu_markup(lang_code)
    update.message.reply_text(
        lang_manager.get_text(lang_code, 'language_selected'),
        reply_markup=markup
    )
    
    # Send welcome message
    update.message.reply_text(
        lang_manager.get_text(lang_code, 'welcome')
    )

def setup_client_welcome_handlers(dispatcher):
    """Register client welcome handlers"""
    # Language selection handler
    dispatcher.add_handler(
        MessageHandler(
            Filters.text & ~Filters.command & Filters.regex(f"^({'|'.join(LANGUAGES.keys())})$"),
            handle_language_selection
        )
    )
