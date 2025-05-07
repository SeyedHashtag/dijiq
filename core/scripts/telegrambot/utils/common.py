from telebot import types

def create_main_markup_with_language(language_translations, is_admin=False):
    """
    Create a main menu markup with the given language translations.
    This function doesn't import language or translations to avoid circular imports.
    """
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    if is_admin:
        # Admin menu
        markup.row('➕ Add User', '👤 Show User')
        markup.row('❌ Delete User', '📊 Server Info')
        markup.row('💾 Backup Server', '💳 Payment Settings')
        markup.row('📝 Edit Plans', '📢 Broadcast Message')
        markup.row('📞 Edit Support')
    else:
        # Non-admin menu with translations
        markup.row(
            language_translations.get("my_configs", "📱 My Configs"), 
            language_translations.get("purchase_plan", "💰 Purchase Plan")
        )
        markup.row(
            language_translations.get("downloads", "⬇️ Downloads"), 
            language_translations.get("test_config", "🎁 Test Config")
        )
        markup.row(
            language_translations.get("support", "📞 Support"), 
            language_translations.get("language", "🌐 Language")
        )
    return markup

def create_main_markup(is_admin=False, user_id=None):
    """
    Create a main menu markup with language detection.
    This function handles imports internally to avoid circular imports.
    """
    if is_admin:
        return create_main_markup_with_language({}, is_admin=True)
    
    # Import here to avoid circular imports
    from utils.translations import BUTTON_TRANSLATIONS, DEFAULT_LANGUAGE
    
    # Get user language - importing here to avoid circular import
    try:
        from utils.language import get_user_language
        language_code = get_user_language(user_id) if user_id else DEFAULT_LANGUAGE
    except (ImportError, Exception):
        language_code = DEFAULT_LANGUAGE
    
    # Get language translations
    language_translations = BUTTON_TRANSLATIONS.get(language_code, BUTTON_TRANSLATIONS[DEFAULT_LANGUAGE])
    
    return create_main_markup_with_language(language_translations, is_admin=False)
