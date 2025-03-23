from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ParseMode
from telegram.ext import CallbackContext, CallbackQueryHandler, CommandHandler
from src.db.storage import Database
from src.utils.config import load_config
from src.api.cryptomus_client import CryptomusClient
from src.bot.keyboards import get_main_menu_keyboard

# Initialize the database
db = Database()

# Load configuration
config = load_config()

# Initialize Cryptomus client
cryptomus_client = CryptomusClient(
    merchant_id=config['cryptomus_merchant_id'],
    api_key=config['cryptomus_api_key'],
    test_mode=config['cryptomus_test_mode']
)

# Client command handlers
def view_plans(update: Update, context: CallbackContext) -> None:
    """Show available plans to the user."""
    plans = db.get_all_plans()
    
    if not plans:
        update.message.reply_text("No plans available at the moment.")
        return
    
    # Create inline keyboard with plans
    keyboard = []
    for plan in plans:
        keyboard.append([InlineKeyboardButton(
            f"{plan['name']} - {plan['price']} {plan['currency']}",
            callback_data=f"plan_details_{plan['id']}"
        )])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.message.reply_text(
        "Available Plans:",
        reply_markup=reply_markup
    )

def show_plan_details(update: Update, context: CallbackContext) -> None:
    """Show details of a selected plan."""
    query = update.callback_query
    query.answer()
    
    plan_id = int(query.data.split('_')[-1])
    plan = db.get_plan(plan_id)
    
    if not plan:
        query.edit_message_text("Plan not found.")
        return
    
    # Create inline keyboard for purchase
    keyboard = [
        [InlineKeyboardButton("Purchase", callback_data=f"purchase_plan_{plan['id']}")],
        [InlineKeyboardButton("Back", callback_data="view_plans")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    query.edit_message_text(
        f"*{plan['name']}*\n\n"
        f"Description: {plan['description']}\n"
        f"Traffic: {plan['traffic_limit']} GB\n"
        f"Duration: {plan['duration_days']} days\n"
        f"Price: {plan['price']} {plan['currency']}",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

def handle_purchase(update: Update, context: CallbackContext) -> None:
    """Handle plan purchase."""
    query = update.callback_query
    query.answer()
    
    plan_id = int(query.data.split('_')[-1])
    plan = db.get_plan(plan_id)
    
    if not plan:
        query.edit_message_text("Plan not found.")
        return
    
    user = update.effective_user
    
    # Create payment
    payment = db.create_payment(
        user_id=user.id,
        plan_id=plan['id'],
        amount=plan['price'],
        currency=plan['currency']
    )
    
    # Create payment in Cryptomus
    payment_details = cryptomus_client.create_payment(
        amount=plan['price'],
        currency=plan['currency'],
        order_id=str(payment),
        description=f"Purchase of {plan['name']} plan",
        callback_url=config['payment_callback_url']
    )
    
    # Update payment with external ID and URL
    db.update_payment(payment, {
        'external_id': payment_details['uuid'],
        'payment_url': payment_details['url']
    })
    
    # Show payment URL to the user
    query.edit_message_text(
        f"Please complete your payment using the following link:\n\n"
        f"[Pay Now]({payment_details['url']})",
        parse_mode=ParseMode.MARKDOWN
    )

def check_payment_status(update: Update, context: CallbackContext) -> None:
    """Check the status of a payment."""
    query = update.callback_query
    query.answer()
    
    payment_id = int(query.data.split('_')[-1])
    payment = db.get_payment(payment_id)
    
    if not payment:
        query.edit_message_text("Payment not found.")
        return
    
    # Get payment status from Cryptomus
    payment_status = cryptomus_client.get_payment(payment_id=payment['payment_id'])
    
    # Update payment status in the database
    db.update_payment(payment_id, {
        'status': payment_status['status']
    })
    
    # Show payment status to the user
    query.edit_message_text(
        f"Payment Status: {payment_status['status']}"
    )

def show_my_subscriptions(update: Update, context: CallbackContext) -> None:
    """Show the user's subscriptions."""
    user = update.effective_user
    payments = db.get_user_payments(user.id)
    
    if not payments:
        update.message.reply_text("You have no subscriptions.")
        return
    
    # Create subscription list text
    message = "*Your Subscriptions:*\n\n"
    for payment in payments:
        message += f"*{payment['plan_name']}* - {payment['amount']} {payment['currency']}\n"
        message += f"Traffic: {payment['traffic_limit']} GB, Duration: {payment['duration_days']} days\n"
        message += f"Status: {payment['status']}\n\n"
    
    update.message.reply_text(
        message,
        parse_mode=ParseMode.MARKDOWN
    )

def show_payment_history(update: Update, context: CallbackContext) -> None:
    """Show the user's payment history."""
    user = update.effective_user
    payments = db.get_user_payments(user.id)
    
    if not payments:
        update.message.reply_text("You have no payment history.")
        return
    
    # Create payment history list text
    message = "*Your Payment History:*\n\n"
    for payment in payments:
        message += f"*{payment['plan_name']}* - {payment['amount']} {payment['currency']}\n"
        message += f"Status: {payment['status']}\n\n"
    
    update.message.reply_text(
        message,
        parse_mode=ParseMode.MARKDOWN
    )

def show_help_support(update: Update, context: CallbackContext) -> None:
    """Show help and support information."""
    update.message.reply_text(
        "For help and support, please contact our support team at support@example.com."
    )

def handle_client_back(update: Update, context: CallbackContext) -> None:
    """Handle back button for client."""
    query = update.callback_query
    query.answer()
    
    query.edit_message_text(
        "Use the keyboard below to navigate:",
        reply_markup=get_main_menu_keyboard()
    )

# Set up all client handlers
def setup_client_handlers(dispatcher):
    """Set up all client command and conversation handlers."""
    # Client commands
    dispatcher.add_handler(CommandHandler("plans", view_plans))
    dispatcher.add_handler(CommandHandler("subscriptions", show_my_subscriptions))
    
    # Button handlers
    dispatcher.add_handler(CallbackQueryHandler(view_plans, pattern=r'^view_plans$'))
    dispatcher.add_handler(CallbackQueryHandler(show_plan_details, pattern=r'^plan_details_\d+$'))
    dispatcher.add_handler(CallbackQueryHandler(handle_purchase, pattern=r'^purchase_plan_\d+$'))
    dispatcher.add_handler(CallbackQueryHandler(check_payment_status, pattern=r'^check_payment_\d+$'))
    dispatcher.add_handler(CallbackQueryHandler(show_my_subscriptions, pattern=r'^my_subscriptions$'))
    dispatcher.add_handler(CallbackQueryHandler(show_payment_history, pattern=r'^payment_history$'))
    dispatcher.add_handler(CallbackQueryHandler(show_help_support, pattern=r'^help_support$'))
    dispatcher.add_handler(CallbackQueryHandler(handle_client_back, pattern=r'^client_back$'))