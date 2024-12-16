from telebot import types
from utils.command import *
from utils.common import create_main_markup, create_purchase_markup, create_downloads_markup
from utils.payments import CryptomusPayment
from utils.admin_plans import load_plans
from datetime import datetime
import qrcode
import io
import base64
from utils.payment_records import add_payment_record, update_payment_status
import threading
import time
from utils.test_mode import load_test_mode

# Initialize payment processor
payment_processor = CryptomusPayment()

# Store payment sessions
payment_sessions = {}

def format_bytes(bytes_value):
    gb = bytes_value / (1024 ** 3)
    return f"{gb:.2f}"

def create_config_qr(config_text):
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(config_text)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert image to bytes
    bio = io.BytesIO()
    img.save(bio, format='PNG')
    bio.seek(0)
    return bio

@bot.message_handler(func=lambda message: message.text == '📱 My Configs')
def show_my_configs(message):
    user_id = str(message.from_user.id)
    command = f"python3 {CLI_PATH} list-users"
    result = run_cli_command(command)
    
    try:
        users = json.loads(result)
        user_configs = []
        
        for username, details in users.items():
            if username.startswith(f"{user_id}d"):
                used_traffic = details.get('used_download_bytes', 0) + details.get('used_upload_bytes', 0)
                max_traffic = details.get('max_download_bytes', 0)
                remaining_days = details.get('remaining_days', 0)
                total_days = details.get('expiration_days', 0)
                
                user_configs.append({
                    'username': username,
                    'used_traffic': format_bytes(used_traffic),
                    'max_traffic': format_bytes(max_traffic),
                    'remaining_days': remaining_days,
                    'total_days': total_days,
                    'config': details.get('config', '')
                })
        
        if not user_configs:
            bot.reply_to(message, "You don't have any active configs. Use the Purchase Plan option to get started!")
            return
            
        for config in user_configs:
            text = (
                f"📱 Config: {config['username']}\n"
                f"📊 Traffic: {config['used_traffic']}/{config['max_traffic']} GB\n"
                f"📅 Days: {config['remaining_days']}/{config['total_days']}\n\n"
                f"📝 Config Text:\n{config['config']}"
            )
            
            # Create and send QR code
            if config['config']:
                qr_bio = create_config_qr(config['config'])
                bot.send_photo(
                    message.chat.id,
                    qr_bio,
                    caption=text,
                    reply_markup=create_main_markup(is_admin=False)
                )
            else:
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

def check_payment_status(payment_id, chat_id, plan_gb):
    while True:
        status = payment_processor.check_payment_status(payment_id)
        if status and status['result']['payment_status'] in ('paid', 'paid_over'):
            # Load plan details
            plans = load_plans()
            plan_days = plans[str(plan_gb)]['days']
            
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            username = f"{chat_id}d{timestamp}"
            
            command = f"python3 {CLI_PATH} add-user -u {username} -t {plan_gb} -e {plan_days}"
            result = run_cli_command(command)
            
            update_payment_status(payment_id, 'completed')
            config_text = extract_config_from_result(result)
            send_config_to_user(chat_id, username, plan_gb, plan_days, config_text)
            
            del payment_sessions[payment_id]
            break
        elif status and status['result']['payment_status'] == 'expired':
            update_payment_status(payment_id, 'expired')
            bot.send_message(
                chat_id,
                "❌ Payment session expired. Please try again."
            )
            del payment_sessions[payment_id]
            break
        time.sleep(30)

def extract_config_from_result(result):
    try:
        # Parse the JSON result
        data = json.loads(result)
        # Return the config string
        return data.get('config', '')
    except:
        return result

def send_config_to_user(chat_id, username, plan_gb, plan_days, config_text):
    # Create message text
    message_text = (
        f"✅ Config created successfully!\n\n"
        f"Username: {username}\n"
        f"Traffic: {plan_gb}GB\n"
        f"Duration: {plan_days} days\n\n"
        f"📝 Config Text:\n{config_text}"
    )
    
    # Create and send QR code with config
    if config_text:
        qr_bio = create_config_qr(config_text)
        bot.send_photo(
            chat_id,
            qr_bio,
            caption=message_text,
            reply_markup=create_main_markup(is_admin=False)
        )
    else:
        bot.send_message(chat_id, message_text)

@bot.callback_query_handler(func=lambda call: call.data.startswith('purchase:'))
def handle_purchase(call):
    plan_gb = int(call.data.split(':')[1])
    
    # Load plans from file
    plans = load_plans()
    
    if str(plan_gb) not in plans:
        bot.answer_callback_query(call.id, "Invalid plan selected")
        return

    amount = plans[str(plan_gb)]['price']
    
    # Check if test mode is enabled
    if load_test_mode():
        # Create test payment record
        payment_id = f"test_{int(time.time())}"
        payment_record = {
            'user_id': call.message.chat.id,
            'plan_gb': plan_gb,
            'amount': amount,
            'status': 'test_mode',
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'payment_url': 'N/A',
            'is_test': True
        }
        add_payment_record(payment_id, payment_record)
        
        # Create user config immediately
        plan_days = plans[str(plan_gb)]['days']
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        username = f"{call.message.chat.id}d{timestamp}"
        
        command = f"python3 {CLI_PATH} add-user -u {username} -t {plan_gb} -e {plan_days}"
        result = run_cli_command(command)
        
        # Update payment record
        update_payment_status(payment_id, 'completed')
        
        # Extract config from result
        config_text = extract_config_from_result(result)
        send_config_to_user(call.message.chat.id, username, plan_gb, plan_days, config_text)
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=(
                "✅ Test Mode: Config created successfully!\n\n"
                f"Username: {username}\n"
                f"Traffic: {plan_gb}GB\n"
                f"Duration: {plan_days} days\n\n"
                f"Config:\n{config_text}"
            )
        )
        return
    
    # Normal payment flow continues here...
    payment = payment_processor.create_payment(amount, plan_gb)
    
    if "error" in payment:
        error_message = payment["error"]
        if "credentials not configured" in error_message:
            bot.reply_to(
                call.message,
                "❌ Payment system is not configured yet. Please contact support.",
                reply_markup=create_main_markup(is_admin=False)
            )
        else:
            bot.reply_to(
                call.message,
                f"❌ Payment Error: {error_message}\nPlease try again later or contact support.",
                reply_markup=create_main_markup(is_admin=False)
            )
        return

    if not payment or 'result' not in payment:
        bot.reply_to(
            call.message,
            "❌ Failed to create payment. Please try again later or contact support.",
            reply_markup=create_main_markup(is_admin=False)
        )
        return

    payment_id = payment['result']['uuid']
    payment_url = payment['result']['url']
    
    # Store payment session
    payment_sessions[payment_id] = {
        'chat_id': call.message.chat.id,
        'plan_gb': plan_gb
    }
    
    # Record payment information
    payment_record = {
        'user_id': call.message.chat.id,
        'plan_gb': plan_gb,
        'amount': amount,
        'status': 'pending',
        'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'payment_url': payment_url
    }
    add_payment_record(payment_id, payment_record)
    
    # Start payment checking thread
    threading.Thread(
        target=check_payment_status,
        args=(payment_id, call.message.chat.id, plan_gb)
    ).start()

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💳 Pay Now", url=payment_url))
    
    bot.edit_message_text(
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
