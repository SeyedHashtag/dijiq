from telebot import types

def create_main_markup(is_admin=False):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    if is_admin:
        # Admin menu
        markup.row('Add User', 'Show User')
        markup.row('Delete User', 'Server Info')
        markup.row('Backup Server')
        markup.row('💳 Payment Settings')
    else:
        # Non-admin menu
        markup.row('📱 My Configs', '💰 Purchase Plan')
        markup.row('⬇️ Downloads', '📞 Support')
        markup.row('🎁 Test Config')
    return markup
