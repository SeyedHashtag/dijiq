import uuid
import datetime  # Added missing import
from telegram import Update, ParseMode
from telegram.ext import (
    CallbackContext, 
    ConversationHandler, 
    CommandHandler, 
    MessageHandler, 
    Filters
)
from src.models.user import VpnUser
from src.models.purchase import Purchase
from src.api.vpn_client import VpnApiClient
from src.payment.cryptomus import CryptomusClient
from src.utils.config import load_config
from src.utils.password import generate_random_password
from src.utils.vpn_config import generate_hy2_config
from src.api.webhook_handler import register_payment_callback
from src.bot.keyboards import (
    get_main_menu_keyboard,
    get_cancel_keyboard,
    get_confirm_keyboard,
    get_payment_button
)
from src.utils.languages import LanguageManager
from src.utils.test_config import has_used_test_config, mark_test_config_used
from src.utils.admin_plans import load_plans

# Initialize language manager
lang_manager = LanguageManager()

# Conversation states
CONFIRMATION, PAYMENT_PENDING = range(2)

# Cancellation text
CANCEL_TEXT = "❌ Cancel"
CONFIRM_TEXT = "✅ Confirm"

# Load configuration
config = load_config()
vpn_package = config.get('vpn_package', {})
vpn_client = VpnApiClient(
    base_url=config['vpn_api_url'],
    api_key=config.get('api_key')
)
cryptomus_client = CryptomusClient(
    merchant_id=config.get('cryptomus_merchant_id', ''),
    api_key=config.get('cryptomus_api_key', '')
)

# Store ongoing purchases
purchases = {}  # user_id -> Purchase object

def start_purchase(update: Update, context: CallbackContext) -> int:
    """Start the VPN purchase process."""
    user = update.effective_user
    
    # Display package information
    update.message.reply_text(
        f"📦 *VPN Package Details*\n\n"
        f"🔹 Traffic: {vpn_package.get('traffic_limit', 100)} GB\n"
        f"🔹 Duration: {vpn_package.get('expiration_days', 90)} days\n"
        f"🔹 Price: ${vpn_package.get('price', 2.5):.2f}\n\n"
        f"Would you like to purchase this package?",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=get_confirm_keyboard()
    )
    return CONFIRMATION

def process_confirmation(update: Update, context: CallbackContext) -> int:
    """Process the user's confirmation for purchase."""
    decision = update.message.text.strip()
    
    if decision == CANCEL_TEXT:
        update.message.reply_text(
            "Purchase cancelled.",
            reply_markup=get_main_menu_keyboard()
        )
        return ConversationHandler.END
    
    if decision != CONFIRM_TEXT:
        update.message.reply_text(
            "Please confirm or cancel the purchase.",
            reply_markup=get_confirm_keyboard()
        )
        return CONFIRMATION
    
    # User confirmed, create payment
    user = update.effective_user
    order_id = str(uuid.uuid4())
    
    try:
        # Create payment via Cryptomus
        payment_result = cryptomus_client.create_payment(
            amount=vpn_package.get('price', 2.5),
            currency=vpn_package.get('currency', 'USD'),
            order_id=order_id,
            user_id=user.id
        )
        
        payment_id = payment_result.get('uuid')
        payment_url = payment_result.get('url')
        
        if not payment_id or not payment_url:
            update.message.reply_text(
                "❌ Failed to create payment. Please try again later.",
                reply_markup=get_main_menu_keyboard()
            )
            return ConversationHandler.END
        
        # Create purchase record
        purchase = Purchase(
            user_id=user.id,
            amount=vpn_package.get('price', 2.5),
            payment_id=payment_id,
            invoice_url=payment_url
        )
        
        # Store purchase for this user
        purchases[user.id] = purchase
        
        # Register callback for when payment is complete
        register_payment_callback(payment_id, lambda data: payment_completed(user.id, data))
        
        # Send message with payment button
        update.message.reply_text(
            f"Please complete the payment using the button below.\n\n"
            f"Your payment will be automatically processed once complete.",
            reply_markup=get_payment_button(payment_url)
        )
        
        # Send follow-up message with cancellation option
        update.message.reply_text(
            "Waiting for your payment. You can cancel anytime.",
            reply_markup=get_cancel_keyboard()
        )
        
        # Set a job to check payment status periodically
        context.job_queue.run_repeating(
            check_payment_status,
            interval=60,  # Check every minute
            first=60,  # Start checking after 1 minute
            context=user.id
        )
        
        return PAYMENT_PENDING
        
    except Exception as e:
        update.message.reply_text(
            f"❌ An error occurred: {str(e)}\n\nPlease try again later.",
            reply_markup=get_main_menu_keyboard()
        )
        return ConversationHandler.END

def check_payment_status(context: CallbackContext):
    """Check payment status job."""
    user_id = context.job.context
    
    if user_id not in purchases:
        # Purchase not found, stop checking
        context.job.schedule_removal()
        return
    
    purchase = purchases[user_id]
    
    try:
        payment_info = cryptomus_client.check_payment(purchase.payment_id)
        status = payment_info.get('status')
        
        if status == 'paid':
            # Payment successful, process it
            payment_completed(user_id, payment_info)
            context.job.schedule_removal()
        elif status in ['expired', 'failed']:
            # Payment failed or expired
            purchase.mark_as_failed()
            
            # Notify user
            context.bot.send_message(
                chat_id=user_id,
                text="❌ Your payment has failed or expired. Please try again.",
                reply_markup=get_main_menu_keyboard()
            )
            
            # Remove the purchase
            del purchases[user_id]
            context.job.schedule_removal()
    except Exception as e:
        # Log the error but continue checking
        print(f"Error checking payment: {e}")

def payment_completed(user_id, payment_data):
    """Process completed payment."""
    if user_id not in purchases:
        return
    
    purchase = purchases[user_id]
    purchase.mark_as_paid()
    
    # Generate VPN user
    try:
        # Generate username and password
        username = f"user{user_id}_{int(datetime.datetime.now().timestamp())}"
        password = generate_random_password(32)
        
        user = VpnUser(
            username=username,
            password=password,
            traffic_limit=vpn_package.get('traffic_limit', 100),
            expiration_days=vpn_package.get('expiration_days', 90)
        )
        
        # Add user to VPN service
        vpn_client.add_user(user)
        
        # Generate configuration
        vpn_config = generate_hy2_config(username, password, config)
        
        # Send configuration to user
        from telegram.bot import Bot
        bot = Bot(token=config['telegram_token'])
        bot.send_message(
            chat_id=user_id,
            text=f"🎉 *Payment Completed!*\n\nYour VPN account has been created.\n\n"
                 f"Username: `{username}`\n"
                 f"Password: `{password}`\n"
                 f"Traffic Limit: {user.traffic_limit} GB\n"
                 f"Expiration: {user.expiration_days} days",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_main_menu_keyboard()
        )
        
        # Send the configuration string in a separate message
        bot.send_message(
            chat_id=user_id,
            text=f"📱 *VPN Configuration*\n\n"
                 f"`{vpn_config}`\n\n"
                 f"Copy this configuration to connect to the VPN.",
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Clean up
        del purchases[user_id]
        
    except Exception as e:
        # If there's an error, notify the user and admins
        print(f"Error creating VPN user: {e}")
        
        from telegram.bot import Bot
        bot = Bot(token=config['telegram_token'])
        bot.send_message(
            chat_id=user_id,
            text="❌ There was an error creating your VPN account. "
                 "An administrator has been notified and will contact you soon.",
            reply_markup=get_main_menu_keyboard()
        )
        
        # Notify admins
        for admin_id in config['admin_users']:
            bot.send_message(
                chat_id=admin_id,
                text=f"⚠️ Error creating VPN user for payment {purchase.payment_id}:\n\n{str(e)}"
            )

def cancel_payment(update: Update, context: CallbackContext) -> int:
    """Cancel an ongoing payment."""
    user_id = update.effective_user.id
    
    # Remove any scheduled jobs
    for job in context.job_queue.get_jobs_by_name(str(user_id)):
        job.schedule_removal()
    
    # Clean up the purchase
    if user_id in purchases:
        del purchases[user_id]
    
    update.message.reply_text(
        "Payment cancelled. You can try again later.",
        reply_markup=get_main_menu_keyboard()
    )
    return ConversationHandler.END

def handle_test_config(update: Update, context: CallbackContext) -> None:
    """Handle test config request"""
    if has_used_test_config(update.effective_user.id):
        update.message.reply_text(
            "❌ You have already used your test config. Please purchase a plan to get a new config.",
            reply_markup=get_main_menu_keyboard(is_admin=False)
        )
        return

    # Create test config
    timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    username = f"{update.effective_user.id}d{timestamp}"
    
    # 1GB traffic limit and 30 days expiration
    user = VpnUser(
        username=username,
        password=generate_random_password(32),
        traffic_limit=1,
        expiration_days=30
    )
    
    try:
        # Call API to create user
        vpn_client.add_user(user)
        
        # Generate VPN configuration
        vpn_config = generate_hy2_config(user.username, user.password, config)
        
        # Create caption with user details
        caption = (
            f"📱 Config: {username}\n"
            f"📊 Traffic: 0.00/1.00 GB\n"
            f"📅 Days: 0/30\n\n"
            f"📝 Config Text:\n"
            f"`{vpn_config}`"
        )
        
        # Mark test config as used
        mark_test_config_used(update.effective_user.id)
        
        # Send config to user
        update.message.reply_text(
            caption,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_main_menu_keyboard(is_admin=False)
        )
    except Exception as e:
        update.message.reply_text(
            f"❌ Failed to create test config: {str(e)}",
            reply_markup=get_main_menu_keyboard(is_admin=False)
        )

def show_my_configs(update: Update, context: CallbackContext) -> None:
    """Show user's active configs"""
    # Get language preference
    lang_code = lang_manager.get_user_language(update.effective_user.id)
    
    # Here we would normally query the API to get configs for this user_id
    # For now, show a placeholder message
    update.message.reply_text(
        "Loading your configurations...",
        reply_markup=get_main_menu_keyboard(is_admin=False)
    )
    
    # API call would go here to get user's configs
    # For now, we'll simulate not finding any configs
    update.message.reply_text(
        "You don't have any active configs. Use the Purchase Plan option to get started!",
        reply_markup=get_main_menu_keyboard(is_admin=False)
    )

def show_downloads(update: Update, context: CallbackContext) -> None:
    """Show download options"""
    # Get language preference
    lang_code = lang_manager.get_user_language(update.effective_user.id)
    
    # This function would typically show a message with download links
    # We'll use a simple text message for now
    update.message.reply_text(
        "📱 *VPN Client Downloads*\n\n"
        "📱 Android: [Play Store](https://play.google.com/store/apps/details?id=app.hiddify.com)\n"
        "📱 Android (APK): [GitHub](https://github.com/hiddify/hiddify-app/releases/latest)\n"
        "🍎 iOS: [App Store](https://apps.apple.com/app/hiddify-proxy-vpn/id6596777532)\n"
        "🪟 Windows: [Download](https://github.com/hiddify/hiddify-app/releases/latest)\n"
        "🐧 Linux: [Download](https://github.com/hiddify/hiddify-app/releases/latest)\n"
        "🍎 macOS: [Download](https://github.com/hiddify/hiddify-app/releases/latest)",
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True,
        reply_markup=get_main_menu_keyboard(is_admin=False)
    )

def show_support(update: Update, context: CallbackContext) -> None:
    """Show support information"""
    # This would typically display support contact information
    update.message.reply_text(
        "📞 *Support Information*\n\n"
        "Need help? Contact our support:\n\n"
        "📱 Telegram: @support_username\n"
        "📧 Email: support@example.com\n"
        "⏰ Working hours: 24/7",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=get_main_menu_keyboard(is_admin=False)
    )

# Create the purchase conversation handler
purchase_conversation_handler = ConversationHandler(
    entry_points=[
        CommandHandler('purchase', start_purchase),
        MessageHandler(Filters.regex('^💰 Purchase VPN$'), start_purchase)
    ],
    states={
        CONFIRMATION: [MessageHandler(Filters.text & ~Filters.command, process_confirmation)],
        PAYMENT_PENDING: [MessageHandler(Filters.regex(f'^{CANCEL_TEXT}$'), cancel_payment)]
    },
    fallbacks=[
        CommandHandler('cancel', cancel_payment),
        MessageHandler(Filters.regex(f'^{CANCEL_TEXT}$'), cancel_payment)
    ]
)

def setup_customer_handlers(dispatcher):
    """Register customer handlers"""
    # Regular commands
    dispatcher.add_handler(MessageHandler(Filters.regex('^📱 My Configs$'), show_my_configs))
    dispatcher.add_handler(MessageHandler(Filters.regex('^⬇️ Downloads$'), show_downloads))
    dispatcher.add_handler(MessageHandler(Filters.regex('^📞 Support$'), show_support))
    dispatcher.add_handler(MessageHandler(Filters.regex('^🎁 Test Config$'), handle_test_config))
    
    # Purchase conversation handler
    dispatcher.add_handler(purchase_conversation_handler)
