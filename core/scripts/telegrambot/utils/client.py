from telebot import types
from utils.command import *
from utils.common import create_main_markup, create_purchase_markup, create_downloads_markup
from utils.payments import CryptomusPayment
from utils.admin_plans import load_plans
from datetime import datetime
from utils.payment_records import add_payment_record, update_payment_status
import threading
import time
from utils.test_mode import load_test_mode

# Initialize payment processor
payment_processor = CryptomusPayment()

# Store payment sessions
payment_sessions = {}

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

def check_payment_status(payment_id, chat_id, plan_gb):
    while True:
        status = payment_processor.check_payment_status(payment_id)
        if status and status['result']['payment_status'] in ('paid', 'paid_over'):
            try:
                # Load plan details
                plans = load_plans()
                plan_days = plans[str(plan_gb)]['days']
                
                # Create username using telegram ID and timestamp
                timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                username = f"{chat_id}d{timestamp}"
                
                # Convert GB to bytes (ensure plan_gb is int)
                traffic_bytes = int(plan_gb) * 1024 * 1024 * 1024
                
                # Create user config with bytes
                command = f"python3 {CLI_PATH} add-user -u {username} -t {traffic_bytes} -e {plan_days} -tid {chat_id}"
                print(f"DEBUG: Running command: {command}")  # Debug print
                result = run_cli_command(command)
                
                # Update payment record
                update_payment_status(payment_id, 'completed')
                
                # Extract config from result
                config_text = extract_config_from_result(result)
                
                bot.send_message(
                    chat_id,
                    f"✅ Payment received! Your config has been created.\n\n"
                    f"Username: {username}\n"
                    f"Traffic: {plan_gb}GB\n"
                    f"Duration: {plan_days} days\n\n"
                    f"Config:\n{config_text}"
                )
            except Exception as e:
                print(f"DEBUG: Error in config creation: {str(e)}")  # Debug print
                bot.send_message(
                    chat_id,
                    "❌ Error creating config. Please contact support."
                )
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
    # Add logic to extract config from CLI result
    # This depends on your CLI output format
    return result

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
        try:
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
            
            # Convert GB to bytes (ensure plan_gb is int)
            traffic_bytes = int(plan_gb) * 1024 * 1024 * 1024
            
            command = f"python3 {CLI_PATH} add-user -u {username} -t {traffic_bytes} -e {plan_days} -tid {call.message.chat.id}"
            print(f"DEBUG: Running command: {command}")  # Debug print
            result = run_cli_command(command)
            
            # Update payment record
            update_payment_status(payment_id, 'completed')
            
            # Extract config from result
            config_text = extract_config_from_result(result)
            
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
        except Exception as e:
            print(f"DEBUG: Error in test mode config creation: {str(e)}")  # Debug print
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="❌ Error creating config. Please contact support."
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
