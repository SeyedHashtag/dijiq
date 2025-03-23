from telegram import Update, ParseMode
from telegram.ext import (
    CallbackContext, 
    ConversationHandler, 
    CommandHandler, 
    MessageHandler, 
    Filters
)
import datetime
from src.models.user import VpnUser
from src.api.vpn_client import VpnApiClient
from src.utils.config import load_config, is_admin
from src.utils.password import generate_random_password
from src.utils.vpn_config import generate_hy2_config
from src.bot.keyboards import (
    get_main_menu_keyboard, 
    get_cancel_keyboard,
    get_remove_keyboard
)

# Conversation states
TRAFFIC_LIMIT, EXPIRATION_DAYS, CONFIRMATION = range(3)

# Cancellation text
CANCEL_TEXT = "❌ Cancel"

# Load configuration
config = load_config()
vpn_client = VpnApiClient(
    base_url=config['vpn_api_url'],
    api_key=config.get('api_key')
)

def generate_username(user_id):
    """Generate a username based on Telegram ID and timestamp."""
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    return f"{user_id}d{timestamp}"

# Command handlers
def start(update: Update, context: CallbackContext) -> None:
    """Start command handler for admins."""
    user = update.effective_user
    
    update.message.reply_text(
        f"Hello {user.first_name}! 🛡️ *ADMIN MODE* 🛡️\n\n"
        "Use the keyboard below to manage VPN users:",
        reply_markup=get_main_menu_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )

# ...existing code...

# Get all admin handlers
def get_user_management_handlers():
    """Return handlers related to user management (admin functionality)."""
    return [
        CommandHandler("help", help_command),
        CommandHandler("admin", start),  # Explicit admin command
        add_user_conversation_handler
    ]
