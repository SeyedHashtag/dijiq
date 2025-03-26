import hashlib
import hmac
import json
import logging
import requests
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class CryptomusClient:
    """Client for the Cryptomus payment API."""
    
    BASE_URL = "https://api.cryptomus.com/v1"
    
    def __init__(self, merchant_id: str, api_key: str):
        """
        Initialize Cryptomus client.
        
        Args:
            merchant_id: Your merchant ID
            api_key: Your API key
        """
        self.merchant_id = merchant_id
        self.api_key = api_key
    
    def _generate_sign(self, data: Dict[str, Any]) -> str:
        """Generate signature for API request."""
        encoded_data = json.dumps(data).encode()
        signature = hmac.new(
            self.api_key.encode(),
            encoded_data,
            hashlib.sha512
        ).hexdigest()
        return signature
    
    def _request(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Make a request to the Cryptomus API."""
        url = f"{self.BASE_URL}/{endpoint}"
        
        # Generate signature
        signature = self._generate_sign(data)
        
        # Set headers
        headers = {
            "merchant": self.merchant_id,
            "sign": signature,
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(url, json=data, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Cryptomus API request failed: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response: {e.response.text}")
            raise Exception(f"Payment API request failed: {str(e)}")
    
    def create_payment(self, amount: float, currency: str, order_id: str, 
                      description: str, success_url: Optional[str] = None) -> Dict[str, Any]:
        """Create a new payment."""
        data = {
            "amount": str(amount),
            "currency": currency,
            "order_id": order_id,
            "description": description
        }
        
        if success_url:
            data["url_success"] = success_url
        
        return self._request("payment", data)
    
    def check_payment(self, order_id: str) -> Dict[str, Any]:
        """Check payment status by order ID."""
        data = {"order_id": order_id}
        return self._request("payment/info", data)
    
    def verify_webhook_signature(self, payload: Dict[str, Any], signature: str) -> bool:
        """Verify webhook signature."""
        try:
            computed_signature = self._generate_sign(payload)
            return hmac.compare_digest(computed_signature, signature)
        except Exception as e:
            logger.error(f"Signature verification failed: {str(e)}")
            return False
