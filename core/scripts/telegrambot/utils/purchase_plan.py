import json
import datetime
from telebot import types
from utils.command import bot, ADMIN_USER_IDS, is_admin
from utils.common import create_main_markup
from utils.edit_plans import load_plans
from utils.payments import CryptoPayment
from utils.payment_records import add_payment_record, update_payment_status, get_payment_record, load_payments
from utils.adduser import APIClient
from utils.translations import BUTTON_TRANSLATIONS, get_message_text
from utils.language import get_user_language
import qrcode
import io
import os
from dotenv import load_dotenv
import uuid

def format_datetime_string():
    """Generate a datetime string in the format required for username"""
    now = datetime.datetime.now()
    return now.strftime("%Y%m%d%H%M%S")

def create_username_from_user_id(user_id):
    """Create a username using the required format: {telegram numeric id}t{exact date and time}"""
    time_str = format_datetime_string()
    return f"{user_id}t{time_str}"

def send_admin_payment_notification(user_id, username, plan_gb, price, payment_id):
    """Send a notification to all admins about a successful payment"""
    try:
        notification_message = (
            f"💰 <b>Payment Notification</b>\n\n"
            f"✅ <b>Successful Payment Received</b>\n\n"
            f"👤 <b>User ID:</b> <code>{user_id}</code>\n"
            f"📱 <b>Username:</b> <code>{username}</code>\n"
            f"📊 <b>Plan Size:</b> {plan_gb} GB\n"
            f"💵 <b>Amount:</b> ${price}\n"
            f"🔑 <b>Payment ID:</b> <code>{payment_id}</code>\n"
            f"📅 <b>Timestamp:</b> {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        # Send notification to all admins
        for admin_id in ADMIN_USER_IDS:
            try:
                bot.send_message(
                    admin_id,
                    notification_message,
                    parse_mode="HTML"
                )
            except Exception as e:
                print(f"Failed to send notification to admin {admin_id}: {str(e)}")
    except Exception as e:
        print(f"Error in send_admin_payment_notification: {str(e)}")

@bot.message_handler(func=lambda message: any(
    message.text == translations["purchase_plan"] 
    for translations in BUTTON_TRANSLATIONS.values()
))
def purchase_plan(message):
    # Non-admin user purchase flow
    user_id = message.from_user.id
    language = get_user_language(user_id)
    plans = load_plans()
    sorted_plans = sorted(plans.items(), key=lambda x: int(x[0]))
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    for gb, details in sorted_plans:
        unlimited_text = " (Unlimited Users)" if details.get("unlimited") else " (Single User)"
        button_text = f"{gb} GB - ${details['price']} - {details['days']} days{unlimited_text}"
        markup.add(types.InlineKeyboardButton(button_text, callback_data=f"purchase:{gb}"))
    
    bot.reply_to(
        message,
        get_message_text(language, "select_plan"),
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('purchase:'))
def handle_purchase_selection(call):
    try:
        bot.answer_callback_query(call.id)
        plan_gb = call.data.split(':')[1]
        plans = load_plans()
        
        if plan_gb in plans:
            plan = plans[plan_gb]
            
            # Generate a confirmation message
            message = f"📋 Plan Details:\n\n"
            message += f"📊 Data: {plan_gb} GB\n"
            message += f"💰 Price: ${plan['price']}\n"
            message += f"📅 Duration: {plan['days']} days\n"
            unlimited_text = "Yes" if plan.get("unlimited") else "Single User"
            message += f"♾️ Unlimited Users: {unlimited_text}\n\n"
            message += "Proceed with payment?"
            
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("✅ Confirm", callback_data=f"confirm_purchase:{plan_gb}"),
                types.InlineKeyboardButton("❌ Cancel", callback_data="cancel_purchase")
            )
            
            bot.edit_message_text(
                message,
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=markup
            )
        else:
            bot.answer_callback_query(call.id, text="Plan not found!")
    except Exception as e:
        bot.answer_callback_query(call.id, text=f"Error: {str(e)}")

@bot.callback_query_handler(func=lambda call: call.data == "cancel_purchase")
def handle_cancel_purchase(call):
    bot.answer_callback_query(call.id)
    bot.edit_message_text(
        "Purchase canceled.",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('confirm_purchase:'))
def handle_confirm_purchase(call):
    try:
        plan_gb = call.data.split(':')[1]
        plans = load_plans()
        user_id = call.from_user.id

        if plan_gb not in plans:
            bot.answer_callback_query(call.id, text="Plan not found!")
            return

        # Load environment variables to check for available payment methods
        env_path = os.path.join(os.path.dirname(__file__), '.env')
        load_dotenv(env_path)

        crypto_configured = all(os.getenv(key) for key in ['CRYPTO_MERCHANT_ID', 'CRYPTO_API_KEY'])
        card_to_card_configured = os.getenv('CARD_TO_CARD_NUMBER')

        # Create a markup for payment method selection
        markup = types.InlineKeyboardMarkup(row_width=1)
        can_proceed = False

        if crypto_configured:
            markup.add(types.InlineKeyboardButton("💳 Crypto", callback_data=f"payment_method:crypto:{plan_gb}"))
            can_proceed = True
        
        if card_to_card_configured:
            markup.add(types.InlineKeyboardButton("📄 Card to Card (Iran)", callback_data=f"payment_method:card_to_card:{plan_gb}"))
            can_proceed = True

        if not can_proceed:
            bot.edit_message_text(
                "No payment methods are currently configured. Please contact support.",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id
            )
            return

        # If there's more than one payment method, let the user choose
        if crypto_configured and card_to_card_configured:
            bot.edit_message_text(
                "Please select your preferred payment method:",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=markup
            )
        # If only one is available, proceed directly
        elif crypto_configured:
            handle_payment_method_selection(call, f"payment_method:crypto:{plan_gb}")
        elif card_to_card_configured:
            handle_payment_method_selection(call, f"payment_method:card_to_card:{plan_gb}")

    except Exception as e:
        bot.answer_callback_query(call.id, text=f"Error: {str(e)}")


@bot.callback_query_handler(func=lambda call: call.data.startswith('payment_method:'))
def handle_payment_method_selection(call, data=None):
    try:
        # If data is passed directly, use it; otherwise, use call.data
        callback_data = data if data else call.data
        
        _, method, plan_gb = callback_data.split(':')

        if method == 'crypto':
            handle_crypto_payment(call, plan_gb)
        elif method == 'card_to_card':
            handle_card_to_card_payment(call, plan_gb)
        else:
            bot.answer_callback_query(call.id, text="Invalid payment method!")

    except Exception as e:
        bot.answer_callback_query(call.id, text=f"Error: {str(e)}")

def handle_crypto_payment(call, plan_gb):
    try:
        plans = load_plans()
        user_id = call.from_user.id
        
        if plan_gb in plans:
            plan = plans[plan_gb]
            payment_handler = CryptoPayment()
            
            payment_response = payment_handler.create_payment(
                plan['price'],
                plan_gb,
                user_id
            )
            
            if "error" in payment_response:
                bot.edit_message_text(
                    f"❌ Error creating payment: {payment_response['error']}",
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id
                )
                return
            
            # Extract payment data
            payment_data = payment_response.get('result', {})
            payment_id = payment_data.get('uuid')
            payment_url = payment_data.get('url')
            gateway_order_id = payment_data.get('order_id')
            
            if not payment_id or not payment_url:
                bot.edit_message_text(
                    "❌ Invalid payment response from payment gateway.",
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id
                )
                return
            
            # Save payment record
            payment_record = {
                'user_id': user_id,
                'plan_gb': plan_gb,
                'price': plan['price'],
                'days': plan['days'],
                'payment_id': payment_id,
                'order_id': gateway_order_id,
                'status': 'pending'
            }
            add_payment_record(payment_id, payment_record)
            
            # Create QR code for payment URL
            qr = qrcode.make(payment_url)
            bio = io.BytesIO()
            qr.save(bio, 'PNG')
            bio.seek(0)
            
            # Send payment instructions
            payment_message = (
                f"💰 Payment Instructions\n\n"
                f"1. Scan the QR code or click the link below\n"
                f"2. Complete the payment of ${plan['price']}\n"
                f"3. Your config will be created automatically once payment is confirmed\n\n"
                f"Payment Link: {payment_url}\n\n"
                f"Payment ID: `{payment_id}`"
            )
            
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton("🔗 Payment Link", url=payment_url),
                types.InlineKeyboardButton("🔄 Check Status", callback_data=f"check_payment:{payment_id}")
            )
            
            bot.delete_message(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id
            )
            
            bot.send_photo(
                call.message.chat.id,
                photo=bio,
                caption=payment_message,
                reply_markup=markup,
                parse_mode="Markdown"
            )
        else:
            bot.answer_callback_query(call.id, text="Plan not found!")
    except Exception as e:
        bot.answer_callback_query(call.id, text=f"Error processing payment: {str(e)}")

def handle_card_to_card_payment(call, plan_gb):
    try:
        user_id = call.from_user.id
        
        # Load environment variables to get the card number
        env_path = os.path.join(os.path.dirname(__file__), '.env')
        load_dotenv(env_path)
        card_number = os.getenv('CARD_TO_CARD_NUMBER')

        if not card_number:
            bot.edit_message_text(
                "Card to Card payment is not configured. Please contact support.",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id
            )
            return

        plans = load_plans()
        plan = plans[plan_gb]
        price = plan['price']

        message = (
            f"📄 Card to Card Payment\n\n"
            f"Please transfer `${price}` to the following card number:\n\n"
            f"`{card_number}`\n\n"
            f"After the transfer, please send a photo of the receipt."
        )

        bot.edit_message_text(
            message,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="Markdown"
        )

        bot.register_next_step_handler(call.message, process_receipt_photo, plan_gb, price)

    except Exception as e:
        bot.answer_callback_query(call.id, text=f"Error: {str(e)}")


def process_receipt_photo(message, plan_gb, price):
    try:
        user_id = message.from_user.id
        
        if not message.photo:
            bot.reply_to(message, "Please upload a photo of the receipt.")
            bot.register_next_step_handler(message, process_receipt_photo, plan_gb, price)
            return

        # Get the file ID of the largest photo
        file_id = message.photo[-1].file_id
        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        # Generate a unique payment ID
        payment_id = str(uuid.uuid4())
        
        # Ensure the uploads directory exists
        uploads_dir = 'uploads'
        if not os.path.exists(uploads_dir):
            os.makedirs(uploads_dir)

        # Save the photo
        photo_path = os.path.join(uploads_dir, f"{payment_id}.jpg")
        with open(photo_path, 'wb') as new_file:
            new_file.write(downloaded_file)

        # Save payment record
        plans = load_plans()
        plan = plans[plan_gb]
        payment_record = {
            'user_id': user_id,
            'plan_gb': plan_gb,
            'price': price,
            'days': plan['days'],
            'payment_id': payment_id,
            'status': 'pending_approval',
            'receipt_path': photo_path
        }
        add_payment_record(payment_id, payment_record)

        # Send notification to admins
        notification_message = (
            f"⏳ New Pending Payment\n\n"
            f"A user has submitted a receipt for a 'Card to Card' payment.\n\n"
            f"👤 <b>User ID:</b> <code>{user_id}</code>\n"
            f"📊 <b>Plan:</b> {plan_gb} GB\n"
            f"💵 <b>Amount:</b> ${price}\n"
            f"🔑 <b>Payment ID:</b> <code>{payment_id}</code>"
        )
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("✅ Approve", callback_data=f"admin_approval:approve:{payment_id}"),
            types.InlineKeyboardButton("❌ Reject", callback_data=f"admin_approval:reject:{payment_id}")
        )

        for admin_id in ADMIN_USER_IDS:
            try:
                with open(photo_path, 'rb') as photo:
                    bot.send_photo(
                        admin_id,
                        photo,
                        caption=notification_message,
                        reply_markup=markup,
                        parse_mode="HTML"
                    )
            except Exception as e:
                print(f"Failed to send notification to admin {admin_id}: {str(e)}")

        bot.reply_to(message, "Your receipt has been submitted for approval. You will be notified once it is processed.")

    except Exception as e:
        bot.reply_to(message, f"An error occurred: {str(e)}")


@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_approval:'))
def handle_admin_approval(call):
    try:
        user_id = call.from_user.id
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, text="You are not authorized to perform this action.")
            return

        _, action, payment_id = call.data.split(':')
        
        payment_record = get_payment_record(payment_id)
        if not payment_record:
            bot.answer_callback_query(call.id, text="Payment record not found!")
            return

        if payment_record['status'] != 'pending_approval':
            bot.answer_callback_query(call.id, text=f"This payment has already been processed and has a status of '{payment_record['status']}'.")
            return

        if action == 'approve':
            # Provision the service
            user_to_notify = payment_record['user_id']
            plan_gb = payment_record['plan_gb']
            days = payment_record['days']
            username = create_username_from_user_id(user_to_notify)
            
            api_client = APIClient()
            result = api_client.add_user(username, int(plan_gb), int(days))

            if result:
                update_payment_status(payment_id, 'completed')
                user_uri_data = api_client.get_user_uri(username)
                
                if user_uri_data and 'normal_sub' in user_uri_data:
                    sub_url = user_uri_data['normal_sub']
                    qr = qrcode.make(sub_url)
                    bio = io.BytesIO()
                    qr.save(bio, 'PNG')
                    bio.seek(0)
                    
                    success_message = (
                        f"✅ Your payment has been approved and your plan is active!\n\n"
                        f"📊 Plan: {plan_gb} GB\n"
                        f"📅 Duration: {days} days\n"
                        f"📱 Username: `{username}`\n\n"
                        f"Subscription URL: `{sub_url}`"
                    )
                    
                    bot.send_photo(
                        user_to_notify,
                        photo=bio,
                        caption=success_message,
                        parse_mode="Markdown"
                    )
                else:
                    bot.send_message(user_to_notify, "✅ Your payment was approved, but there was an error retrieving your subscription URL. Please contact support.")

                bot.edit_message_caption(caption=f"✅ Payment {payment_id} approved by {call.from_user.first_name}.", chat_id=call.message.chat.id, message_id=call.message.message_id)
            else:
                bot.answer_callback_query(call.id, text="Failed to create user. Please check the logs.")
                bot.send_message(user_to_notify, "❌ Your payment was approved, but there was an error creating your account. Please contact support.")

        elif action == 'reject':
            update_payment_status(payment_id, 'rejected')
            user_to_notify = payment_record['user_id']
            bot.send_message(user_to_notify, "❌ Your payment has been rejected. Please contact support if you believe this is an error.")
            bot.edit_message_caption(caption=f"❌ Payment {payment_id} rejected by {call.from_user.first_name}.", chat_id=call.message.chat.id, message_id=call.message.message_id)

    except Exception as e:
        bot.answer_callback_query(call.id, text=f"An error occurred: {str(e)}")


@bot.callback_query_handler(func=lambda call: call.data.startswith('check_payment:'))
def handle_check_payment(call):
    payment_id = call.data.split(':')[1]
    payment_record = get_payment_record(payment_id)
    
    if not payment_record:
        bot.answer_callback_query(call.id, text="Payment record not found!")
        return
    
    payment_handler = CryptoPayment()
    payment_status_response = payment_handler.check_payment_status(payment_id)
    
    if "error" in payment_status_response:
        bot.answer_callback_query(call.id, text=f"Error checking payment: {payment_status_response['error']}")
        return
    
    payment_status_data = payment_status_response.get('result', {})
    # Support different field names returned by the gateway
    status = payment_status_data.get('status') or payment_status_data.get('payment_status') or payment_status_data.get('paymentStatus')
    
    if status and status.lower() == 'paid':
        user_id = payment_record.get('user_id')
        plan_gb = payment_record.get('plan_gb')
        days = payment_record.get('days')
        price = payment_record.get('price')
        
        # Create a username based on user ID and current timestamp
        username = create_username_from_user_id(user_id)
        
        # Use APIClient to create a user
        api_client = APIClient()
        result = api_client.add_user(username, int(plan_gb), int(days))
        
        if result:
            # Send admin notification about successful payment
            send_admin_payment_notification(user_id, username, plan_gb, price, payment_id)
            
            # Get user URI from API
            user_uri_data = api_client.get_user_uri(username)
            if user_uri_data and 'normal_sub' in user_uri_data:
                sub_url = user_uri_data['normal_sub']
                # Update payment status
                update_payment_status(payment_id, 'completed')
                # Create QR code for subscription URL if available
                qr = qrcode.make(sub_url)
                bio = io.BytesIO()
                qr.save(bio, 'PNG')
                bio.seek(0)
                # Format the message with available links
                success_message = (
                    f"✅ Payment completed!\n\n"
                    f"📊 Your {plan_gb}GB plan is ready.\n"
                    f"📱 Username: `{username}`\n\n"
                    f"Subscription URL: `{sub_url}`\n\n"
                    f"Scan the QR code to configure your VPN."
                )
                # Send the success message with QR code
                bot.send_photo(
                    call.message.chat.id,
                    photo=bio,
                    caption=success_message,
                    parse_mode="Markdown"
                )
            else:
                bot.send_message(
                    call.message.chat.id,
                    f"✅ Payment completed and account created, but couldn't generate subscription URL. Please contact support.",
                    parse_mode="Markdown"
                )
        else:
            bot.send_message(
                call.message.chat.id,
                f"✅ Payment completed but error creating account. Please contact support.",
                parse_mode="Markdown"
            )
    elif status and status.lower() == 'pending':
        bot.answer_callback_query(call.id, text="Payment is still pending. Please complete the payment.")
    else:
        # If we didn't get a clear status, include some debug info for easier troubleshooting
        bot.answer_callback_query(call.id, text=f"Payment status: {status or 'unknown'}")
        try:
            # Optionally log raw response to payments file for debugging (non-blocking)
            import logging
            logging.getLogger('dijiq.payments').debug(f"Check payment response for {payment_id}: {payment_status_response}")
        except Exception:
            pass

# Webhook handler to process payment callbacks (implement if your payment gateway supports webhooks)
def process_payment_webhook(request_data):
    try:
        # This function would be called by your webhook endpoint
        # Webhook payloads may include either 'uuid' (gateway invoice uuid) or 'order_id'
        status = request_data.get('status') or request_data.get('payment_status') or request_data.get('paymentStatus')

        # Resolve the internal payment record key (we store records keyed by gateway uuid)
        payments = load_payments()
        record_key = None

        # If gateway provided uuid, use it directly
        if request_data.get('uuid'):
            record_key = request_data.get('uuid')
        # If only order_id provided, try to find matching record by stored order_id or payment_id
        elif request_data.get('order_id'):
            incoming_order = request_data.get('order_id')
            for k, v in payments.items():
                if v.get('order_id') == incoming_order or v.get('payment_id') == incoming_order:
                    record_key = k
                    break

        if not record_key:
            # Could not resolve payment record
            return False

        if status and status.lower() == 'paid':
            payment_record = get_payment_record(record_key)
            if payment_record and payment_record.get('status') != 'completed':
                # Process the payment as complete
                user_id = payment_record.get('user_id')
                plan_gb = payment_record.get('plan_gb')
                days = payment_record.get('days')
                price = payment_record.get('price')

                # Create a username based on user ID and current timestamp
                username = create_username_from_user_id(user_id)

                # Use APIClient to create a user
                api_client = APIClient()
                result = api_client.add_user(username, int(plan_gb), int(days))

                if result:
                    # Send admin notification about successful payment
                    send_admin_payment_notification(user_id, username, plan_gb, price, record_key)
                    
                    # Get subscription URL
                    sub_url = api_client.get_subscription_url(username)

                    # Update payment status using the internal record key
                    update_payment_status(record_key, 'completed')

                    # Format the message with available links
                    success_message = (
                        f"✅ Payment completed!\n\n"
                        f"📊 Your {plan_gb}GB plan is ready.\n"
                        f"📱 Username: `{username}`\n\n"
                    )

                    if sub_url:
                        success_message += f"Subscription URL: `{sub_url}`\n\n"
                        success_message += "Please save this information for your records."

                    # Send the success message to user
                    bot.send_message(
                        user_id,
                        success_message,
                        parse_mode="Markdown"
                    )

                    # If subscription URL is available, send it as a QR code
                    if sub_url:
                        qr = qrcode.make(sub_url)
                        bio = io.BytesIO()
                        qr.save(bio, 'PNG')
                        bio.seek(0)

                        bot.send_photo(
                            user_id,
                            photo=bio,
                            caption="Scan this QR code to configure your VPN client."
                        )

                    return True
                else:
                    # Send error message to user
                    bot.send_message(
                        user_id,
                        f"✅ Payment completed but error creating account. Please contact support.",
                        parse_mode="Markdown"
                    )
                    return False

        return False
    except Exception as e:
        print(f"Error processing webhook: {str(e)}")
        return False
