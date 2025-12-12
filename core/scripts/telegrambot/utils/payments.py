import base64
import json
import uuid
from hashlib import md5
import requests
import os
from dotenv import load_dotenv

load_dotenv()

class CryptoPayment:
    def __init__(self):
        self.merchant_id = os.getenv('CRYPTO_MERCHANT_ID')
        self.payment_api_key = os.getenv('CRYPTO_API_KEY')
        self.base_url = "https://api.heleket.com/v1/payment"

    def _check_credentials(self):
        if not self.merchant_id or not self.payment_api_key:
            return False
        return True

    def _generate_sign(self, payload):
        encoded_data = base64.b64encode(
            json.dumps(payload).encode("utf-8")
        ).decode("utf-8")
        return md5(f"{encoded_data}{self.payment_api_key}".encode("utf-8")).hexdigest()

    def create_payment(self, amount, plan_gb, user_id, currency="USD", network=None, to_currency=None, url_return=None, url_success=None, url_callback=None, is_payment_multiple=False, lifetime=3600, additional_data=None, subtract=None, accuracy_payment_percent=None, currencies=None, except_currencies=None, course_source=None, from_referral_code=None, discount_percent=None, is_refresh=False):
        if not self._check_credentials():
            return {"error": "Payment credentials not configured"}

        payment_id = str(uuid.uuid4())
        payload = {
            "amount": str(amount),
            "currency": currency,
            "order_id": payment_id,
            "is_payment_multiple": is_payment_multiple,
            "lifetime": lifetime
        }
        # Optional parameters
        if network:
            payload["network"] = network
        if to_currency:
            payload["to_currency"] = to_currency
        if url_return:
            payload["url_return"] = url_return
        if url_success:
            payload["url_success"] = url_success
        if url_callback:
            payload["url_callback"] = url_callback
        if subtract is not None:
            payload["subtract"] = subtract
        if accuracy_payment_percent is not None:
            payload["accuracy_payment_percent"] = accuracy_payment_percent
        if currencies:
            payload["currencies"] = currencies
        if except_currencies:
            payload["except_currencies"] = except_currencies
        if course_source:
            payload["course_source"] = course_source
        if from_referral_code:
            payload["from_referral_code"] = from_referral_code
        if discount_percent is not None:
            payload["discount_percent"] = discount_percent
        if is_refresh:
            payload["is_refresh"] = is_refresh
        # Additional data
        if additional_data is None:
            additional_data = {}
        additional_data.update({
            "plan_gb": plan_gb,
            "payment_id": payment_id,
            "user_id": user_id
        })
        payload["additional_data"] = json.dumps(additional_data)

        try:
            headers = {
                "merchant": self.merchant_id,
                "sign": self._generate_sign(payload)
            }

            response = requests.post(
                self.base_url,  # Fixed endpoint
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

            # The base_url already contains the /payment segment (https://api.heleket.com/v1/payment)
            # the info endpoint is exposed as /info, so call {base_url}/info
            info_url = f"{self.base_url}/info"

            response = requests.post(
                info_url,
                json=payload,
                headers=headers
            )

            # Return full response for easier debugging when not 200
            if response.status_code == 200:
                return response.json()
            return {"error": f"API Error: {response.status_code} - {response.text}", "status_code": response.status_code}
        except Exception as e:
            return {"error": f"Request Error: {str(e)}"}