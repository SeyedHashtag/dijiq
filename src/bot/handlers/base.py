"""
Base handlers for the Telegram bot.
"""

from telegram import Update, ParseMode, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackContext, CommandHandler

def help_command(update: Update, context: CallbackContext) -> None:
    """General help command handler."""
    user = update.effective_user
    
    keyboard = [
        [InlineKeyboardButton("🛒 Purchase VPN", callback_data="purchase")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.message.reply_text(
        f"Hello {user.first_name}! 👋\n\n"
        "Welcome to our VPN service bot. You can use the following commands:\n\n"
        "/start - Start the bot and show main menu\n"
        "/buy - Purchase a VPN plan\n"
        "/help - Show this help message\n\n"
        "Click the button below to purchase:",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

def get_base_handlers():
    """Return handlers that apply to all users."""
    return [
        CommandHandler("help", help_command)
    ]
