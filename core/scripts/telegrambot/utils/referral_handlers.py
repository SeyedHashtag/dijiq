from telebot import types
from utils.command import bot
from utils.referral import get_or_create_referral_code, get_referral_stats
from utils.translations import BUTTON_TRANSLATIONS, get_message_text, get_button_text
from utils.language import get_user_language

@bot.message_handler(func=lambda message: any(
    message.text == get_button_text(get_user_language(message.from_user.id), "referral") for lang in BUTTON_TRANSLATIONS
))
def referral_menu(message):
    user_id = message.from_user.id
    language = get_user_language(user_id)
    
    code = get_or_create_referral_code(user_id)
    stats = get_referral_stats(user_id)
    
    try:
        bot_info = bot.get_me()
        bot_username = bot_info.username
    except Exception:
        bot_username = "YourBotName" # Fallback if API fails
    
    referral_link = f"https://t.me/{bot_username}?start={code}"
    
    msg = get_message_text(language, "referral_stats").format(
        count=stats["count"],
        total_earnings=stats["total_earnings"],
        available_balance=stats["available_balance"],
        referral_link=referral_link
    )
    
    bot.reply_to(message, msg, parse_mode="Markdown")
