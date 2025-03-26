"""
Module for setting up all bot handlers.
"""

from telegram import Update
from telegram.ext import Dispatcher, CommandHandler, CallbackContext
from src.utils.config import is_admin

def start_router(update: Update, context: CallbackContext) -> None:
    """
    Router function to direct users to either admin or client interface.
    
    Args:
        update: The update to process
        context: The context object for the update
    """
    user = update.effective_user
    
    # Import locally to avoid circular imports
    if is_admin(user.id):
        # Admin user, use admin interface
        from .handlers import start
        return start(update, context)
    else:
        # Regular user, use client interface
        from .customer import start_customer
        return start_customer(update, context)

def setup_handlers(dispatcher: Dispatcher) -> None:
    """
    Set up all command and conversation handlers.
    
    Args:
        dispatcher: The Telegram dispatcher to register handlers with
    """
    # Import handler functions locally to avoid circular imports
    from .base import get_base_handlers
    from .handlers import get_user_management_handlers
    from .customer import get_customer_handlers
    
    # Add the start router as the main entry point
    dispatcher.add_handler(CommandHandler("start", start_router))
    
    # Add base handlers
    for handler in get_base_handlers():
        dispatcher.add_handler(handler)
    
    # Add customer-side handlers
    for handler in get_customer_handlers():
        dispatcher.add_handler(handler)
    
    # Add admin-side handlers
    for handler in get_user_management_handlers():
        dispatcher.add_handler(handler)
