from telegram import Update, ParseMode, InlineKeyboardMarkup, InlineKeyboardButton
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
from src.db.storage import Database

# Initialize the database
db = Database()

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
    """Start command handler."""
    user = update.effective_user
    
    # Store or update user in database (whether admin or client)
    if user.id:
        db.add_client(
            telegram_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name
        )
    
    # Different experience for admins vs regular clients
    if is_admin(user.id):
        # Admin interface
        update.message.reply_text(
            f"Hello {user.first_name}! I'm your VPN User Management Bot.\n\n"
            "As an admin, you can manage users and plans:",
            reply_markup=get_main_menu_keyboard()
        )
    else:
        # Client interface
        keyboard = [
            [InlineKeyboardButton("📦 View Plans", callback_data="view_plans")],
            [InlineKeyboardButton("📊 My Subscriptions", callback_data="my_subscriptions")],
            [InlineKeyboardButton("📋 Payment History", callback_data="payment_history")],
            [InlineKeyboardButton("ℹ️ Help & Support", callback_data="help_support")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        update.message.reply_text(
            f"Hello {user.first_name}! Welcome to the VPN service.\n\n"
            "What would you like to do today?",
            reply_markup=reply_markup
        )

def help_command(update: Update, context: CallbackContext) -> None:
    """Help command handler."""
    user = update.effective_user
    
    if is_admin(user.id):
        # Admin help
        update.message.reply_text(
            "🔹 *VPN User Management Bot Help* 🔹\n\n"
            "*Admin Commands*:\n"
            "/start - Start the bot\n"
            "/adduser - Add a new VPN user\n"
            "/plans - Manage subscription plans\n"
            "/addplan - Add a new subscription plan\n"
            "/editplan - Edit an existing plan\n"
            "/deleteplan - Delete/deactivate a plan\n"
            "/help - Show this help message",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        # Client help
        update.message.reply_text(
            "🔹 *VPN Service Help* 🔹\n\n"
            "*Commands*:\n"
            "/start - Main menu\n"
            "/plans - View available plans\n"
            "/subscriptions - View your active subscriptions\n"
            "/help - Show this help message\n\n"
            "For further assistance, please contact support.",
            parse_mode=ParseMode.MARKDOWN
        )

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
    """Handle traffic limit input."""
    text = update.message.text.strip()
    
    # Check for cancel command first
    if text == CANCEL_TEXT:
        return cancel_handler(update, context)
    
    try:
        traffic_limit = int(text)
        if traffic_limit <= 0:
            raise ValueError("Traffic limit must be positive")
        
        context.user_data['traffic_limit'] = traffic_limit
        update.message.reply_text(
            f"Traffic limit: {traffic_limit} GB\n\n"
            "Now, enter the number of days until expiration (e.g., 30):",
            reply_markup=get_cancel_keyboard()  # Keep cancel button available
        )
        return EXPIRATION_DAYS
    
    except ValueError:
        update.message.reply_text(
            "Please enter a valid positive number for traffic limit:",
            reply_markup=get_cancel_keyboard()  # Keep cancel button available
        )
        return TRAFFIC_LIMIT

def expiration_days_handler(update: Update, context: CallbackContext) -> int:
    """Handle expiration days input."""
    text = update.message.text.strip()
    
    # Check for cancel command first
    if text == CANCEL_TEXT:
        return cancel_handler(update, context)
    
    try:
        expiration_days = int(text)
        if expiration_days <= 0:
            raise ValueError("Expiration days must be positive")
        
        context.user_data['expiration_days'] = expiration_days
        
        # Show summary for confirmation (including the generated password)
        update.message.reply_text(
            "Please confirm the following information:\n\n"
            f"Username: {context.user_data['username']}\n"
            f"Password: {context.user_data['password']}\n"
            f"Traffic Limit: {context.user_data['traffic_limit']} GB\n"
            f"Expiration: {context.user_data['expiration_days']} days\n\n"
            "Type 'confirm' to add this user or 'cancel' to abort.",
            reply_markup=get_cancel_keyboard()  # Keep cancel button available
        )
        return CONFIRMATION
    
    except ValueError:
        update.message.reply_text(
            "Please enter a valid positive number for expiration days:",
            reply_markup=get_cancel_keyboard()  # Keep cancel button available
        )
        return EXPIRATION_DAYS

def confirmation_handler(update: Update, context: CallbackContext) -> int:
    """Handle confirmation input."""
    decision = update.message.text.strip().lower()
    
    # Check for cancel command first (case insensitive)
    if decision == CANCEL_TEXT.lower() or decision == 'cancel':
        return cancel_handler(update, context)
    
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
            
            # Generate VPN configuration string
            vpn_config = generate_hy2_config(user.username, user.password, config)
            
            # Send success message with user details
            update.message.reply_text(
                f"✅ User successfully added!\n\n"
                f"Username: {user.username}\n"
                f"Password: {user.password}\n"
                f"Traffic Limit: {user.traffic_limit} GB\n"
                f"Expiration: {user.expiration_days} days",
                reply_markup=get_main_menu_keyboard()
            )
            
            # Send the configuration string in a separate message
            update.message.reply_text(
                f"📱 *VPN Configuration*\n\n"
                f"`{vpn_config}`\n\n"
                f"Copy this configuration to connect to the VPN.",
                parse_mode=ParseMode.MARKDOWN
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
        TRAFFIC_LIMIT: [MessageHandler(Filters.text & ~Filters.command, traffic_limit_handler)],
        EXPIRATION_DAYS: [MessageHandler(Filters.text & ~Filters.command, expiration_days_handler)],
        CONFIRMATION: [MessageHandler(Filters.text & ~Filters.command, confirmation_handler)]
    },
    fallbacks=[
        CommandHandler('cancel', cancel_handler),
        MessageHandler(Filters.regex(f'^{CANCEL_TEXT}$'), cancel_handler)
    ]
)

# Set up all handlers
def setup_handlers(dispatcher):
    """Set up all command and conversation handlers."""
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("help", help_command))
    dispatcher.add_handler(add_user_conversation_handler)
    
    # Note: We no longer have a fallback handler that sends all text to start
    # This is intentional to avoid conflicts with client handlers
    # Only add admin-specific fallbacks here
