from telebot import types
from utils.languages import get_text, get_user_language

def create_main_markup(is_admin=False, lang_code="en"):
    """
    Create the main menu markup with localized button text
    
    Args:
        is_admin (bool): Whether the user is an admin
        lang_code (str): Language code for button text
        
    Returns:
        ReplyKeyboardMarkup: The keyboard markup
    """
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    if is_admin:
        # Admin menu (admin menus remain in English)
        markup.row('➕ Add User', '👤 Show User')
        markup.row('❌ Delete User', '📊 Server Info')
        markup.row('💾 Backup Server', '💳 Payment Settings')
        markup.row('📝 Edit Plans', '📢 Broadcast Message')
        markup.row('📞 Edit Support')
    else:
        # Regular user menu (localized)
        markup.row(
            get_text("btn_my_configs", lang_code),
            get_text("btn_purchase_plan", lang_code)
        )
        markup.row(
            get_text("btn_downloads", lang_code),
            get_text("btn_test_config", lang_code)
        )
        markup.row(
            get_text("btn_support", lang_code),
            get_text("btn_language", lang_code)
        )
    return markup
