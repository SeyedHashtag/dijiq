from telegram import Update, ParseMode
from telegram.ext import (
    CallbackContext, 
    ConversationHandler, 
    CommandHandler, 
    MessageHandler, 
    Filters
)
from src.models.user import VpnUser
from src.api.vpn_client import VpnApiClient
from src.utils.config import load_config, is_admin
from src.bot.keyboards import (
    get_main_menu_keyboard, 
    get_cancel_keyboard,
    get_remove_keyboard
)

# Conversation states
USERNAME, PASSWORD, TRAFFIC_LIMIT, EXPIRATION_DAYS, CONFIRMATION = range(5)

# Load configuration
config = load_config()
vpn_client = VpnApiClient(config['vpn_api_url'])

# Command handlers
def start(update: Update, context: CallbackContext) -> None:
    """Start command handler."""
    user = update.effective_user
    
    if not is_admin(user.id):
        update.message.reply_text(
            "Sorry, you are not authorized to use this bot."
        )
        return
    
    update.message.reply_text(
        f"Hello {user.first_name}! I'm your VPN User Management Bot.\n\n"
        "Use the keyboard below to navigate:",
        reply_markup=get_main_menu_keyboard()
    )

def help_command(update: Update, context: CallbackContext) -> None:
    """Help command handler."""
    update.message.reply_text(
        "🔹 *VPN User Management Bot Help* 🔹\n\n"
        "*Commands*:\n"
        "/start - Start the bot\n"
        "/adduser - Add a new VPN user\n"
        "/help - Show this help message\n\n"
        "*Adding a user*:\n"
        "1. Click '➕ Add New User' or use /adduser\n"
        "2. Follow the prompts to enter user details\n"
        "3. Confirm the information",
        parse_mode=ParseMode.MARKDOWN
    )

# Add user conversation
def add_user_start(update: Update, context: CallbackContext) -> int:
    """Start the add user conversation."""
    user = update.effective_user
    
    if not is_admin(user.id):
        update.message.reply_text(
            "Sorry, you are not authorized to perform this action."
        )
        return ConversationHandler.END
    
    update.message.reply_text(
        "Let's add a new VPN user.\n\n"
        "What should be the username? (letters and numbers only)",
        reply_markup=get_cancel_keyboard()
    )
    return USERNAME

def username_handler(update: Update, context: CallbackContext) -> int:
    """Handle username input."""
    username = update.message.text.strip()
    
    # Validate username
    if not username.isalnum():
        update.message.reply_text(
            "Username must contain only letters and numbers. Please try again:"
        )
        return USERNAME
    
    context.user_data['username'] = username
    update.message.reply_text(
        f"Username: {username}\n\n"
        "Now, please enter a password:",
    )
    return PASSWORD

def password_handler(update: Update, context: CallbackContext) -> int:
    """Handle password input."""
    password = update.message.text.strip()
    
    if len(password) < 6:
        update.message.reply_text(
            "Password must be at least 6 characters long. Please try again:"
        )
        return PASSWORD
    
    context.user_data['password'] = password
    update.message.reply_text(
        "Now, enter the traffic limit in GB (e.g., 50):"
    )
    return TRAFFIC_LIMIT

def traffic_limit_handler(update: Update, context: CallbackContext) -> int:
    """Handle traffic limit input."""
    try:
        traffic_limit = int(update.message.text.strip())
        if traffic_limit <= 0:
            raise ValueError("Traffic limit must be positive")
        
        context.user_data['traffic_limit'] = traffic_limit
        update.message.reply_text(
            f"Traffic limit: {traffic_limit} GB\n\n"
            "Now, enter the number of days until expiration (e.g., 30):"
        )
        return EXPIRATION_DAYS
    
    except ValueError:
        update.message.reply_text(
            "Please enter a valid positive number for traffic limit:"
        )
        return TRAFFIC_LIMIT

def expiration_days_handler(update: Update, context: CallbackContext) -> int:
    """Handle expiration days input."""
    try:
        expiration_days = int(update.message.text.strip())
        if expiration_days <= 0:
            raise ValueError("Expiration days must be positive")
        
        context.user_data['expiration_days'] = expiration_days
        
        # Show summary for confirmation
        update.message.reply_text(
            "Please confirm the following information:\n\n"
            f"Username: {context.user_data['username']}\n"
            f"Password: {context.user_data['password']}\n"
            f"Traffic Limit: {context.user_data['traffic_limit']} GB\n"
            f"Expiration: {context.user_data['expiration_days']} days\n\n"
            "Type 'confirm' to add this user or 'cancel' to abort."
        )
        return CONFIRMATION
    
    except ValueError:
        update.message.reply_text(
            "Please enter a valid positive number for expiration days:"
        )
        return EXPIRATION_DAYS

def confirmation_handler(update: Update, context: CallbackContext) -> int:
    """Handle confirmation input."""
    decision = update.message.text.strip().lower()
    
    if decision == 'confirm':
        try:
            user = VpnUser(
                username=context.user_data['username'],
                password=context.user_data['password'],
                traffic_limit=context.user_data['traffic_limit'],
                expiration_days=context.user_data['expiration_days']
            )
            
            # Call the API to add the user
            response = vpn_client.add_user(user)
            
            update.message.reply_text(
                f"✅ User successfully added!\n\n"
                f"Username: {user.username}\n"
                f"Password: {user.password}\n"
                f"Traffic Limit: {user.traffic_limit} GB\n"
                f"Expiration: {user.expiration_days} days",
                reply_markup=get_main_menu_keyboard()
            )
            
        except Exception as e:
            update.message.reply_text(
                f"❌ Failed to add user: {str(e)}",
                reply_markup=get_main_menu_keyboard()
            )
    else:
        update.message.reply_text(
            "User creation cancelled.",
            reply_markup=get_main_menu_keyboard()
        )
    
    # Clear user data
    context.user_data.clear()
    return ConversationHandler.END

def cancel_handler(update: Update, context: CallbackContext) -> int:
    """Handle conversation cancellation."""
    update.message.reply_text(
        "Operation cancelled.",
        reply_markup=get_main_menu_keyboard()
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
        USERNAME: [MessageHandler(Filters.text & ~Filters.command, username_handler)],
        PASSWORD: [MessageHandler(Filters.text & ~Filters.command, password_handler)],
        TRAFFIC_LIMIT: [MessageHandler(Filters.text & ~Filters.command, traffic_limit_handler)],
        EXPIRATION_DAYS: [MessageHandler(Filters.text & ~Filters.command, expiration_days_handler)],
        CONFIRMATION: [MessageHandler(Filters.text & ~Filters.command, confirmation_handler)]
    },
    fallbacks=[
        CommandHandler('cancel', cancel_handler),
        MessageHandler(Filters.regex('^❌ Cancel$'), cancel_handler)
    ]
)

# Set up all handlers
def setup_handlers(dispatcher):
    """Set up all command and conversation handlers."""
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("help", help_command))
    dispatcher.add_handler(add_user_conversation_handler)
    
    # Add a fallback handler
    dispatcher.add_handler(MessageHandler(Filters.text, start))
