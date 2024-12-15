import asyncio
import base64
import json
import uuid
from hashlib import md5
import aiohttp
import os
from dotenv import load_dotenv
import time

load_dotenv()

async def create_invoice(url: str, invoice_data: dict):
    encoded_data = base64.b64encode(
        json.dumps(invoice_data).encode("utf-8")
    ).decode("utf-8")

    async with aiohttp.ClientSession(headers={
        "merchant": os.getenv('CRYPTOMUS_MERCHANT_ID'),
        "sign": md5(f"{encoded_data}{os.getenv('CRYPTOMUS_API_KEY')}".encode("utf-8")).hexdigest(),
    }) as session:
        async with session.post(url=url, json=invoice_data) as response:
            if not response.ok:
                raise ValueError(await response.json())
            
            return await response.json()

async def check_invoice_paid(payment_id: str, bot, chat_id: int, plan_gb: int):
    while True:
        try:
            invoice_data = await create_invoice(
                url="https://api.cryptomus.com/v1/payment/info",
                invoice_data={"uuid": payment_id},
            )

            if invoice_data['result']['payment_status'] in ('paid', 'paid_over'):
                username = f"user_{chat_id}_{int(time.time())}"
                command = f"python3 {CLI_PATH} add-user -u {username} -t {plan_gb} -e 30 -tid {chat_id}"
                result = run_cli_command(command)
                await bot.send_message(chat_id, f"✅ Payment received! Your config has been created.\n\n{result}")
                break
            else:
                print(f"Payment {payment_id} not paid yet")

        except Exception as e:
            print(f"Error checking payment status: {e}")
            
        await asyncio.sleep(30) 
