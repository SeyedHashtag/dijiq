from telegram.ext import CommandHandler, MessageHandler, Filters, Dispatcher
from src.bot.handlers.base import start, help_command
from src.bot.handlers.admin_handlers import add_user_conversation_handler
from src.bot.handlers.customer_handlers import purchase_conversation_handler, setup_customer_handlers
from src.bot.handlers.client_welcome import setup_client_welcome_handlers
from src.bot.handlers.admin_plans import setup_admin_plans_handlers
from src.bot.handlers.admin_broadcast import setup_admin_broadcast_handlers
from src.utils.config import is_admin

def setup_handlers(dispatcher: Dispatcher):
    """Set up all command and conversation handlers."""
    # Basic command handlers
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("help", help_command))
    
    # Admin conversation handlers
    dispatcher.add_handler(add_user_conversation_handler)
    
    # Setup client welcome handlers
    setup_client_welcome_handlers(dispatcher)
    
    # Setup customer handlers
    setup_customer_handlers(dispatcher)
    
    # Setup admin plans handlers
    setup_admin_plans_handlers(dispatcher)
    
    # Setup admin broadcast handlers
    setup_admin_broadcast_handlers(dispatcher)
    
    # Add a fallback handler
    dispatcher.add_handler(MessageHandler(Filters.text, start))
