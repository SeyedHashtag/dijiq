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

# Add user conversation
def add_user_start(update: Update, context: CallbackContext) -> int:
    """Start the add user conversation and generate username automatically."""
    user = update.effective_user
    
    if not is_admin(user.id):
        update.message.reply_text(
            "Sorry, you are not authorized to perform this action."
        )
        return ConversationHandler.END
    
    # Generate username automatically using the user's Telegram ID and timestamp
    username = generate_username(user.id)
    context.user_data['username'] = username
    
    # Generate random password
    context.user_data['password'] = generate_random_password(32)
    
    update.message.reply_text(
        "Let's add a new VPN user.\n\n"
        f"Username: {username}\n\n"
        "Enter the traffic limit in GB (e.g., 50):",
        reply_markup=get_cancel_keyboard()
    )
    return TRAFFIC_LIMIT

def traffic_limit_handler(update: Update, context: CallbackContext) -> int:
    # ...existing code...

def expiration_days_handler(update: Update, context: CallbackContext) -> int:
    # ...existing code...

def confirmation_handler(update: Update, context: CallbackContext) -> int:
    # ...existing code...

def cancel_handler(update: Update, context: CallbackContext) -> int:
    """Handle conversation cancellation."""
    update.message.reply_text(
        "Operation cancelled.",
        reply_markup=get_main_menu_keyboard(is_admin(update.effective_user.id))
    )
    context.user_data.clear()
    return ConversationHandler.END

# Create the add user conversation handler
add_user_conversation_handler = ConversationHandler(
    entry_points=[
        CommandHandler('adduser', add_user_start),
        MessageHandler(Filters.regex('^➕ Add New User$'), add_user_start)
    ],
    states={
        TRAFFIC_LIMIT: [MessageHandler(Filters.text & ~Filters.command, traffic_limit_handler)],
        EXPIRATION_DAYS: [MessageHandler(Filters.text & ~Filters.command, expiration_days_handler)],
        CONFIRMATION: [MessageHandler(Filters.text & ~Filters.command, confirmation_handler)]
    },
    fallbacks=[
        CommandHandler('cancel', cancel_handler),
        MessageHandler(Filters.regex(f'^{CANCEL_TEXT}$'), cancel_handler)
    ]
)