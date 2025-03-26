import hashlib
import hmac
import json
import uuid
import requests
import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class CryptomusClient:
    """Client for Cryptomus payment API."""
    
    def __init__(self, merchant_id: str, api_key: str, base_url: str = "https://api.cryptomus.com/v1"):
        self.merchant_id = merchant_id
        self.api_key = api_key
        self.base_url = base_url
    
    def _generate_sign(self, body: Dict[str, Any]) -> str:
        """Generate signature for Cryptomus API requests."""
        encoded_body = json.dumps(body).encode()
        sign = hmac.new(
            self.api_key.encode(),
            encoded_body,
            hashlib.sha512
        ).hexdigest()
        return sign
    
    def _make_request(self, endpoint: str, method: str = "POST", body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make a request to Cryptomus API."""
        if body is None:
            body = {}
        
        url = f"{self.base_url}/{endpoint}"
        sign = self._generate_sign(body)
        
        headers = {
            "merchant": self.merchant_id,
            "sign": sign,
            "Content-Type": "application/json"
        }
        
        try:
            if method.upper() == "POST":
                response = requests.post(url, json=body, headers=headers)
            elif method.upper() == "GET":
                response = requests.get(url, headers=headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Cryptomus API request failed: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response: {e.response.text}")
            raise
    
    def create_payment(self, amount: float, currency: str, order_id: str, user_id: int) -> Dict[str, Any]:
        """
        Create a new payment.
        
        Args:
            amount: Payment amount
            currency: Currency code (USD, EUR, etc)
            order_id: Unique order ID
            user_id: Telegram user ID
            
        Returns:
            Payment details including payment URL
        """
        body = {
            "amount": str(amount),
            "currency": currency,
            "order_id": order_id,
            "url_return": "https://t.me/your_bot_username",  # Replace with your bot's username
            "url_callback": "https://your-webhook-url.com/webhook/payment",  # Replace with your webhook URL
            "is_payment_multiple": False,
            "lifetime": 3600,  # 1 hour in seconds
            "additional_data": {
                "user_id": user_id
            }
        }
        
        response = self._make_request("payment", "POST", body)
        return response.get("result", {})
    
    def check_payment(self, payment_id: str) -> Dict[str, Any]:
        """
        Check payment status.
        
        Args:
            payment_id: Payment ID from Cryptomus
            
        Returns:
            Payment details including status
        """
        body = {
            "uuid": payment_id
        }
        
        response = self._make_request("payment/info", "POST", body)
        return response.get("result", {})
    
    def verify_webhook_signature(self, request_body: bytes, signature: str) -> bool:
        """
        Verify webhook signature from Cryptomus.
        
        Args:
            request_body: Raw request body bytes
            signature: Signature from request headers
            
        Returns:
            True if signature is valid, False otherwise
        """
        calculated_sign = hmac.new(
            self.api_key.encode(),
            request_body,
            hashlib.sha512
        ).hexdigest()
        
        return hmac.compare_digest(calculated_sign, signature)
