from telebot import types
from . import language_pack # Use relative import

def create_main_markup(is_admin=False, user_id=None): # Add user_id parameter
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    # Get localized strings for buttons
    my_configs_text = language_pack.get_string("my_configs", user_id=user_id)
    purchase_plan_text = language_pack.get_string("purchase_plan", user_id=user_id)
    downloads_text = language_pack.get_string("downloads", user_id=user_id)
    test_config_text = language_pack.get_string("test_config", user_id=user_id)
    support_text = language_pack.get_string("support", user_id=user_id)
    language_text = language_pack.get_string("language", user_id=user_id)

    if is_admin:
        # Admin menu (Assuming admin also needs localization, add keys to language_pack if needed)
        # For now, keeping admin buttons as is, or you can create admin specific keys
        markup.row('➕ Add User', '👤 Show User')
        markup.row('❌ Delete User', '📊 Server Info')
        markup.row('💾 Backup Server', '💳 Payment Settings')
        markup.row('📝 Edit Plans', '📢 Broadcast Message')
        markup.row('📞 Edit Support', language_text) # Add language button for admin too
    else:
        # Non-admin menu
        markup.row(my_configs_text, purchase_plan_text)
        markup.row(downloads_text, test_config_text)
        markup.row(support_text, language_text)
    return markup
