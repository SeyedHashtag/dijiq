import base64
import json
import uuid
from hashlib import md5
import requests
import os
from dotenv import load_dotenv

load_dotenv()

class CryptomusPayment:
    def __init__(self):
        self.merchant_id = os.getenv('CRYPTOMUS_MERCHANT_ID')
        self.payment_api_key = os.getenv('CRYPTOMUS_API_KEY')
        self.base_url = "https://api.cryptomus.com/v1"

    def _check_credentials(self):
        if not self.merchant_id or not self.payment_api_key:
            return False
        return True

    def _generate_sign(self, payload):
        encoded_data = base64.b64encode(
            json.dumps(payload).encode("utf-8")
        ).decode("utf-8")
        return md5(f"{encoded_data}{self.payment_api_key}".encode("utf-8")).hexdigest()

    def create_payment(self, amount, plan_gb):
        if not self._check_credentials():
            return {"error": "Payment credentials not configured"}

        payment_id = str(uuid.uuid4())
        payload = {
            "amount": str(amount),
            "currency": "USD",
            "order_id": payment_id,
            "is_payment_multiple": False,
            "lifetime": 3600,
            "additional_data": json.dumps({
                "plan_gb": plan_gb,
                "payment_id": payment_id
            })
        }

        try:
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
            return {"error": f"API Error: {response.text}"}
        except Exception as e:
            return {"error": f"Request Error: {str(e)}"}

    def check_payment_status(self, payment_id):
        if not self._check_credentials():
            return {"error": "Payment credentials not configured"}

        payload = {
            "uuid": payment_id
        }

        try:
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
                result = response.json()
                # Add debug logging
                print(f"Payment status response: {json.dumps(result, indent=2)}")
                
                # Extract and normalize payment data
                if 'result' in result:
                    payment_data = result['result']
                    # Ensure consistent field names
                    payment_data['amount_paid'] = float(payment_data.get('paid_amount', 0))
                    payment_data['amount'] = float(payment_data.get('amount', 0))
                    payment_data['payment_status'] = payment_data.get('status', '')
                    result['result'] = payment_data
                
                return result
            return {"error": f"API Error: {response.text}"}
        except Exception as e:
            return {"error": f"Request Error: {str(e)}"} 
