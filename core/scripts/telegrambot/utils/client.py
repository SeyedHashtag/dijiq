from telebot import types
from utils.command import *
from utils.common import create_main_markup, create_purchase_markup, create_downloads_markup
from utils.payments import create_invoice, check_invoice_paid
import asyncio
import uuid

@bot.message_handler(func=lambda message: message.text == '📱 My Configs')
def show_my_configs(message):
    user_id = str(message.from_user.id)
    command = f"python3 {CLI_PATH} list-users"
    result = run_cli_command(command)
    
    try:
        users = json.loads(result)
        user_configs = []
        
        for username, details in users.items():
            # Assuming you store telegram_id in user details
            if details.get('telegram_id') == user_id:
                user_configs.append({
                    'username': username,
                    'traffic': details['max_download_bytes'] / (1024 ** 3),
                    'days': details['expiration_days']
                })
        
        if not user_configs:
            bot.reply_to(message, "You don't have any active configs. Use the Purchase Plan option to get started!")
            return
            
        for config in user_configs:
            text = (
                f"📱 Config: {config['username']}\n"
                f"📊 Traffic: {config['traffic']:.2f} GB\n"
                f"📅 Days: {config['days']}"
            )
            bot.reply_to(message, text)
            
    except json.JSONDecodeError:
        bot.reply_to(message, "Error retrieving configs. Please try again later.")

@bot.message_handler(func=lambda message: message.text == '💰 Purchase Plan')
def show_purchase_options(message):
    bot.reply_to(
        message,
        "Select a plan to purchase:",
        reply_markup=create_purchase_markup()
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('purchase:'))
async def handle_purchase(call):
    plan_gb = int(call.data.split(':')[1])
    
    # Set price based on plan
    prices = {
        30: 1.80,
        60: 3.00,
        100: 4.20
    }
    amount = prices.get(plan_gb)
    
    if not amount:
        await bot.answer_callback_query(call.id, "Invalid plan selected")
        return

    try:
        # Create payment
        invoice_data = await create_invoice(
            url="https://api.cryptomus.com/v1/payment",
            invoice_data={
                "amount": str(amount),
                "currency": "USD",
                "id": str(uuid.uuid4()),
            },
        )

        if not invoice_data or 'result' not in invoice_data:
            await bot.reply_to(
                call.message,
                "❌ Failed to create payment. Please try again later or contact support.",
                reply_markup=create_main_markup(is_admin=False)
            )
            return

        payment_id = invoice_data['result']['uuid']
        payment_url = invoice_data['result']['url']

        # Start payment checking task
        asyncio.create_task(check_invoice_paid(
            payment_id, 
            bot, 
            call.message.chat.id, 
            plan_gb
        ))

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("💳 Pay Now", url=payment_url))
        
        await bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=(
                f"💰 Payment for {plan_gb}GB Plan\n\n"
                f"Amount: ${amount:.2f}\n"
                f"Payment ID: {payment_id}\n\n"
                "Click the button below to proceed with payment.\n"
                "The config will be created automatically after payment is confirmed."
            ),
            reply_markup=markup
        )

    except Exception as e:
        print(f"Error creating payment: {e}")
        await bot.reply_to(
            call.message,
            "❌ An error occurred. Please try again later or contact support.",
            reply_markup=create_main_markup(is_admin=False)
        )

@bot.message_handler(func=lambda message: message.text == '⬇️ Downloads')
def show_downloads(message):
    bot.reply_to(
        message,
        "Download our apps:",
        reply_markup=create_downloads_markup()
    )

@bot.message_handler(func=lambda message: message.text == '📞 Support')
def show_support(message):
    support_text = (
        "Need help? Contact our support:\n\n"
        "📱 Telegram: @your_support_username\n"
        "📧 Email: support@yourdomain.com\n"
        "⏰ Working hours: 24/7"
    )
    bot.reply_to(message, support_text) 
