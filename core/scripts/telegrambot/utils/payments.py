import base64
import json
import uuid
import re
from hashlib import md5
import requests
import os
from dotenv import load_dotenv

load_dotenv()


class CryptomusPayment:
    def __init__(self):
        # support both HELEKET and legacy CRYPTOMUS env names
        self.merchant_id = os.getenv('HELEKET_MERCHANT_ID')
        self.payment_api_key = os.getenv('HELEKET_API_KEY')
        self.base_url = "https://api.heleket.com/v1/payment"

    def _check_credentials(self):
        return bool(self.merchant_id and self.payment_api_key)

    def _generate_sign(self, payload):
        # Use deterministic JSON encoding for consistent signatures
        json_str = json.dumps(payload, separators=(',', ':'), sort_keys=True)
        encoded_data = base64.b64encode(json_str.encode("utf-8")).decode("utf-8")
        return md5(f"{encoded_data}{self.payment_api_key}".encode("utf-8")).hexdigest()

    def create_payment(self, amount, plan_gb, user_id, currency="USD", network=None, to_currency=None, url_return=None, url_success=None, url_callback=None, is_payment_multiple=True, lifetime=3600, additional_data=None, subtract=None, accuracy_payment_percent=None, currencies=None, except_currencies=None, course_source=None, from_referral_code=None, discount_percent=None, is_refresh=False, order_id=None):
        if not self._check_credentials():
            return {"error": "Payment credentials not configured"}

        # If merchant supplies an order_id, validate it; otherwise generate one
        if order_id:
            if not (1 <= len(order_id) <= 128) or not re.match(r'^[A-Za-z0-9_-]+$', order_id):
                return {"error": "order_id must be 1-128 chars and contain only letters, numbers, underscores or dashes"}
            payment_order_id = order_id
        else:
            payment_order_id = str(uuid.uuid4())

        payload = {
            "amount": str(amount),
            "currency": currency,
            "order_id": payment_order_id,
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
        # include some internal metadata in additional_data (string, max 255 chars)
        additional_data.update({
            "plan_gb": plan_gb,
            "payment_id": payment_order_id,
            "user_id": user_id
        })
        payload["additional_data"] = json.dumps(additional_data)

        try:
            headers = {
                "merchant": self.merchant_id,
                "sign": self._generate_sign(payload),
                "Content-Type": "application/json"
            }

            response = requests.post(self.base_url, json=payload, headers=headers)

            # treat any 2xx as success, attempt to return structured JSON on errors too
            if response.ok:
                return response.json()
            try:
                return response.json()
            except Exception:
                return {"error": f"API Error: {response.text}"}
        except Exception as e:
            return {"error": f"Request Error: {str(e)}"}

    def check_payment_status(self, payment_id):
        if not self._check_credentials():
            return {"error": "Payment credentials not configured"}

        payload = {"uuid": payment_id}

        try:
            headers = {
                "merchant": self.merchant_id,
                "sign": self._generate_sign(payload),
                "Content-Type": "application/json"
            }

            # fix duplicate 'payment' segment: /v1/payment/info
            response = requests.post(f"{self.base_url}/info", json=payload, headers=headers)

            if response.ok:
                return response.json()
            try:
                return response.json()
            except Exception:
                return {"error": f"API Error: {response.text}"}
        except Exception as e:
            return {"error": f"Request Error: {str(e)}"}