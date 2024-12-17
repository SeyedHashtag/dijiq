from telebot import types
from utils.command import *
from utils.common import create_main_markup, create_purchase_markup, create_downloads_markup
from utils.payments import CryptomusPayment
from utils.admin_plans import load_plans
from datetime import datetime
from utils.payment_records import add_payment_record, update_payment_status
from utils.spam_protection import spam_protection
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
    if not spam_protection.can_send_message(message.from_user.id):
        bot.reply_to(message, "⚠️ You are sending messages too quickly. Please wait a moment and try again.")
        return

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
                config_v4 = config_v4.replace("Warning: IP4 or IP6 is not set in configs.env. Fetching from ip.gs...\n", "")
                config_v4 = config_v4.replace("IPv4:\n", "").strip()
                
                # Create QR code
                qr = qrcode.make(config_v4)
                bio = io.BytesIO()
                qr.save(bio, 'PNG')
                bio.seek(0)
                
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
        
        if "error" in status:
            bot.send_message(chat_id, f"❌ Error checking payment status: {status['error']}\nPlease contact support.")
            spam_protection.remove_payment_link(chat_id, payment_id)
            del payment_sessions[payment_id]
            break

        if not status or 'result' not in status:
            bot.send_message(chat_id, "❌ Invalid payment status response. Please contact support.")
            spam_protection.remove_payment_link(chat_id, payment_id)
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

        if payment_status == 'paid':
            if amount_paid < amount_required:
                bot.send_message(
                    chat_id,
                    f"⚠️ Payment underpaid (${amount_paid:.2f} of ${amount_required:.2f})\n"
                    "Please contact support."
                )
                update_payment_status(payment_id, 'underpaid')
            elif amount_paid > amount_required:
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
            else:
                plans = load_plans()
                plan_days = plans[str(plan_gb)]['days']
                timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                username = f"{chat_id}d{timestamp}"
                command = f"python3 {CLI_PATH} add-user -u {username} -t {plan_gb} -e {plan_days}"
                result = run_cli_command(command)
                update_payment_status(payment_id, 'completed')
                send_new_config(chat_id, username, plan_gb, plan_days, result)
            
            spam_protection.remove_payment_link(chat_id, payment_id)
            del payment_sessions[payment_id]
            break
            
        elif payment_status == 'expired':
            bot.send_message(chat_id, "❌ Payment session expired. Please try again.")
            update_payment_status(payment_id, 'expired')
            spam_protection.remove_payment_link(chat_id, payment_id)
            del payment_sessions[payment_id]
            break
            
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
    if not spam_protection.can_send_message(call.from_user.id):
        bot.answer_callback_query(call.id, "⚠️ You are sending messages too quickly. Please wait a moment and try again.")
        return

    if not spam_protection.can_create_payment(call.from_user.id):
        bot.answer_callback_query(call.id)
        bot.edit_message_text(
            "⚠️ You have too many active payment links. Please wait for them to expire or complete existing payments.",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id
        )
        return

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
        
        update_payment_status(payment_id, 'completed')
        send_new_config(call.message.chat.id, username, plan_gb, plan_days, result)
        return

    # Normal payment flow
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
    
    # Add payment link to spam protection
    spam_protection.add_payment_link(call.message.chat.id, payment_id)
    
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
    if not spam_protection.can_send_message(message.from_user.id):
        bot.reply_to(message, "⚠️ You are sending messages too quickly. Please wait a moment and try again.")
        return

    markup = create_downloads_markup()
    bot.reply_to(message, "Download our apps:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == '📞 Support')
def show_support(message):
    if not spam_protection.can_send_message(message.from_user.id):
        bot.reply_to(message, "⚠️ You are sending messages too quickly. Please wait a moment and try again.")
        return

    bot.reply_to(message, get_support_text())
