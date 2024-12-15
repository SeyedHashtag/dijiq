import os
from telebot import types
from utils.command import bot, is_admin
from utils.language import get_text, get_user_language
from utils.payments import PaymentManager
from dotenv import load_dotenv, set_key

def create_payment_settings_markup():
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = [
        types.InlineKeyboardButton("🏢 Set Merchant ID", callback_data="set_merchant"),
        types.InlineKeyboardButton("🔑 Set API Key", callback_data="set_api_key"),
        types.InlineKeyboardButton("💱 Test System", callback_data="test_payment"),
    ]
    markup.add(*buttons)
    return markup

@bot.message_handler(func=lambda message: is_admin(message.from_user.id) and message.text == '💳 Payment Settings')
def payment_settings(message):
    language = get_user_language(message.from_user.id)
    merchant_id = os.getenv('CRYPTOMUS_MERCHANT_ID', 'Not set')
    api_key = os.getenv('CRYPTOMUS_API_KEY', 'Not set')
    if api_key != 'Not set':
        api_key = api_key[:6] + '...' + api_key[-4:]  # Mask the API key
    
    settings_text = get_text(language, "current_payment_settings").format(
        merchant_id=merchant_id,
        api_key=api_key,
        currency="USDT",
        network="TRON",
        status="✅ Configured" if merchant_id != 'Not set' and api_key != 'Not set' else "❌ Not Configured"
    )
    
    markup = create_payment_settings_markup()
    bot.reply_to(message, settings_text, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data in ["set_merchant", "set_api_key", "test_payment"])
def handle_payment_settings(call):
    if not is_admin(call.from_user.id):
        return
        
    action = call.data
    if action == "set_merchant":
        msg = bot.send_message(call.message.chat.id, get_text(get_user_language(call.from_user.id), "enter_merchant_id"))
        bot.register_next_step_handler(msg, process_merchant_id)
    elif action == "set_api_key":
        msg = bot.send_message(call.message.chat.id, get_text(get_user_language(call.from_user.id), "enter_api_key"))
        bot.register_next_step_handler(msg, process_api_key)
    elif action == "test_payment":
        test_payment_system(call.message)

def process_merchant_id(message):
    if not is_admin(message.from_user.id):
        return
        
    merchant_id = message.text.strip()
    env_file = '.env'
    set_key(env_file, 'CRYPTOMUS_MERCHANT_ID', merchant_id)
    os.environ['CRYPTOMUS_MERCHANT_ID'] = merchant_id
    
    bot.reply_to(message, get_text(get_user_language(message.from_user.id), "settings_updated"))
    payment_settings(message)

def process_api_key(message):
    if not is_admin(message.from_user.id):
        return
        
    api_key = message.text.strip()
    env_file = '.env'
    set_key(env_file, 'CRYPTOMUS_API_KEY', api_key)
    os.environ['CRYPTOMUS_API_KEY'] = api_key
    
    # Delete the message containing the API key for security
    bot.delete_message(message.chat.id, message.message_id)
    
    bot.send_message(message.chat.id, get_text(get_user_language(message.from_user.id), "settings_updated"))
    payment_settings(message)

async def test_payment_system(message):
    try:
        # Create a test payment for $0.01
        payment_manager = PaymentManager()
        result = await payment_manager.create_payment(0.01)
        if result and 'result' in result:
            bot.reply_to(message, get_text(get_user_language(message.from_user.id), "test_success"))
        else:
            bot.reply_to(
                message,
                get_text(get_user_language(message.from_user.id), "test_failed").format(error="Invalid response")
            )
    except Exception as e:
        bot.reply_to(
            message,
            get_text(get_user_language(message.from_user.id), "test_failed").format(error=str(e))
        )
