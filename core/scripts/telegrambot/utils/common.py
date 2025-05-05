from telebot import types
from utils.translations import get_message
from utils.language import get_user_language

def create_main_markup(is_admin=False, user_id=None):
    """Create the main keyboard markup for a user
    
    Args:
        is_admin (bool): Whether the user is an admin
        user_id (int): Telegram user ID for language preferences
        
    Returns:
        types.ReplyKeyboardMarkup: The keyboard markup
    """
    # Get user's language preference, default to English if not specified
    lang_code = 'en'
    if user_id is not None:
        lang_code = get_user_language(user_id)
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    if is_admin:
        # Admin menu - no translation for admin panel for simplicity
        markup.row('➕ Add User', '👤 Show User')
        markup.row('❌ Delete User', '📊 Server Info')
        markup.row('💾 Backup Server', '💳 Payment Settings')
        markup.row('📝 Edit Plans', '📢 Broadcast Message')
        markup.row('📞 Edit Support')
    else:
        # Regular user menu with translations
        markup.row(
            get_message('btn_my_configs', lang_code), 
            get_message('btn_purchase_plan', lang_code)
        )
        markup.row(
            get_message('btn_downloads', lang_code), 
            get_message('btn_test_config', lang_code)
        )
        markup.row(
            get_message('btn_support', lang_code),
            get_message('btn_language', lang_code)
        )
    return markup

def send_welcome(message, restart=False):
    """Send welcome message with the main menu
    
    Args:
        message: Telegram message object
        restart (bool): Whether this is a language change/restart
    """
    from utils.command import is_admin, bot
    
    user_id = message.from_user.id
    admin = is_admin(user_id)
    lang_code = get_user_language(user_id)
    
    # Get translated welcome message
    welcome_text = get_message('welcome', lang_code)
    
    # Send the welcome message with the appropriate markup
    bot.send_message(
        message.chat.id,
        welcome_text,
        reply_markup=create_main_markup(is_admin=admin, user_id=user_id)
    )
