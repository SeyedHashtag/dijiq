import base64
import json
import uuid
import asyncio
from hashlib import md5
import aiohttp
from utils.command import bot
from utils.language import get_text, get_user_language
from utils.plans import PLANS
from utils.client_manager import create_client_config, load_clients, save_clients
from datetime import datetime
from utils.payment_tracking import track_payment_request

# Load these from environment variables
MERCHANT_ID = "YOUR-MERCHANT-ID"
PAYMENT_API_KEY = "YOUR-API-KEY"

class PaymentManager:
    def __init__(self):
        self.base_url = "https://api.cryptomus.com/v1"
        self.headers = {
            "merchant": MERCHANT_ID,
        }
        
    def _get_signature(self, payload):
        encoded_data = base64.b64encode(
            json.dumps(payload).encode("utf-8")
        ).decode("utf-8")
        return md5(f"{encoded_data}{PAYMENT_API_KEY}".encode("utf-8")).hexdigest()
    
    async def create_payment(self, amount, currency="USDT", order_id=None):
        if not order_id:
            order_id = str(uuid.uuid4())
            
        payload = {
            "amount": str(amount),
            "currency": currency,
            "order_id": order_id,
            "network": "tron",  # You can change this or make it configurable
        }
        
        headers = self.headers.copy()
        headers["sign"] = self._get_signature(payload)
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/payment",
                headers=headers,
                json=payload
            ) as response:
                if response.status != 200:
                    raise ValueError(f"Payment creation failed: {await response.text()}")
                return await response.json()
    
    async def check_payment_status(self, payment_id):
        payload = {"uuid": payment_id}
        headers = self.headers.copy()
        headers["sign"] = self._get_signature(payload)
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/payment/info",
                headers=headers,
                json=payload
            ) as response:
                if response.status != 200:
                    return None
                result = await response.json()
                return result.get("result", {}).get("payment_status")

payment_manager = PaymentManager()

async def process_payment(call, plan_id):
    """Process payment for a specific plan"""
    plan = PLANS.get(plan_id)
    if not plan:
        await bot.answer_callback_query(call.id, "Invalid plan selected")
        return
        
    try:
        # Create payment
        payment_result = await payment_manager.create_payment(plan["price"])
        payment_url = payment_result["result"]["url"]
        payment_id = payment_result["result"]["uuid"]
        
        # Track payment request
        track_payment_request(call.message.chat.id, plan_id, payment_id)
        
        # Send payment link
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("💳 Pay Now", url=payment_url),
            types.InlineKeyboardButton("🔄 Check Payment", callback_data=f"check_payment:{payment_id}")
        )
        
        await bot.edit_message_reply_markup(
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup
        )
        
        # Start payment checking task
        asyncio.create_task(check_payment_loop(call.message, payment_id, plan))
        
        language = get_user_language(call.from_user.id)
        success_msg = get_text(language, "payment_success")
        await bot.send_message(call.message.chat.id, success_msg)
        
    except Exception as e:
        failed_msg = get_text(language, "payment_failed").format(error=str(e))
        await bot.send_message(call.message.chat.id, failed_msg)

async def check_payment_loop(message, payment_id, plan):
    """Check payment status in a loop"""
    check_count = 0
    max_checks = 60  # 10 minutes maximum
    
    while check_count < max_checks:
        try:
            status = await payment_manager.check_payment_status(payment_id)
            
            if status in ("paid", "paid_over"):
                await bot.send_message(
                    message.chat.id,
                    f"Payment successful! Creating your {plan['traffic']}GB account..."
                )
                create_client_config(message, plan, payment_id, status)
                break
                
            elif status in ("failed", "expired"):
                # Store failed payment info
                clients = load_clients()
                user_id = str(message.chat.id)
                
                if user_id not in clients:
                    clients[user_id] = []
                
                clients[user_id].append({
                    'payment': {
                        'id': payment_id,
                        'status': status,
                        'amount': plan['price'],
                        'currency': 'USDT',
                        'timestamp': datetime.now().isoformat()
                    },
                    'plan': {
                        'name': plan['name'],
                        'traffic': plan['traffic'],
                        'days': plan['days'],
                        'price': plan['price']
                    }
                })
                save_clients(clients)
                
                await bot.send_message(
                    message.chat.id,
                    "Payment failed or expired. Please try again."
                )
                break
                
        except Exception as e:
            print(f"Payment check error: {e}")
            
        await asyncio.sleep(10)
        check_count += 1
