from telebot import types
from utils.test_mode import load_test_mode

def create_main_markup(is_admin=False):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    
    if is_admin:
        # Admin menu
        markup.row('➕ Add User', '👤 Show User')
        markup.row('❌ Delete User', '📊 Server Info')
        markup.row('💾 Backup Server', '💳 Payment Settings')
        markup.row('📝 Edit Plans', '🔧 Payment Test')
        markup.row('📞 Edit Support')
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
        types.InlineKeyboardButton("📱 Android - Play Store", url="https://play.google.com/store/apps/details?id=app.hiddify.com&hl=en"),
        types.InlineKeyboardButton("📱 Android - GitHub", url="https://github.com/hiddify/hiddify-app/releases/download/v2.5.7/Hiddify-Android-arm64.apk"),
        types.InlineKeyboardButton("🍎 iOS", url="https://apps.apple.com/us/app/hiddify-proxy-vpn/id6596777532"),
        types.InlineKeyboardButton("🪟 Windows", url="https://github.com/hiddify/hiddify-app/releases/download/v2.5.7/Hiddify-Windows-Setup-x64.exe"),
        types.InlineKeyboardButton("💻 Other OS", url="https://github.com/hiddify/hiddify-app/releases/tag/v2.5.7")
    )
    return markup
