from telebot import types
from utils.language import get_text

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
        # Non-admin menu - with translations
        markup.row(get_text('my_configs', user_id), get_text('purchase_plan', user_id))
        markup.row(get_text('downloads', user_id), get_text('test_config', user_id))
        markup.row(get_text('support', user_id), get_text('language', user_id))
    return markup
