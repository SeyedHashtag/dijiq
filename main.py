import logging
import os
from telegram.ext import Updater
from src.utils.config import load_config
from src.bot.handlers.setup import setup_handlers  # Updated import path

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Set debug level for API client if DEBUG environment variable is set
if os.environ.get('DEBUG', '').lower() in ('true', '1', 'yes'):
    logging.getLogger('src.api.vpn_client').setLevel(logging.DEBUG)

def main():
    """Start the bot."""
    # Load configuration
    try:
        config = load_config()
        
        # Create the Updater and pass it your bot's token
        updater = Updater(config['telegram_token'])
        
        # Get the dispatcher to register handlers
        dispatcher = updater.dispatcher
        
        # Set up all handlers
        setup_handlers(dispatcher)
        
        # Start the Bot
        updater.start_polling()
        logger.info("Bot started successfully!")
        
        # Run the bot until you press Ctrl-C
        updater.idle()
        
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        raise

if __name__ == '__main__':
    main()
