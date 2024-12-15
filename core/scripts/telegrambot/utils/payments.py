import base64
import json
import uuid
from hashlib import md5
import requests
import os
from dotenv import load_dotenv

load_dotenv()

MERCHANT_ID = os.getenv('CRYPTOMUS_MERCHANT_ID')
PAYMENT_API_KEY = os.getenv('CRYPTOMUS_API_KEY')

class CryptomusPayment:
    def __init__(self):
        self.merchant_id = MERCHANT_ID
        self.payment_api_key = PAYMENT_API_KEY
        self.base_url = "https://api.cryptomus.com/v1"

    def _generate_sign(self, payload):
        encoded_data = base64.b64encode(
            json.dumps(payload).encode("utf-8")
        ).decode("utf-8")
        return md5(f"{encoded_data}{self.payment_api_key}".encode("utf-8")).hexdigest()

    def create_payment(self, amount, plan_gb):
        payment_id = str(uuid.uuid4())
        payload = {
            "amount": str(amount),
            "currency": "USD",
            "order_id": payment_id,
            "network": "tron",
            "url_callback": "https://your-callback-url.com/payment/callback",
            "is_payment_multiple": False,
            "lifetime": 3600,
            "to_currency": "USDT",
            "additional_data": json.dumps({
                "plan_gb": plan_gb,
                "payment_id": payment_id
            })
        }

        headers = {
            "merchant": self.merchant_id,
            "sign": self._generate_sign(payload)
        }

        response = requests.post(
            f"{self.base_url}/payment",
            json=payload,
            headers=headers
        )

        if response.status_code == 200:
            return response.json()
        return None

    def check_payment_status(self, payment_id):
        payload = {
            "uuid": payment_id
        }

        headers = {
            "merchant": self.merchant_id,
            "sign": self._generate_sign(payload)
        }

        response = requests.post(
            f"{self.base_url}/payment/info",
            json=payload,
            headers=headers
        )

        if response.status_code == 200:
            return response.json()
        return None 
