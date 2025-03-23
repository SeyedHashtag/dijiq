import logging
import os
from telegram.ext import Updater
from src.utils.config import load_config
from src.bot.handlers import setup_handlers
from src.api.webhook_handler import WebhookServer

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
    """Start the bot and webhook server."""
    # Load configuration
    try:
        config = load_config()
        
        # Create the Updater and pass it your bot's token
        updater = Updater(config['telegram_token'])
        
        # Get the dispatcher to register handlers
        dispatcher = updater.dispatcher
        
        # Set up all handlers
        setup_handlers(dispatcher)
        
        # Start webhook server for payment notifications if webhook config is present
        webhook_host = os.environ.get('WEBHOOK_HOST')
        webhook_port = int(os.environ.get('WEBHOOK_PORT', 8080))
        
        if webhook_host:
            logger.info("Starting webhook server for payment notifications")
            webhook_server = WebhookServer(host=webhook_host, port=webhook_port)
            webhook_server.start()
        
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
