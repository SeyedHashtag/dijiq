"""
Translations module for multi-language support
"""

# Main translations dictionary
# Structure: 
# {
#   "message_key": {
#       "en": "English text",
#       "fa": "Persian text"
#   }
# }
TRANSLATIONS = {
    # Welcome messages
    "welcome": {
        "en": "Welcome to Dijiq VPN Bot! What would you like to do?",
        "fa": "به ربات Dijiq VPN خوش آمدید! چه کاری می‌خواهید انجام دهید؟"
    },
    
    # Main menu buttons
    "btn_my_configs": {
        "en": "📱 My Configs",
        "fa": "📱 پیکربندی‌های من"
    },
    "btn_test_config": {
        "en": "🎁 Test Config",
        "fa": "🎁 پیکربندی آزمایشی"
    },
    "btn_purchase_plan": {
        "en": "💰 Purchase Plan",
        "fa": "💰 خرید پلن"
    },
    "btn_check_status": {
        "en": "🔄 Check Status",
        "fa": "🔄 بررسی وضعیت"
    },
    "btn_downloads": {
        "en": "⬇️ Downloads",
        "fa": "⬇️ دانلودها"
    },
    "btn_support": {
        "en": "🆘 Support",
        "fa": "🆘 پشتیبانی"
    },
    "btn_language": {
        "en": "🌐 Language",
        "fa": "🌐 زبان"
    },
    
    # Admin buttons
    "btn_admin_panel": {
        "en": "⚙️ Admin Panel",
        "fa": "⚙️ پنل مدیریت"
    },
    "btn_add_user": {
        "en": "➕ Add User",
        "fa": "➕ افزودن کاربر"
    },
    "btn_edit_user": {
        "en": "✏️ Edit User",
        "fa": "✏️ ویرایش کاربر"
    },
    "btn_delete_user": {
        "en": "🗑️ Delete User",
        "fa": "🗑️ حذف کاربر"
    },
    "btn_search_user": {
        "en": "🔍 Search User",
        "fa": "🔍 جستجوی کاربر"
    },
    "btn_server_info": {
        "en": "📊 Server Info",
        "fa": "📊 اطلاعات سرور"
    },
    "btn_payment_setup": {
        "en": "💲 Payment Setup",
        "fa": "💲 تنظیمات پرداخت"
    },
    "btn_edit_plans": {
        "en": "📝 Edit Plans",
        "fa": "📝 ویرایش پلن‌ها"
    },
    "btn_edit_support": {
        "en": "📢 Edit Support",
        "fa": "📢 ویرایش پشتیبانی"
    },
    "btn_broadcast": {
        "en": "📢 Broadcast Message",
        "fa": "📢 ارسال پیام همگانی"
    },
    "btn_backup": {
        "en": "💾 Backup",
        "fa": "💾 پشتیبان‌گیری"
    },
    
    # Download section
    "download_title": {
        "en": "📥 Select your platform to download the VPN client:",
        "fa": "📥 برای دانلود کلاینت VPN، پلتفرم خود را انتخاب کنید:"
    },
    "download_ios": {
        "en": "📱 iOS",
        "fa": "📱 آی‌او‌اس"
    },
    "download_android": {
        "en": "📱 Android",
        "fa": "📱 اندروید"
    },
    "download_windows": {
        "en": "💻 Windows",
        "fa": "💻 ویندوز"
    },
    
    # My configs section
    "no_configs": {
        "en": "❌ You don't have any active configurations.\n\nPlease use the '🎁 Test Config' button to get a free test config or the '💰 Purchase Plan' button to buy a subscription.",
        "fa": "❌ شما هیچ پیکربندی فعالی ندارید.\n\nلطفاً از دکمه '🎁 پیکربندی آزمایشی' برای دریافت پیکربندی آزمایشی رایگان یا از دکمه '💰 خرید پلن' برای خرید اشتراک استفاده کنید."
    },
    "select_config": {
        "en": "📱 Select a configuration to view:",
        "fa": "📱 یک پیکربندی را برای مشاهده انتخاب کنید:"
    },
    "config_expired": {
        "en": "❌ Your configuration has expired!",
        "fa": "❌ پیکربندی شما منقضی شده است!"
    },
    
    # Common actions
    "cancel": {
        "en": "❌ Cancel",
        "fa": "❌ لغو"
    },
    "back": {
        "en": "◀️ Back",
        "fa": "◀️ بازگشت"
    },
    "error": {
        "en": "⚠️ Error: {message}",
        "fa": "⚠️ خطا: {message}"
    },
    
    # Language selection
    "select_language": {
        "en": "Please select your language / لطفا زبان خود را انتخاب کنید",
        "fa": "Please select your language / لطفا زبان خود را انتخاب کنید"
    },
    "language_set": {
        "en": "✅ Language set to English!",
        "fa": "✅ زبان به فارسی تغییر یافت!"
    }
}

def get_message(message_key, lang_code='en'):
    """
    Get a translated message for the specified language
    
    Args:
        message_key (str): The message key to look up
        lang_code (str): The language code (default: 'en')
        
    Returns:
        str: The translated message or English message if translation not found
    """
    if message_key not in TRANSLATIONS:
        return f"Missing translation: {message_key}"
    
    translations = TRANSLATIONS[message_key]
    
    # Return requested language or fall back to English if not available
    if lang_code in translations:
        return translations[lang_code]
    else:
        return translations.get('en', f"Missing {lang_code} translation for: {message_key}")
        
def get_formatted_message(message_key, lang_code='en', **kwargs):
    """
    Get a translated message with variable replacements
    
    Args:
        message_key (str): The message key to look up
        lang_code (str): The language code
        **kwargs: Variables to replace in the message
        
    Returns:
        str: The translated and formatted message
    """
    message = get_message(message_key, lang_code)
    try:
        return message.format(**kwargs)
    except KeyError as e:
        return f"{message} (Missing format variable: {str(e)})"
    except Exception:
        return message