import logging
import os
import sys
from telegram.ext import Updater
from src.utils.config import load_config

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Set debug level for API client if DEBUG environment variable is set
if os.environ.get('DEBUG', '').lower() in ('true', '1', 'yes'):
    logging.getLogger('src.api.vpn_client').setLevel(logging.DEBUG)
    # Set everything to DEBUG to troubleshoot handler issues
    logging.getLogger().setLevel(logging.DEBUG)

def main():
    """Start the bot."""
    # Load configuration
    try:
        config = load_config()
        
        # Create the Updater and pass it your bot's token
        updater = Updater(config['telegram_token'])
        
        # Get the dispatcher to register handlers
        dispatcher = updater.dispatcher
        
        # IMPORTANT: Import handlers here to avoid circular imports
        from src.bot.handlers.base import start, help_command
        from src.bot.handlers.admin_handlers import add_user_conversation_handler
        from src.bot.handlers.customer_handlers import purchase_conversation_handler
        
        # Register commands
        from telegram.ext import CommandHandler, MessageHandler, Filters
        
        # Basic command handlers
        dispatcher.add_handler(CommandHandler("start", start))
        dispatcher.add_handler(CommandHandler("help", help_command))
        
        # Add conversation handlers
        dispatcher.add_handler(add_user_conversation_handler)
        dispatcher.add_handler(purchase_conversation_handler)
        
        # Fallback for text messages
        dispatcher.add_handler(MessageHandler(Filters.text, start))
        
        logger.info("Handlers registered successfully")
        
        # Start the Bot
        updater.start_polling()
        logger.info("Bot started successfully!")
        
        # Run the bot until you press Ctrl-C
        updater.idle()
        
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        # Print stack trace for better debugging
        import traceback
        logger.error(traceback.format_exc())
        raise

if __name__ == '__main__':
    main()
