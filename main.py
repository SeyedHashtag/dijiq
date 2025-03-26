import logging
import os
from telegram.ext import Updater
from src.utils.config import load_config
from src.bot.handlers import setup_handlers
from src.api.webhook_handler import WebhookServer, register_payment_callback

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Set debug level for API client if DEBUG environment variable is set
if os.environ.get('DEBUG', '').lower() in ('true', '1', 'yes'):
    logging.getLogger('src.api.vpn_client').setLevel(logging.DEBUG)

def payment_notification_callback(order_id: str):
    """Callback function for payment notifications."""
    from telegram.ext import Updater
    from src.models.purchase import PurchaseManager
    from src.utils.config import load_config
    from src.utils.vpn_config import generate_hy2_config
    
    # Get the purchase information
    purchase_manager = PurchaseManager()
    purchase = purchase_manager.get_purchase_by_id(order_id)
    
    if not purchase or not purchase.telegram_id:
        logger.error(f"Cannot notify user: Purchase not found or no telegram_id for order {order_id}")
        return
    
    if not purchase.vpn_username or not purchase.vpn_password:
        logger.error(f"Cannot notify user: Missing VPN credentials for order {order_id}")
        return
    
    # Load config
    config = load_config()
    
    # Generate VPN configuration
    vpn_config = generate_hy2_config(purchase.vpn_username, purchase.vpn_password, config)
    
    # Set up temporary Telegram updater to send message
    updater = Updater(config['telegram_token'])
    
    # Send notification message
    try:
        updater.bot.send_message(
            chat_id=purchase.telegram_id,
            text=f"✅ *Payment Received!*\n\n"
                f"Your VPN account has been created:\n\n"
                f"*Username:* `{purchase.vpn_username}`\n"
                f"*Password:* `{purchase.vpn_password}`\n"
                f"*Traffic Limit:* 100 GB\n"
                f"*Expires in:* 90 days\n\n"
                f"*Configuration String:*\n"
                f"`{vpn_config}`\n\n"
                f"To use this VPN, import the configuration into your Hysteria2 client.",
            parse_mode="Markdown"
        )
        logger.info(f"Payment notification sent to user {purchase.telegram_id} for order {order_id}")
    except Exception as e:
        logger.error(f"Failed to send payment notification: {str(e)}")

def main():
    """Start the bot and webhook server."""
    # Load configuration
    try:
        config = load_config()
        
        # Register payment notification callback
        register_payment_callback(payment_notification_callback)
        
        # Start webhook server for payment notifications if configured
        webhook_host = os.environ.get('WEBHOOK_HOST')
        webhook_port = int(os.environ.get('WEBHOOK_PORT', 8080))
        
        if webhook_host:
            logger.info("Starting webhook server for payment notifications")
            webhook_server = WebhookServer(host=webhook_host, port=webhook_port)
            webhook_server.start()
        
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
