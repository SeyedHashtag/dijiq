from telebot import types
from .language import get_text, get_user_language # Import language functions

def create_main_markup(user_id, is_admin=False): # Add user_id
    lang_code = get_user_language(user_id) # Get user's language
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    if is_admin:
        # Admin menu - Assuming admin interface is not multilingual for now or uses a default language
        # If admin also needs i18n, apply get_text here as well
        markup.row('➕ Add User', '👤 Show User')
        markup.row('❌ Delete User', '📊 Server Info')
        markup.row('💾 Backup Server', '💳 Payment Settings')
        markup.row('📝 Edit Plans', '📢 Broadcast Message')
        markup.row('📞 Edit Support')
    else:
        # Non-admin menu
        markup.row(get_text(lang_code, 'my_configs'), get_text(lang_code, 'purchase_plan'))
        markup.row(get_text(lang_code, 'downloads'), get_text(lang_code, 'test_config'))
        markup.row(get_text(lang_code, 'support'), get_text(lang_code, 'language'))
    return markup
