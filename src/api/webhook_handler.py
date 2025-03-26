import json
import logging
from typing import Dict, Any, Callable, List
from src.utils.config import load_config
from src.payment.cryptomus import CryptomusClient
from src.models.purchase import Purchase, PaymentStatus

logger = logging.getLogger(__name__)

# Store callbacks to be executed when payment is completed
payment_callbacks: Dict[str, List[Callable]] = {}

def register_payment_callback(payment_id: str, callback: Callable) -> None:
    """Register a callback to be executed when payment is completed."""
    if payment_id not in payment_callbacks:
        payment_callbacks[payment_id] = []
    payment_callbacks[payment_id].append(callback)

def handle_payment_webhook(request_body: bytes, signature: str) -> Dict[str, Any]:
    """
    Handle payment webhook from Cryptomus.
    
    Args:
        request_body: Raw request body
        signature: Signature from request headers
        
    Returns:
        Response to be sent back to Cryptomus
    """
    config = load_config()
    
    # Create Cryptomus client
    client = CryptomusClient(
        merchant_id=config.get("cryptomus_merchant_id", ""),
        api_key=config.get("cryptomus_api_key", "")
    )
    
    # Verify signature
    if not client.verify_webhook_signature(request_body, signature):
        logger.warning("Invalid webhook signature")
        return {"status": "error", "message": "Invalid signature"}
    
    # Parse webhook data
    try:
        webhook_data = json.loads(request_body.decode('utf-8'))
        payment_data = webhook_data.get("payload", {})
        
        if not payment_data:
            logger.error("No payment data in webhook")
            return {"status": "error", "message": "No payment data"}
        
        payment_id = payment_data.get("uuid", "")
        status = payment_data.get("status")
        order_id = payment_data.get("order_id", "")
        
        logger.info(f"Received payment webhook: ID={payment_id}, Status={status}")
        
        # Process payment status
        if status == "paid":
            # Execute registered callbacks
            if payment_id in payment_callbacks:
                for callback in payment_callbacks[payment_id]:
                    try:
                        callback(payment_data)
                    except Exception as e:
                        logger.error(f"Error executing payment callback: {e}")
                
                # Remove callbacks after execution
                del payment_callbacks[payment_id]
            
            return {"status": "success"}
        elif status in ["expired", "failed"]:
            # Handle failed/expired payment
            # You might want to update the purchase status in your database
            return {"status": "success"}
        else:
            # Unhandled status
            logger.warning(f"Unhandled payment status: {status}")
            return {"status": "success"}
    
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        return {"status": "error", "message": str(e)}
