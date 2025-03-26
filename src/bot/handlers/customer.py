"""
Customer-side handlers for purchasing VPN service.
"""

import uuid
import logging
from datetime import datetime

from telegram import Update, ParseMode, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    CallbackContext, 
    ConversationHandler, 
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    Filters
)

from src.models.user import VpnUser
from src.models.purchase import Purchase, PurchaseManager
from src.api.vpn_client import VpnApiClient
from src.utils.config import load_config
from src.payment.cryptomus import CryptomusClient
from src.utils.password import generate_random_password
from src.utils.vpn_config import generate_hy2_config

# Configure logger
logger = logging.getLogger(__name__)

# States
PAYMENT_PENDING = 0

# Load configuration
config = load_config()
vpn_client = VpnApiClient(
    base_url=config['vpn_api_url'],
    api_key=config.get('api_key')
)

# Initialize payment client
cryptomus = CryptomusClient(
    merchant_id=config.get('cryptomus_merchant_id', ''),
    api_key=config.get('cryptomus_api_key', '')
)

# Initialize purchase manager
purchase_manager = PurchaseManager()

def generate_username(user_id):
    """Generate a username based on Telegram ID and timestamp."""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"{user_id}d{timestamp}"

def start_customer(update: Update, context: CallbackContext) -> None:
    """Start command handler for customers."""
    user = update.effective_user
    
    keyboard = [
        [InlineKeyboardButton("🛒 Purchase VPN", callback_data="purchase")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.message.reply_text(
        f"Welcome {user.first_name}! 🌐\n\n"
        "Our VPN service offers secure and private internet access.\n\n"
        "• 100GB Traffic\n"
        "• 90 Days Access\n"
        "• Only $2.50\n\n"
        "Click the button below to purchase:",
        reply_markup=reply_markup
    )

def show_purchase_options(update: Update, context: CallbackContext) -> None:
    """Show the purchase options to the user."""
    query = update.callback_query
    
    if query:
        query.answer()
    
    keyboard = [
        [InlineKeyboardButton("✅ Buy VPN Plan ($2.50)", callback_data="confirm_purchase")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel_purchase")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = "*Premium VPN Plan*\n\n" \
           "📊 *Traffic:* 100 GB\n" \
           "⏱ *Duration:* 90 days\n" \
           "💲 *Price:* $2.50\n\n" \
           "Click below to proceed with purchase:"
    
    if query:
        query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    else:
        update.message.reply_text(text=text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

def start_payment(update: Update, context: CallbackContext) -> int:
    """Start the payment process."""
    query = update.callback_query
    query.answer()
    
    user_id = update.effective_user.id
    
    # Generate unique order ID
    order_id = str(uuid.uuid4())
    
    # Create purchase record
    purchase = Purchase(
        purchase_id=order_id,
        telegram_id=user_id,
        plan_id="premium",
        amount=2.50,
        currency="USD",
        payment_id=None,
        status="pending",
        created_at=datetime.now().isoformat()
    )
    purchase_manager.add_purchase(purchase)
    
    # Store in context for the conversation
    context.user_data['purchase_id'] = order_id
    
    try:
        # Get bot username for success URL
        bot_username = context.bot.get_me().username
        success_url = f"https://t.me/{bot_username}?start=payment_{order_id}"
        
        # Create payment in Cryptomus
        payment_data = cryptomus.create_payment(
            amount=2.50,
            currency="USD",
            order_id=order_id,
            description="VPN Plan: 100GB for 90 days",
            success_url=success_url
        )
        
        if 'result' not in payment_data or 'url' not in payment_data['result']:
            query.edit_message_text("Sorry, there was an error creating your payment. Please try again later.")
            return ConversationHandler.END
        
        payment_url = payment_data['result']['url']
        
        # Send payment URL to user
        keyboard = [
            [InlineKeyboardButton("💳 Pay Now", url=payment_url)],
            [InlineKeyboardButton("✅ I've Paid", callback_data=f"check_{order_id}")],
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel_purchase")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        query.edit_message_text(
            "*VPN Purchase - Payment*\n\n"
            "Please click the button below to make your payment.\n"
            "After completing the payment, click 'I've Paid' to check status.\n\n"
            "*Order ID:* `" + order_id + "`",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
        return PAYMENT_PENDING
        
    except Exception as e:
        logger.error(f"Payment creation failed: {str(e)}")
        query.edit_message_text(
            "Sorry, there was an error processing your payment request. "
            "Please try again later."
        )
        return ConversationHandler.END

def check_payment_status(update: Update, context: CallbackContext) -> int:
    """Check if payment was completed."""
    query = update.callback_query
    query.answer()
    
    order_id = query.data.split('_')[1]
    
    try:
        # Check payment status
        payment_info = cryptomus.check_payment(order_id)
        
        if 'result' not in payment_info:
            query.edit_message_text("Sorry, couldn't retrieve payment information.")
            return ConversationHandler.END
        
        status = payment_info['result'].get('status')
        
        if status == 'paid':
            # Payment was successful, create VPN account
            return process_successful_payment(update, context, order_id)
        else:
            # Payment not completed yet
            keyboard = [
                [InlineKeyboardButton("💳 Check Again", callback_data=f"check_{order_id}")],
                [InlineKeyboardButton("❌ Cancel", callback_data="cancel_purchase")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            query.edit_message_text(
                "*Payment Pending*\n\n"
                "Your payment has not been confirmed yet. This may take a few minutes.\n\n"
                "Click 'Check Again' to refresh the status.",
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
            return PAYMENT_PENDING
            
    except Exception as e:
        logger.error(f"Payment check failed: {str(e)}")
        query.edit_message_text(
            "Sorry, there was an error checking your payment. Please try again later."
        )
        return ConversationHandler.END

def process_successful_payment(update: Update, context: CallbackContext, order_id: str) -> int:
    """Process a successful payment by creating a VPN account."""
    # Get purchase record
    purchase = purchase_manager.get_purchase_by_id(order_id)
    
    if not purchase:
        update.callback_query.edit_message_text(
            "Sorry, there was an error processing your purchase. "
            "Please contact support with your order ID."
        )
        return ConversationHandler.END
    
    # Generate VPN credentials
    username = generate_username(update.effective_user.id)
    password = generate_random_password(32)
    
    try:
        # Create VPN user
        vpn_user = VpnUser(
            username=username,
            password=password,
            traffic_limit=100,  # 100 GB
            expiration_days=90  # 90 days
        )
        
        # Call the API to add the user
        response = vpn_client.add_user(vpn_user)
        
        # Update purchase record with VPN credentials
        purchase.status = "completed"
        purchase.completed_at = datetime.now().isoformat()
        purchase.vpn_username = username
        purchase.vpn_password = password
        purchase_manager.update_purchase(purchase)
        
        # Generate VPN configuration
        vpn_config = generate_hy2_config(username, password, config)
        
        # Send success messages
        update.callback_query.edit_message_text(
            "✅ *Payment Successful!*\n\n"
            "Your VPN account has been created successfully. "
            "You'll find your configuration details below.",
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Send configuration in a separate message
        context.bot.send_message(
            chat_id=update.effective_user.id,
            text=f"📱 *Your VPN Configuration*\n\n"
                f"*Username:* `{username}`\n"
                f"*Password:* `{password}`\n"
                f"*Traffic Limit:* 100 GB\n"
                f"*Expires in:* 90 days\n\n"
                f"*Configuration String:*\n"
                f"`{vpn_config}`\n\n"
                f"To use this VPN, import the configuration into your Hysteria2 client.",
            parse_mode=ParseMode.MARKDOWN
        )
        
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Error creating VPN user: {str(e)}")
        update.callback_query.edit_message_text(
            "Sorry, there was an error creating your VPN account. "
            "Please contact support with your order ID."
        )
        return ConversationHandler.END

def cancel_purchase(update: Update, context: CallbackContext) -> int:
    """Cancel the purchase process."""
    query = update.callback_query
    query.answer()
    
    # Check if there's a pending purchase to cancel
    if 'purchase_id' in context.user_data:
        purchase_id = context.user_data['purchase_id']
        purchase = purchase_manager.get_purchase_by_id(purchase_id)
        if purchase and purchase.status == "pending":
            purchase.status = "cancelled"
            purchase_manager.update_purchase(purchase)
            logger.info(f"Purchase {purchase_id} cancelled by user")
    
    # Clear user data
    context.user_data.clear()
    
    # Return to main menu
    keyboard = [
        [InlineKeyboardButton("🛒 Purchase VPN", callback_data="purchase")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    query.edit_message_text(
        "Purchase cancelled. You can try again later if you change your mind.",
        reply_markup=reply_markup
    )
    
    return ConversationHandler.END

def get_customer_handlers():
    """Return handlers for customer functionality."""
    
    # Create purchase conversation handler
    purchase_conversation = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_payment, pattern='^confirm_purchase$')
        ],
        states={
            PAYMENT_PENDING: [
                CallbackQueryHandler(check_payment_status, pattern='^check_'),
                CallbackQueryHandler(cancel_purchase, pattern='^cancel_purchase$')
            ]
        },
        fallbacks=[
            CallbackQueryHandler(cancel_purchase, pattern='^cancel_purchase$')
        ],
        allow_reentry=True
    )
    
    return [
        CommandHandler("buy", show_purchase_options),
        CallbackQueryHandler(show_purchase_options, pattern='^purchase$'),
        CallbackQueryHandler(cancel_purchase, pattern='^cancel_purchase$'),
        purchase_conversation
    ]
