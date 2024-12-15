from telebot import types

def create_main_markup(is_admin=False):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    
    if is_admin:
        # Admin menu
        markup.row('➕ Add User', '👤 Show User')
        markup.row('❌ Delete User', '📊 Server Info')
        markup.row('💾 Backup Server', '💳 Payment Settings')
    else:
        # Client menu
        markup.row('📱 My Configs', '💰 Purchase Plan')
        markup.row('⬇️ Downloads', '📞 Support')
    
    return markup

def create_purchase_markup():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("30 GB - $1.80 💰", callback_data="purchase:30"),
        types.InlineKeyboardButton("60 GB - $3.00 💰", callback_data="purchase:60"),
        types.InlineKeyboardButton("100 GB - $4.20 💰", callback_data="purchase:100")
    )
    return markup

def create_downloads_markup():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("📱 Android - Play Store", url="your_playstore_link"),
        types.InlineKeyboardButton("📱 Android - GitHub", url="your_github_android_link"),
        types.InlineKeyboardButton("🍎 iOS", url="your_ios_link"),
        types.InlineKeyboardButton("🪟 Windows", url="your_github_windows_link"),
        types.InlineKeyboardButton("💻 Other OS", url="your_other_os_link")
    )
    return markup
