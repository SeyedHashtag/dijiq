import hashlib
import json
import hmac
import uuid
import requests
import logging
from typing import Dict, Any, Optional, List, Union

logger = logging.getLogger(__name__)

class CryptomusClient:
    """
    Client for interacting with the Cryptomus payment API.
    """
    def __init__(self, merchant_id: str, api_key: str, test_mode: bool = False):
        """
        Initialize the Cryptomus API client.
        
        Args:
            merchant_id: Your Cryptomus merchant ID
            api_key: Your Cryptomus API key
            test_mode: Whether to use test mode (sandbox)
        """
        self.merchant_id = merchant_id
        self.api_key = api_key
        self.test_mode = test_mode
        self.base_url = "https://api.cryptomus.com/v1"
    
    def _sign_request(self, payload: Dict[str, Any]) -> Dict[str, str]:
        """
        Sign the request payload for Cryptomus API.
        
        Args:
            payload: Request data to sign
            
        Returns:
            Headers with authentication
        """
        json_payload = json.dumps(payload)
        payload_hash = hashlib.md5(json_payload.encode()).hexdigest()
        
        signature = hmac.new(
            self.api_key.encode(),
            payload_hash.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return {
            'merchant': self.merchant_id,
            'sign': signature,
            'Content-Type': 'application/json'
        }
    
    def create_payment(self, 
                      amount: float,
                      currency: str,
                      order_id: str = None,
                      description: str = None,
                      return_url: str = None,
                      callback_url: str = None,
                      expiration: int = None) -> Dict[str, Any]:
        """
        Create a new payment in Cryptomus.
        
        Args:
            amount: Payment amount
            currency: Payment currency (e.g., 'USDT')
            order_id: Your internal order ID (optional)
            description: Payment description (optional)
            return_url: URL to redirect user after payment (optional)
            callback_url: Webhook URL for payment notifications (optional)
            expiration: Payment expiration in minutes (optional)
            
        Returns:
            Payment details from Cryptomus
        """
        # Generate order ID if not provided
        if not order_id:
            order_id = str(uuid.uuid4())
        
        payload = {
            "amount": str(amount),
            "currency": currency,
            "order_id": order_id,
            "is_test": self.test_mode
        }
        
        # Add optional parameters if provided
        if description:
            payload["description"] = description
        if return_url:
            payload["url_return"] = return_url
        if callback_url:
            payload["url_callback"] = callback_url
        if expiration:
            payload["lifetime"] = expiration
        
        headers = self._sign_request(payload)
        url = f"{self.base_url}/payment"
        
        try:
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json().get('result', {})
        except requests.exceptions.RequestException as e:
            logger.error(f"Cryptomus payment creation error: {str(e)}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Response: {e.response.text}")
            raise
    
    def get_payment(self, payment_id: str = None, order_id: str = None) -> Dict[str, Any]:
        """
        Get payment details from Cryptomus.
        
        Args:
            payment_id: Cryptomus payment ID (optional)
            order_id: Your internal order ID (optional)
            
        Returns:
            Payment details
            
        Note:
            Either payment_id or order_id must be provided
        """
        if not payment_id and not order_id:
            raise ValueError("Either payment_id or order_id must be provided")
        
        payload = {}
        if payment_id:
            payload["uuid"] = payment_id
        if order_id:
            payload["order_id"] = order_id
        
        headers = self._sign_request(payload)
        url = f"{self.base_url}/payment/info"
        
        try:
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json().get('result', {})
        except requests.exceptions.RequestException as e:
            logger.error(f"Cryptomus payment info error: {str(e)}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Response: {e.response.text}")
            raise
    
    def verify_webhook_signature(self, signature: str, payload: Union[str, Dict[str, Any]]) -> bool:
        """
        Verify the signature of a webhook notification from Cryptomus.
        
        Args:
            signature: Signature from the webhook headers
            payload: Request payload (JSON string or dictionary)
            
        Returns:
            True if the signature is valid, False otherwise
        """
        if isinstance(payload, dict):
            payload = json.dumps(payload)
        
        payload_hash = hashlib.md5(payload.encode()).hexdigest()
        
        expected_signature = hmac.new(
            self.api_key.encode(),
            payload_hash.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_signature)
