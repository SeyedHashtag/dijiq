import json
import logging
from typing import Dict, Any, Callable, Optional
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
from datetime import datetime

from src.payment.cryptomus import CryptomusClient
from src.models.purchase import PurchaseManager
from src.models.user import VpnUser
from src.api.vpn_client import VpnApiClient
from src.utils.config import load_config
from src.utils.password import generate_random_password

logger = logging.getLogger(__name__)

# Global callback for handling completed payments
payment_completed_callback: Optional[Callable[[str], None]] = None

class WebhookHandler(BaseHTTPRequestHandler):
    """HTTP handler for payment webhooks."""
    
    def _set_response(self, status_code=200):
        """Set response headers."""
        self.send_response(status_code)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
    
    def do_POST(self):
        """Handle POST requests (webhooks)."""
        # Read request body
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        try:
            # Parse JSON payload
            payload = json.loads(post_data.decode('utf-8'))
            logger.info(f"Received webhook: {self.path}")
            logger.debug(f"Webhook payload: {payload}")
            
            # Handle based on webhook path
            if self.path == '/webhook/payment':
                self._handle_payment_webhook(payload)
            else:
                logger.warning(f"Unknown webhook path: {self.path}")
                self._set_response(404)
                self.wfile.write(json.dumps({"status": "error", "message": "Unknown webhook"}).encode())
                return
            
            # Send success response
            self._set_response(200)
            self.wfile.write(json.dumps({"status": "success"}).encode())
            
        except json.JSONDecodeError:
            logger.error("Invalid JSON in webhook payload")
            self._set_response(400)
            self.wfile.write(json.dumps({"status": "error", "message": "Invalid JSON"}).encode())
        except Exception as e:
            logger.error(f"Error processing webhook: {str(e)}")
            self._set_response(500)
            self.wfile.write(json.dumps({"status": "error", "message": "Internal server error"}).encode())
    
    def _handle_payment_webhook(self, payload: Dict[str, Any]):
        """
        Handle payment webhook from Cryptomus.
        """
        try:
            # Load config
            config = load_config()
            
            # Verify signature
            signature = self.headers.get('sign', '')
            
            # Initialize Cryptomus client
            cryptomus = CryptomusClient(
                merchant_id=config.get('cryptomus_merchant_id', ''),
                api_key=config.get('cryptomus_api_key', '')
            )
            
            # Verify webhook signature
            if not cryptomus.verify_webhook_signature(payload, signature):
                logger.warning("Invalid webhook signature")
                return
            
            # Extract payment info
            order_id = payload.get('order_id')
            status = payload.get('status')
            
            if not order_id or not status:
                logger.warning("Missing order_id or status in webhook payload")
                return
            
            # Handle payment status
            if status == 'paid':
                # Process the completed payment
                process_completed_payment(order_id)
                
            elif status == 'canceled':
                # Update purchase record as cancelled
                purchase_manager = PurchaseManager()
                purchase = purchase_manager.get_purchase_by_id(order_id)
                
                if purchase:
                    purchase.status = "cancelled"
                    purchase_manager.update_purchase(purchase)
                    logger.info(f"Payment cancelled for order {order_id}")
            
        except Exception as e:
            logger.error(f"Error handling payment webhook: {str(e)}")
            raise


def process_completed_payment(order_id: str) -> None:
    """Process a completed payment by creating a VPN account."""
    # Get purchase record
    purchase_manager = PurchaseManager()
    purchase = purchase_manager.get_purchase_by_id(order_id)
    
    if not purchase:
        logger.warning(f"Purchase not found for order_id: {order_id}")
        return
    
    # Check if this purchase is in pending state
    if purchase.status != "pending":
        logger.info(f"Purchase {order_id} is already processed (status: {purchase.status})")
        return
    
    # Load configuration
    config = load_config()
    
    # Initialize VPN client
    vpn_client = VpnApiClient(
        base_url=config['vpn_api_url'],
        api_key=config.get('api_key')
    )
    
    try:
        # Generate username and password for VPN
        username = f"{purchase.telegram_id}d{datetime.now().strftime('%Y%m%d%H%M%S')}"
        password = generate_random_password(32)
        
        # Create VPN user
        vpn_user = VpnUser(
            username=username,
            password=password,
            traffic_limit=100,  # 100 GB
            expiration_days=90  # 90 days
        )
        
        # Call the API to add the user
        vpn_client.add_user(vpn_user)
        
        # Update purchase record with VPN credentials
        purchase.status = "completed"
        purchase.completed_at = datetime.now().isoformat()
        purchase.vpn_username = username
        purchase.vpn_password = password
        purchase_manager.update_purchase(purchase)
        
        logger.info(f"Successfully processed payment for order {order_id}, created VPN user {username}")
        
        # Notify the user with the telegram bot
        if payment_completed_callback:
            payment_completed_callback(order_id)
        
    except Exception as e:
        logger.error(f"Error processing completed payment: {str(e)}")
        purchase.status = "failed"
        purchase_manager.update_purchase(purchase)


class WebhookServer:
    """Server for handling payment webhooks."""
    
    def __init__(self, host='0.0.0.0', port=8080):
        """Initialize webhook server."""
        self.host = host
        self.port = port
        self.server = None
        self.thread = None
    
    def start(self):
        """Start the webhook server in a separate thread."""
        try:
            self.server = HTTPServer((self.host, self.port), WebhookHandler)
            self.thread = threading.Thread(target=self.server.serve_forever)
            self.thread.daemon = True
            self.thread.start()
            logger.info(f"Webhook server started at http://{self.host}:{self.port}")
        except Exception as e:
            logger.error(f"Failed to start webhook server: {str(e)}")
            raise
    
    def stop(self):
        """Stop the webhook server."""
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            logger.info("Webhook server stopped")


def register_payment_callback(callback: Callable[[str], None]):
    """Register a callback for completed payments."""
    global payment_completed_callback
    payment_completed_callback = callback
