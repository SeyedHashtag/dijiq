"""
Module for setting up all bot handlers.
"""

from telegram import Update, ParseMode
from telegram.ext import Dispatcher, CommandHandler, CallbackQueryHandler, CallbackContext
from src.utils.config import is_admin

from .base import get_base_handlers
from .user_management import get_user_management_handlers
from .client import get_client_handlers, start_client

def start_router(update: Update, context: CallbackContext) -> None:
    """
    Router function to direct users to either admin or client interface.
    
    Args:
        update: The update to process
        context: The context object for the update
    """
    user = update.effective_user
    
    # Check if user is an admin
    if is_admin(user.id):
        # Import locally to avoid circular imports
        from .user_management import start as admin_start
        return admin_start(update, context)
    else:
        # Regular user, route to client interface
        return start_client(update, context)

def setup_handlers(dispatcher: Dispatcher) -> None:
    """
    Set up all command and conversation handlers.
    
    Args:
        dispatcher: The Telegram dispatcher to register handlers with
    """
    # Add the start router as the main entry point
    dispatcher.add_handler(CommandHandler("start", start_router))
    
    # Add base handlers
    for handler in get_base_handlers():
        dispatcher.add_handler(handler)
    
    # Add user management handlers for admin functionality
    for handler in get_user_management_handlers():
        dispatcher.add_handler(handler)
    
    # Add client-side handlers for regular users
    for handler in get_client_handlers():
        dispatcher.add_handler(handler)
