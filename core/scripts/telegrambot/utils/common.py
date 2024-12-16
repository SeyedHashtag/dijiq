from telebot import types

def create_main_markup(is_admin=False):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    
    if is_admin:
        # Admin menu
        markup.row('➕ Add User', '👤 Show User')
        markup.row('❌ Delete User', '📊 Server Info')
        markup.row('💾 Backup Server', '💳 Payment Settings')
        markup.row('📝 Edit Plans')
    else:
        # Client menu
        markup.row('📱 My Configs', '💰 Purchase Plan')
        markup.row('⬇️ Downloads', '📞 Support')
    
    return markup

def create_purchase_markup():
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    # Load plans from file
    from utils.admin_plans import load_plans
    plans = load_plans()
    
    # Create buttons for each plan
    for gb, details in plans.items():
        markup.add(types.InlineKeyboardButton(
            f"{gb} GB - ${details['price']} 💰",
            callback_data=f"purchase:{gb}"
        ))
    
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
