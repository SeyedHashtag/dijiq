from flask import Flask, request, jsonify
import logging
from src.api.cryptomus_client import CryptomusClient
from src.db.storage import Database
from src.models.user import VpnUser
from src.api.vpn_client import VpnApiClient
from src.utils.password import generate_random_password
import threading
import urllib.parse

logger = logging.getLogger(__name__)
app = Flask(__name__)

# Global references
db = Database()
vpn_client = None
cryptomus_client = None
config = None

@app.route('/webhook/cryptomus', methods=['POST'])
def cryptomus_webhook():
    """Handle incoming webhook notifications from Cryptomus."""
    try:
        # Verify the signature
        signature = request.headers.get('sign')
        if not signature:
            logger.error("Missing signature in Cryptomus webhook")
            return jsonify({"status": "error", "message": "Invalid signature"}), 400
        
        payload = request.json
        if not cryptomus_client.verify_webhook_signature(signature, payload):
            logger.error("Invalid signature in Cryptomus webhook")
            return jsonify({"status": "error", "message": "Invalid signature"}), 400
        
        # Process the webhook data
        order_id = payload.get('order_id')
        status = payload.get('status')
        payment_id = payload.get('uuid')
        
        logger.info(f"Received payment webhook: {order_id}, status: {status}")
        
        # Extract internal payment ID from order_id (format should be payment_123)
        if order_id and order_id.startswith('payment_'):
            internal_payment_id = int(order_id.split('_')[1])
            
            # Update payment status in database
            db.update_payment(internal_payment_id, {
                'status': status,
                'external_id': payment_id
            })
            
            # If payment is completed, create VPN account
            if status == 'paid':
                process_successful_payment(internal_payment_id)
        
        return jsonify({"status": "success"}), 200
    
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

def process_successful_payment(payment_id):
    """Process a successful payment by creating a VPN account."""
    try:
        # Get payment details
        payment = db.get_payment(payment_id)
        if not payment:
            logger.error(f"Payment not found: {payment_id}")
            return
        
        # Get plan details
        plan = db.get_plan(payment['plan_id'])
        if not plan:
            logger.error(f"Plan not found for payment: {payment_id}")
            return
        
        # Create VPN user
        username = f"{payment['user_id']}d{payment_id}"
        password = generate_random_password(32)
        
        user = VpnUser(
            username=username,
            password=password,
            traffic_limit=plan['traffic_limit'],
            expiration_days=plan['duration_days']
        )
        
        # Call the API to create the user
        response = vpn_client.add_user(user)
        
        logger.info(f"VPN account created for payment {payment_id}: {username}")
        
        # Store account details in a separate table or send to user
        # This is implementation-specific and would depend on how you want to handle it
        
    except Exception as e:
        logger.error(f"Error creating VPN account for payment {payment_id}: {str(e)}")

def setup_webhook_server(app_config):
    """Set up and start the webhook server."""
    global config, vpn_client, cryptomus_client
    
    config = app_config
    
    # Initialize VPN client
    vpn_client = VpnApiClient(
        base_url=config['vpn_api_url'],
        api_key=config.get('api_key')
    )
    
    # Initialize Cryptomus client if credentials are available
    if config.get('cryptomus_merchant_id') and config.get('cryptomus_api_key'):
        cryptomus_client = CryptomusClient(
            merchant_id=config['cryptomus_merchant_id'],
            api_key=config['cryptomus_api_key'],
            test_mode=config.get('cryptomus_test_mode', False)
        )
    
    # Extract host and port from callback URL
    try:
        parsed_url = urllib.parse.urlparse(config.get('payment_callback_url', ''))
        host = parsed_url.hostname or '0.0.0.0'
        port = parsed_url.port or 5000
        
        # Start Flask app
        app.run(host=host, port=port, debug=False)
    except Exception as e:
        logger.error(f"Failed to start webhook server: {str(e)}")
