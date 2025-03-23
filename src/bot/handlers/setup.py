"""
Module for setting up all bot handlers.
"""

from telegram.ext import Dispatcher, CommandHandler, CallbackQueryHandler

from .base import get_base_handlers
from .user_management import get_user_management_handlers
from .client import get_client_handlers, start_client

def setup_handlers(dispatcher: Dispatcher) -> None:
    """
    Set up all command and conversation handlers.
    
    Args:
        dispatcher: The Telegram dispatcher to register handlers with
    """
    # Add base handlers
    for handler in get_base_handlers():
        dispatcher.add_handler(handler)
    
    # Add user management handlers
    for handler in get_user_management_handlers():
        dispatcher.add_handler(handler)
    
    # Add client-side handlers
    for handler in get_client_handlers():
        dispatcher.add_handler(handler)
    
    # Add main client entry point
    dispatcher.add_handler(CommandHandler("start", start_client))
