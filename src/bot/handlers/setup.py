from telegram.ext import CommandHandler, MessageHandler, Filters, Dispatcher
from src.bot.handlers.base import start, help_command
from src.bot.handlers.admin_handlers import add_user_conversation_handler
from src.bot.handlers.customer_handlers import purchase_conversation_handler

def setup_handlers(dispatcher: Dispatcher):
    """Set up all command and conversation handlers."""
    # Common handlers
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("help", help_command))
    
    # Admin conversation handlers
    dispatcher.add_handler(add_user_conversation_handler)
    
    # Customer conversation handlers
    dispatcher.add_handler(purchase_conversation_handler)
    
    # Add a fallback handler that responds to all text messages
    dispatcher.add_handler(MessageHandler(Filters.text, start))
