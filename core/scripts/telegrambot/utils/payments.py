import base64
import json
import uuid
import hashlib
import aiohttp
import os
from dotenv import load_dotenv
import asyncio
import logging
import time

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_payment_settings():
    """Load payment settings from environment variables."""
    load_dotenv()
    return {
        'enabled': bool(os.getenv('CRYPTOMUS_MERCHANT_ID') and os.getenv('CRYPTOMUS_API_KEY')),
        'merchant_id': os.getenv('CRYPTOMUS_MERCHANT_ID'),
        'payment_key': os.getenv('CRYPTOMUS_API_KEY')
    }

async def create_payment(amount: float, plan_gb: int) -> dict:
    """Create a new payment in Cryptomus."""
    settings = load_payment_settings()
    if not settings['enabled']:
        return None

    order_id = str(uuid.uuid4())
    invoice_data = {
        "amount": str(amount),
        "currency": "USD",
        "order_id": order_id,
        "url_return": "https://t.me/your_bot_username",
        "is_payment_multiple": False,
        "additional_data": json.dumps({
            "plan_gb": plan_gb,
            "payment_id": order_id
        })
    }

    encoded_data = base64.b64encode(
        json.dumps(invoice_data).encode("utf-8")
    ).decode("utf-8")

    headers = {
        "merchant": settings['merchant_id'],
        "sign": hashlib.md5(
            f"{encoded_data}{settings['payment_key']}".encode("utf-8")
        ).hexdigest(),
    }

    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.post(
                url="https://api.cryptomus.com/v1/payment",
                json=invoice_data
            ) as response:
                if response.status == 200:
                    logger.info(f"Created payment with Order ID: {order_id} for amount: ${amount}")
                    return await response.json()
    except Exception as e:
        logger.error(f"Error creating payment: {e}")
    return None

async def check_payment_status(payment_id: str, chat_id: int, plan_gb: int) -> None:
    """Check payment status and create config when paid."""
    settings = load_payment_settings()
    if not settings['enabled']:
        return

    invoice_data = {"uuid": payment_id}
    encoded_data = base64.b64encode(
        json.dumps(invoice_data).encode("utf-8")
    ).decode("utf-8")

    headers = {
        "merchant": settings['merchant_id'],
        "sign": hashlib.md5(
            f"{encoded_data}{settings['payment_key']}".encode("utf-8")
        ).hexdigest(),
    }

    logger.info(f"Starting payment status check for Payment ID: {payment_id}")

    while True:
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.post(
                    url="https://api.cryptomus.com/v1/payment/info",
                    json=invoice_data
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        if result['result']['payment_status'] in ('paid', 'paid_over'):
                            # Create user config after successful payment
                            username = f"user_{chat_id}_{int(time.time())}"
                            command = f"python3 {CLI_PATH} add-user -u {username} -t {plan_gb} -e 30 -tid {chat_id}"
                            result = run_cli_command(command)
                            
                            # Send success message through bot
                            await bot.send_message(
                                chat_id,
                                f"✅ Payment received! Your config has been created.\n\n{result}"
                            )
                            return
                        elif result['result']['payment_status'] == 'expired':
                            await bot.send_message(
                                chat_id,
                                "❌ Payment session expired. Please try again."
                            )
                            return
        except Exception as e:
            logger.error(f"Error checking payment status: {e}")
        
        await asyncio.sleep(10) 
