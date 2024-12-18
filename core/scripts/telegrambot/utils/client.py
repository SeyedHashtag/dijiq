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
import qrcode
import io
from utils.admin_support import get_support_text

# Initialize payment processor
payment_processor = CryptomusPayment()

# Store payment sessions
payment_sessions = {}

@bot.message_handler(func=lambda message: message.text == '📱 My Configs')
def show_my_configs(message):
    command = f"python3 {CLI_PATH} list-users"
    result = run_cli_command(command)
    
    try:
        users = json.loads(result)
        found = False
        
        for username, details in users.items():
            # Check if config belongs to user and is not blocked
            if username.startswith(f"{message.from_user.id}d") and not details.get('blocked', False):
                found = True
                
                # Get IPv4 config and clean up the warning message
                command = f"python3 {CLI_PATH} show-user-uri -u {username} -ip 4"
                config_v4 = run_cli_command(command)
                # Remove the warning message and clean up the text
                config_v4 = config_v4.replace("Warning: IP4 or IP6 is not set in configs.env. Fetching from ip.gs...\n", "")
                config_v4 = config_v4.replace("IPv4:\n", "").strip()
                
                # Create QR code
                qr = qrcode.make(config_v4)
                bio = io.BytesIO()
                qr.save(bio, 'PNG')
                bio.seek(0)
                
                # Format message with the exact style requested
                caption = (
                    f"📱 Config: {username}\n"
                    f"📊 Traffic: {details.get('used_download_bytes', 0) / (1024**3):.2f}/{details.get('max_download_bytes', 0) / (1024**3):.2f} GB\n"
                    f"📅 Days: {details.get('remaining_days', 0)}/{details.get('expiration_days', 0)}\n\n"
                    f"📝 Config Text:\n"
                    f"`{config_v4}`"
                )
                
                bot.send_photo(
                    message.chat.id,
                    photo=bio,
                    caption=caption,
                    parse_mode="Markdown"
                )
        
        if not found:
            bot.reply_to(message, "You don't have any active configs. Use the Purchase Plan option to get started!")
            
    except json.JSONDecodeError:
        bot.reply_to(message, "Error retrieving configs. Please try again later.")

def send_new_config(chat_id, username, plan_gb, plan_days, result_text):
    try:
        # Get IPv4 config
        command = f"python3 {CLI_PATH} show-user-uri -u {username} -ip 4"
        config_v4 = run_cli_command(command).replace("IPv4:\n", "").strip()
        
        # Create QR code
        qr = qrcode.make(config_v4)
        bio = io.BytesIO()
        qr.save(bio, 'PNG')
        bio.seek(0)
        
        # Format caption with the exact style requested
        caption = (
            f"📱 Config: {username}\n"
            f"📊 Traffic: 0.00/{plan_gb:.2f} GB\n"
            f"📅 Days: 0/{plan_days}\n\n"
            f"📝 Config Text:\n"
            f"`{config_v4}`"
        )
        
        bot.send_photo(
            chat_id,
            photo=bio,
            caption=caption,
            parse_mode="Markdown",
            reply_markup=create_main_markup(is_admin=False)
        )
    except Exception as e:
        bot.send_message(chat_id, f"Error generating config QR code: {str(e)}")

def check_payment_status(payment_id, chat_id, plan_gb):
    while True:
        status = payment_processor.check_payment_status(payment_id)
        
        # First check if there's an error in the response
        if "error" in status:
            bot.send_message(
                chat_id,
                f"❌ Error checking payment status: {status['error']}\nPlease contact support."
            )
            del payment_sessions[payment_id]
            break

        # Check if we have a valid result
        if not status or 'result' not in status:
            bot.send_message(
                chat_id,
                "❌ Invalid payment status response. Please contact support."
            )
            del payment_sessions[payment_id]
            break

        result = status['result']
        payment_status = result.get('status', '')
        
        try:
            amount_paid = float(result.get('amount_paid_usd', 0))
            amount_required = float(result.get('amount_usd', 0))
        except (ValueError, TypeError):
            amount_paid = 0
            amount_required = 0

        # Check payment status
        if payment_status == 'paid':
            if amount_paid < amount_required:
                # Underpaid
                bot.send_message(
                    chat_id,
                    f"⚠️ Payment underpaid (${amount_paid:.2f} of ${amount_required:.2f})\n"
                    "Please contact support."
                )
                update_payment_status(payment_id, 'underpaid')
                del payment_sessions[payment_id]
                break
            elif amount_paid > amount_required:
                # Overpaid but process anyway
                plans = load_plans()
                plan_days = plans[str(plan_gb)]['days']
                
                timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                username = f"{chat_id}d{timestamp}"
                
                command = f"python3 {CLI_PATH} add-user -u {username} -t {plan_gb} -e {plan_days}"
                result = run_cli_command(command)
                
                update_payment_status(payment_id, 'completed_overpaid')
                send_new_config(chat_id, username, plan_gb, plan_days, result)
                
                bot.send_message(
                    chat_id,
                    f"⚠️ Note: Payment was overpaid (${amount_paid:.2f} of ${amount_required:.2f})\n"
                    "Please contact support for a refund."
                )
                
                del payment_sessions[payment_id]
                break
            else:
                # Exact payment
                plans = load_plans()
                plan_days = plans[str(plan_gb)]['days']
                
                timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                username = f"{chat_id}d{timestamp}"
                
                command = f"python3 {CLI_PATH} add-user -u {username} -t {plan_gb} -e {plan_days}"
                result = run_cli_command(command)
                
                update_payment_status(payment_id, 'completed')
                send_new_config(chat_id, username, plan_gb, plan_days, result)
                
                del payment_sessions[payment_id]
                break
            
        elif payment_status == 'expired':
            # Payment expired
            bot.send_message(
                chat_id,
                "❌ Payment session expired. Please try again."
            )
            update_payment_status(payment_id, 'expired')
            del payment_sessions[payment_id]
            break
            
        # If still pending, wait and check again
        time.sleep(30)

@bot.message_handler(func=lambda message: message.text == '💰 Purchase Plan')
def show_purchase_options(message):
    bot.reply_to(
        message,
        "Select a plan to purchase:",
        reply_markup=create_purchase_markup()
    )

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
    markup = create_downloads_markup()  # Get the markup first
    bot.reply_to(
        message,
        "Download our apps:",
        reply_markup=markup
    )

@bot.message_handler(func=lambda message: message.text == '📞 Support')
def show_support(message):
    bot.reply_to(message, get_support_text()) 
