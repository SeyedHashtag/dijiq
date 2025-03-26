from telegram import Update, ParseMode
from telegram.ext import CallbackContext
from src.utils.config import load_config, is_admin
from src.bot.keyboards import get_main_menu_keyboard

def start(update: Update, context: CallbackContext) -> None:
    """Start command handler."""
    user = update.effective_user
    admin_user = is_admin(user.id)
    
    welcome_text = (
        f"Hello {user.first_name}! Welcome to the VPN Service Bot.\n\n"
    )
    
    if admin_user:
        welcome_text += "You are logged in as an admin. Use the keyboard below to navigate:"
    else:
        welcome_text += "Use the keyboard below to navigate:"
    
    update.message.reply_text(
        welcome_text,
        reply_markup=get_main_menu_keyboard(admin_user)
    )

def help_command(update: Update, context: CallbackContext) -> None:
    """Help command handler."""
    user = update.effective_user
    admin_user = is_admin(user.id)
    
    help_text = (
        "🔹 *VPN Service Bot Help* 🔹\n\n"
        "*Commands*:\n"
        "/start - Start the bot and show main menu\n"
        "/help - Show this help message\n"
    )
    
    if admin_user:
        help_text += (
            "\n*Admin Commands*:\n"
            "/adduser - Add a new VPN user\n"
            "\n*Adding a user*:\n"
            "1. Click '➕ Add New User' or use /adduser\n"
            "2. Follow the prompts to enter user details\n"
            "3. Confirm the information\n"
        )
    else:
        help_text += (
            "\n*Purchase a VPN*:\n"
            "1. Click '💰 Purchase VPN'\n"
            "2. Follow the payment instructions\n"
            "3. Once payment is completed, you'll receive your VPN configuration\n"
        )
    
    update.message.reply_text(
        help_text,
        parse_mode=ParseMode.MARKDOWN
    )
