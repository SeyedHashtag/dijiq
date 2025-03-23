"""
Client-side handlers for the Telegram bot.
"""

import uuid
import logging
from datetime import datetime
import threading
from typing import Dict, List, Optional

from telegram import Update, ParseMode, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    CallbackContext, 
    ConversationHandler, 
    CommandHandler, 
    MessageHandler,
    Filters,
    CallbackQueryHandler
)

from src.models.plan import Plan, PlanManager
from src.models.purchase import Purchase, PurchaseManager
from src.models.user import VpnUser
from src.api.vpn_client import VpnApiClient
from src.utils.config import load_config
from src.payment.cryptomus import CryptomusClient
from src.utils.password import generate_random_password
from src.utils.vpn_config import generate_hy2_config
from src.api.webhook_handler import register_payment_callback

# Conversation states
SELECT_PLAN, PAYMENT_PENDING = range(2)

# Initialize managers
plan_manager = PlanManager()
purchase_manager = PurchaseManager()

# Global variables for purchase tracking
pending_purchases: Dict[str, Dict] = {}
purchase_awaiting_callbacks: Dict[int, List[str]] = {}

# Configure logger
logger = logging.getLogger(__name__)

# Load config
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

def start_client(update: Update, context: CallbackContext) -> None:
    """Start command handler for clients."""
    user = update.effective_user
    
    keyboard = [
        [InlineKeyboardButton("🛒 Purchase Plan", callback_data="purchase")],
        [InlineKeyboardButton("🔑 My VPNs", callback_data="my_vpns")],
        [InlineKeyboardButton("📝 Purchase History", callback_data="history")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.message.reply_text(
        f"Welcome {user.first_name}! 🌐\n\n"
        "I'm your VPN service bot. Use the buttons below to purchase plans "
        "or manage your VPN accounts.",
        reply_markup=reply_markup
    )

def show_plans(update: Update, context: CallbackContext) -> int:
    """Show available plans to the user."""
    query = update.callback_query
    
    if query:
        query.answer()
    
    # Get all plans
    plans = plan_manager.get_all_plans()
    
    if not plans:
        text = "Sorry, no plans are currently available."
        if query:
            query.edit_message_text(text=text)
        else:
            update.message.reply_text(text=text)
        return ConversationHandler.END
    
    # Create keyboard with plans
    keyboard = []
    for plan in plans:
        keyboard.append([
            InlineKeyboardButton(
                f"{plan.name} - ${plan.price:.2f}",
                callback_data=f"plan_{plan.id}"
            )
        ])
    
    # Add cancel button
    keyboard.append([InlineKeyboardButton("Cancel", callback_data="cancel")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = "📱 *Available VPN Plans*\n\n"
    text += "Please select a plan to purchase:"
    
    if query:
        query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    else:
        update.message.reply_text(text=text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    
    return SELECT_PLAN

def select_plan(update: Update, context: CallbackContext) -> int:
    """Handle plan selection."""
    query = update.callback_query
    query.answer()
    
    if query.data == "cancel":
        query.edit_message_text("Operation cancelled.")
        return ConversationHandler.END
    
    plan_id = query.data.split('_')[1]
    plan = plan_manager.get_plan_by_id(plan_id)
    
    if not plan:
        query.edit_message_text("Sorry, this plan is no longer available.")
        return ConversationHandler.END
    
    # Generate unique order ID
    order_id = str(uuid.uuid4())
    
    # Create purchase record
    purchase = Purchase(
        purchase_id=order_id,
        telegram_id=update.effective_user.id,
        plan_id=plan.id,
        amount=plan.price,
        currency=plan.currency,
        payment_id=None,
        status="pending",
        created_at=datetime.now().isoformat()
    )
    purchase_manager.add_purchase(purchase)
    
    # Create payment
    try:
        bot_username = context.bot.get_me().username
        success_url = f"https://t.me/{bot_username}?start=payment_{order_id}"
        
        payment_data = cryptomus.create_payment(
            amount=plan.price,
            currency=plan.currency,
            order_id=order_id,
            description=f"VPN Plan: {plan.name}",
            success_url=success_url
        )
        
        if 'result' not in payment_data or 'url' not in payment_data['result']:
            query.edit_message_text("Sorry, there was an error creating your payment.")
            return ConversationHandler.END
        
        payment_url = payment_data['result']['url']
        
        # Store in pending purchases
        pending_purchases[order_id] = {
            "user_id": update.effective_user.id,
            "plan_id": plan.id,
            "created_at": datetime.now().isoformat()
        }
        
        # Track for this user
        if update.effective_user.id not in purchase_awaiting_callbacks:
            purchase_awaiting_callbacks[update.effective_user.id] = []
        purchase_awaiting_callbacks[update.effective_user.id].append(order_id)
        
        # Create payment keyboard
        keyboard = [
            [InlineKeyboardButton("Pay Now", url=payment_url)],
            [InlineKeyboardButton("I've Paid", callback_data=f"check_{order_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Send payment instructions
        query.edit_message_text(
            f"*VPN Plan: {plan.name}*\n"
            f"Price: ${plan.price:.2f}\n"
            f"Traffic: {plan.traffic_limit} GB\n"
            f"Duration: {plan.expiration_days} days\n\n"
            "Please click the button below to make your payment. After payment, "
            "click 'I've Paid' to check the status.",
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

def check_payment(update: Update, context: CallbackContext) -> int:
    """Check payment status when user clicks 'I've Paid'."""
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
            # Process successful payment
            return process_successful_payment(update, context, order_id)
        else:
            # Payment not completed yet
            keyboard = [
                [InlineKeyboardButton("Check Again", callback_data=f"check_{order_id}")],
                [InlineKeyboardButton("Cancel", callback_data="cancel_payment")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            query.edit_message_text(
                "Your payment has not been confirmed yet. This may take a few minutes.\n\n"
                "Click 'Check Again' to refresh the status.",
                reply_markup=reply_markup
            )
            return PAYMENT_PENDING
            
    except Exception as e:
        logger.error(f"Payment check failed: {str(e)}")
        query.edit_message_text(
            "Sorry, there was an error checking your payment. "
            "Please try again later."
        )
        return ConversationHandler.END

def process_successful_payment(update: Update, context: CallbackContext, order_id: str) -> int:
    """Process a successful payment."""
    # Get purchase record
    purchase = purchase_manager.get_purchase_by_id(order_id)
    
    if not purchase:
        update.callback_query.edit_message_text(
            "Sorry, there was an error processing your purchase. "
            "Please contact support."
        )
        return ConversationHandler.END
    
    # Get plan details
    plan = plan_manager.get_plan_by_id(purchase.plan_id)
    
    if not plan:
        update.callback_query.edit_message_text(
            "Sorry, the plan you purchased is no longer available. "
            "Please contact support."
        )
        return ConversationHandler.END
    
    # Create a VPN user
    username = f"{update.effective_user.id}d{datetime.now().strftime('%Y%m%d%H%M%S')}"
    password = generate_random_password(32)
    
    try:
        # Create user via API
        vpn_user = VpnUser(
            username=username,
            password=password,
            traffic_limit=plan.traffic_limit,
            expiration_days=plan.expiration_days
        )
        
        vpn_client.add_user(vpn_user)
        
        # Update purchase with VPN credentials
        purchase.status = "completed"
        purchase.completed_at = datetime.now().isoformat()
        purchase.vpn_username = username
        purchase.vpn_password = password
        purchase_manager.update_purchase(purchase)
        
        # Generate VPN configuration
        vpn_config = generate_hy2_config(username, password, config)
        
        # Send success message with configuration
        update.callback_query.edit_message_text(
            f"✅ *Payment Successful!*\n\n"
            f"Your VPN account has been created:\n\n"
            f"Username: `{username}`\n"
            f"Password: `{password}`\n"
            f"Traffic Limit: {plan.traffic_limit} GB\n"
            f"Expires in: {plan.expiration_days} days\n\n"
            f"*VPN Configuration:*\n"
            f"`{vpn_config}`\n\n"
            f"Use this configuration with a Hysteria2 client to connect to the VPN.",
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Remove from pending purchases
        if order_id in pending_purchases:
            del pending_purchases[order_id]
        
        # Remove from awaiting callbacks
        if update.effective_user.id in purchase_awaiting_callbacks:
            if order_id in purchase_awaiting_callbacks[update.effective_user.id]:
                purchase_awaiting_callbacks[update.effective_user.id].remove(order_id)
        
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Error creating VPN user: {str(e)}")
        update.callback_query.edit_message_text(
            "Sorry, there was an error creating your VPN account. "
            "Please contact support."
        )
        return ConversationHandler.END

def cancel_payment(update: Update, context: CallbackContext) -> int:
    """Cancel the payment process."""
    query = update.callback_query
    query.answer()
    
    query.edit_message_text("Payment process cancelled. You can try again later.")
    return ConversationHandler.END

def show_purchase_history(update: Update, context: CallbackContext) -> None:
    """Show user's purchase history."""
    query = update.callback_query
    
    if query:
        query.answer()
    
    # Get user's purchases
    purchases = purchase_manager.get_user_purchases(update.effective_user.id)
    
    if not purchases:
        text = "You haven't made any purchases yet."
        if query:
            query.edit_message_text(text=text)
        else:
            update.message.reply_text(text=text)
        return
    
    # Sort purchases by creation date (newest first)
    purchases.sort(key=lambda p: p.created_at, reverse=True)
    
    # Create text with purchase history
    text = "📋 *Your Purchase History*\n\n"
    
    for i, purchase in enumerate(purchases, 1):
        plan = plan_manager.get_plan_by_id(purchase.plan_id)
        plan_name = plan.name if plan else "Unknown Plan"
        
        text += f"*{i}. {plan_name}*\n"
        text += f"Amount: ${purchase.amount:.2f}\n"
        text += f"Status: {purchase.status.title()}\n"
        text += f"Date: {purchase.created_at.split('T')[0]}\n"
        
        if purchase.status == "completed" and purchase.vpn_username:
            text += f"Username: `{purchase.vpn_username}`\n"
        
        text += "\n"
    
    # Add back button
    keyboard = [[InlineKeyboardButton("Back", callback_data="back_to_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if query:
        query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    else:
        update.message.reply_text(text=text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

def show_my_vpns(update: Update, context: CallbackContext) -> None:
    """Show user's active VPN accounts."""
    query = update.callback_query
    
    if query:
        query.answer()
    
    # Get user's completed purchases with VPN accounts
    purchases = [
        p for p in purchase_manager.get_user_purchases(update.effective_user.id)
        if p.status == "completed" and p.vpn_username
    ]
    
    if not purchases:
        text = "You don't have any active VPN accounts."
        if query:
            query.edit_message_text(text=text)
        else:
            update.message.reply_text(text=text)
        return
    
    # Sort purchases by creation date (newest first)
    purchases.sort(key=lambda p: p.completed_at or p.created_at, reverse=True)
    
    # Create text with VPN accounts
    text = "🔑 *Your VPN Accounts*\n\n"
    
    for i, purchase in enumerate(purchases, 1):
        plan = plan_manager.get_plan_by_id(purchase.plan_id)
        plan_name = plan.name if plan else "Unknown Plan"
        
        text += f"*{i}. {plan_name}*\n"
        text += f"Username: `{purchase.vpn_username}`\n"
        text += f"Password: `{purchase.vpn_password}`\n"
        text += "\n"
        
        # Generate VPN configuration
        vpn_config = generate_hy2_config(purchase.vpn_username, purchase.vpn_password, config)
        text += f"*Configuration:*\n`{vpn_config}`\n\n"
    
    # Add back button
    keyboard = [[InlineKeyboardButton("Back", callback_data="back_to_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if query:
        query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    else:
        update.message.reply_text(text=text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

def back_to_menu(update: Update, context: CallbackContext) -> None:
    """Return to the main menu."""
    query = update.callback_query
    query.answer()
    
    keyboard = [
        [InlineKeyboardButton("🛒 Purchase Plan", callback_data="purchase")],
        [InlineKeyboardButton("🔑 My VPNs", callback_data="my_vpns")],
        [InlineKeyboardButton("📝 Purchase History", callback_data="history")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    query.edit_message_text(
        f"Welcome {query.from_user.first_name}! 🌐\n\n"
        "I'm your VPN service bot. Use the buttons below to purchase plans "
        "or manage your VPN accounts.",
        reply_markup=reply_markup
    )

def handle_webhook_callback(order_id: str) -> None:
    """
    Handle webhook callback for completed payment.
    
    Args:
        order_id: Order ID of the completed payment
    """
    purchase = purchase_manager.get_purchase_by_id(order_id)
    if not purchase:
        logger.warning(f"Purchase not found for order_id: {order_id}")
        return
    
    # Check if this purchase is in pending state and has a user ID
    if purchase.status != "completed" and purchase.telegram_id:
        # Get plan details
        plan = plan_manager.get_plan_by_id(purchase.plan_id)
        
        if not plan:
            logger.warning(f"Plan not found for purchase: {order_id}")
            return
        
        # Create a VPN user
        username = f"{purchase.telegram_id}d{datetime.now().strftime('%Y%m%d%H%M%S')}"
        password = generate_random_password(32)
        
        try:
            # Create user via API
            vpn_user = VpnUser(
                username=username,
                password=password,
                traffic_limit=plan.traffic_limit,
                expiration_days=plan.expiration_days
            )
            
            vpn_client.add_user(vpn_user)
            
            # Update purchase with VPN credentials
            purchase.status = "completed"
            purchase.completed_at = datetime.now().isoformat()
            purchase.vpn_username = username
            purchase.vpn_password = password
            purchase_manager.update_purchase(purchase)
            
            logger.info(f"Created VPN account for completed payment: {order_id}")
            
            # Check if there's a pending conversation with this user
            if (purchase.telegram_id in purchase_awaiting_callbacks and 
                order_id in purchase_awaiting_callbacks[purchase.telegram_id]):
                # Will be handled by the conversation handler
                pass
            else:
                # Need to proactively message the user
                from telegram.ext import Updater
                updater = Updater(token=config["telegram_token"])
                
                # Generate VPN configuration
                vpn_config = generate_hy2_config(username, password, config)
                
                # Send success message with configuration
                updater.bot.send_message(
                    chat_id=purchase.telegram_id,
                    text=f"✅ *Payment Successful!*\n\n"
                        f"Your VPN account has been created:\n\n"
                        f"Username: `{username}`\n"
                        f"Password: `{password}`\n"
                        f"Traffic Limit: {plan.traffic_limit} GB\n"
                        f"Expires in: {plan.expiration_days} days\n\n"
                        f"*VPN Configuration:*\n"
                        f"`{vpn_config}`\n\n"
                        f"Use this configuration with a Hysteria2 client to connect to the VPN.",
                    parse_mode=ParseMode.MARKDOWN
                )
            
        except Exception as e:
            logger.error(f"Error processing webhook payment: {str(e)}")

# Register the webhook callback handler
register_payment_callback(handle_webhook_callback)

def get_client_handlers():
    """Return handlers related to client functionality."""
    
    # Create conversation handler for plan purchase
    purchase_conversation_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(show_plans, pattern='^purchase$'),
            CommandHandler('purchase', show_plans)
        ],
        states={
            SELECT_PLAN: [
                CallbackQueryHandler(select_plan, pattern='^plan_'),
                CallbackQueryHandler(start_client, pattern='^cancel$')
            ],
            PAYMENT_PENDING: [
                CallbackQueryHandler(check_payment, pattern='^check_'),
                CallbackQueryHandler(cancel_payment, pattern='^cancel_payment$')
            ]
        },
        fallbacks=[
            CallbackQueryHandler(cancel_payment, pattern='^cancel$'),
            CommandHandler('cancel', cancel_payment)
        ],
        allow_reentry=True
    )
    
    return [
        CommandHandler('buy', show_plans),
        CallbackQueryHandler(show_plans, pattern='^purchase$'),
        CallbackQueryHandler(show_purchase_history, pattern='^history$'),
        CallbackQueryHandler(show_my_vpns, pattern='^my_vpns$'),
        CallbackQueryHandler(back_to_menu, pattern='^back_to_menu$'),
        purchase_conversation_handler
    ]
