from telebot import types
from utils.translations import get_button_text
from utils.language import get_user_language

def create_main_markup(is_admin=False, user_id=None):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    if is_admin:
        # Admin menu
        markup.row('➕ Add User', '👤 Show User')
        markup.row('❌ Delete User', '📊 Server Info')
        markup.row('💾 Backup Server', '💳 Payment Settings')
        markup.row('📝 Edit Plans', '📢 Broadcast Message')
        markup.row('📞 Edit Support')
    else:
        # Get user's language preference
        language = get_user_language(user_id) if user_id else "en"
        
        # Non-admin menu with translations
        markup.row(
            get_button_text(language, "my_configs"), 
            get_button_text(language, "purchase_plan")
        )
        markup.row(
            get_button_text(language, "downloads"), 
            get_button_text(language, "test_config")
        )
        markup.row(
            get_button_text(language, "support"), 
            get_button_text(language, "language")
        )
    return markup
