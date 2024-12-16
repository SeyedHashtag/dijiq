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
from utils.languages import get_user_language, get_text
import json
from io import BytesIO

# Initialize payment processor
payment_processor = CryptomusPayment()

# Store payment sessions
payment_sessions = {}

def get_user_configs(user_id):
    command = f"python3 {CLI_PATH} list-users"
    result = run_cli_command(command)
    
    try:
        users = json.loads(result)
        user_configs = []
        
        for username, details in users.items():
            if username.startswith(str(user_id)):
                if not details.get('blocked', True):
                    user_configs.append({
                        'username': username,
                        'configs': details.get('configs', []),
                        'traffic': details.get('traffic', 0),
                        'expire': details.get('expire', 0)
                    })
        return user_configs
    except:
        return []

def format_config_text(config_data, lang_code):
    try:
        traffic_gb = round(float(config_data.get('traffic', 0)) / (1024 * 1024 * 1024), 2)
        expire_date = datetime.fromtimestamp(config_data.get('expire', 0)).strftime('%Y-%m-%d')
        
        if lang_code == 'fa':
            return (
                f"🔰 اطلاعات پیکربندی:\n\n"
                f"🔹 نام کاربری: {config_data.get('username')}\n"
                f"🔹 ترافیک: {traffic_gb} GB\n"
                f"🔹 تاریخ انقضا: {expire_date}\n"
            )
        elif lang_code == 'tk':
            return (
                f"🔰 Konfigurasiýa maglumatlary:\n\n"
                f"🔹 Ulanyjy ady: {config_data.get('username')}\n"
                f"🔹 Trafik: {traffic_gb} GB\n"
                f"🔹 Möhleti: {expire_date}\n"
            )
        elif lang_code == 'hi':
            return (
                f"🔰 कॉन्फ़िगरेशन जानकारी:\n\n"
                f"🔹 उपयोगकर्ता नाम: {config_data.get('username')}\n"
                f"🔹 ट्रैफ़िक: {traffic_gb} GB\n"
                f"🔹 समाप्ति तिथि: {expire_date}\n"
            )
        elif lang_code == 'ar':
            return (
                f"🔰 معلومات الإعداد:\n\n"
                f"🔹 اسم المستخدم: {config_data.get('username')}\n"
                f"🔹 حركة المرور: {traffic_gb} GB\n"
                f"🔹 تاريخ الانتهاء: {expire_date}\n"
            )
        elif lang_code == 'ru':
            return (
                f"🔰 Информация о конфигурации:\n\n"
                f"🔹 Имя пользователя: {config_data.get('username')}\n"
                f"🔹 Трафик: {traffic_gb} GB\n"
                f"🔹 Дата окончания: {expire_date}\n"
            )
        else:  # Default to English
            return (
                f"🔰 Configuration Info:\n\n"
                f"🔹 Username: {config_data.get('username')}\n"
                f"🔹 Traffic: {traffic_gb} GB\n"
                f"🔹 Expiry Date: {expire_date}\n"
            )
    except Exception as e:
        print(f"Error formatting config text: {str(e)}")
        return "Error formatting configuration information."

def send_config_details(message, config):
    user_lang = get_user_language(message.from_user.id)
    
    # Send config text
    config_text = format_config_text(config, user_lang)
    bot.reply_to(message, config_text, reply_markup=create_client_markup(user_lang))
    
    # Generate and send QR codes for each config URL
    for config_url in config.get('configs', []):
        try:
            # Generate QR code
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(config_url)
            qr.make(fit=True)
            
            # Create image
            img = qr.make_image(fill_color="black", back_color="white")
            bio = BytesIO()
            img.save(bio, 'PNG')
            bio.seek(0)
            
            # Send QR code image
            bot.send_photo(message.chat.id, bio)
            
            # Send config URL as text
            bot.send_message(message.chat.id, f"`{config_url}`", parse_mode='Markdown')
        except Exception as e:
            print(f"Error sending config details: {str(e)}")
            continue

def show_user_configs(message):
    user_lang = get_user_language(message.from_user.id)
    configs = get_user_configs(message.from_user.id)
    
    if not configs:
        bot.reply_to(
            message,
            get_text(user_lang, 'no_configs'),
            reply_markup=create_client_markup(user_lang)
        )
        return
    
    for config in configs:
        send_config_details(message, config)

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

        payment_status = status['result'].get('payment_status', '')
        amount_paid = float(status['result'].get('paid_amount', 0))
        amount_required = float(status['result'].get('amount', 0))

        # Check various payment statuses
        if payment_status == 'paid' and amount_paid >= amount_required:
            # Payment successful
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
            
        elif payment_status == 'paid' and amount_paid < amount_required:
            # Underpaid
            bot.send_message(
                chat_id,
                f"⚠️ Payment underpaid. Paid: ${amount_paid}, Required: ${amount_required}\n"
                "Please contact support."
            )
            update_payment_status(payment_id, 'underpaid')
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
            
        elif payment_status == 'paid_over':
            # Overpaid but still process
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
                f"⚠️ Note: Payment was overpaid. Paid: ${amount_paid}, Required: ${amount_required}\n"
                "Please contact support for assistance."
            )
            
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
