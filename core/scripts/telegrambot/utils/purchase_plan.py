import json
import datetime
from telebot import types
from utils.command import bot
from utils.common import create_main_markup
from utils.edit_plans import load_plans
from utils.payments import CryptomusPayment
from utils.payment_records import add_payment_record, update_payment_status, get_payment_record
from utils.adduser import APIClient
from utils.translations import BUTTON_TRANSLATIONS, get_message_text
from utils.language import get_user_language
import qrcode
import io

def format_datetime_string():
    """Generate a datetime string in the format required for username"""
    now = datetime.datetime.now()
    return now.strftime("%Y%m%d%H%M%S")

def create_username_from_user_id(user_id):
    """Create a username using the required format: {telegram numeric id}t{exact date and time}"""
    time_str = format_datetime_string()
    return f"{user_id}t{time_str}"

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
        button_text = f"{gb} GB - ${details['price']} - {details['days']} days"
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
            message += f"📅 Duration: {plan['days']} days\n\n"
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
        
        if plan_gb in plans:
            plan = plans[plan_gb]
            payment_handler = CryptomusPayment()
            
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
            try:
                payment_data = payment_response.get('result', {})
                payment_id = payment_data.get('uuid')
                payment_url = payment_data.get('url')
                
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
                    'status': 'pending'
                }
                add_payment_record(payment_id, payment_record)
                
                # Create QR code for payment URL
                qr = qrcode.make(payment_url)
                bio = io.BytesIO()
                qr.save(bio, 'PNG')
                bio.seek(0)
                
                # Send payment instructions with QR code
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
                
                # Send the QR code with payment instructions
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
                
            except Exception as e:
                bot.edit_message_text(
                    f"❌ Error processing payment: {str(e)}",
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id
                )
        else:
            bot.answer_callback_query(call.id, text="Plan not found!")
    except Exception as e:
        bot.answer_callback_query(call.id, text=f"Error: {str(e)}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('check_payment:'))
def handle_check_payment(call):
    payment_id = call.data.split(':')[1]
    payment_record = get_payment_record(payment_id)
    
    if not payment_record:
        bot.answer_callback_query(call.id, text="Payment record not found!")
        return
    
    payment_handler = CryptomusPayment()
    payment_status_response = payment_handler.check_payment_status(payment_id)
    
    if "error" in payment_status_response:
        bot.answer_callback_query(call.id, text=f"Error checking payment: {payment_status_response['error']}")
        return
    
    payment_status_data = payment_status_response.get('result', {})
    status = payment_status_data.get('status')
    
    if status == 'paid':
        user_id = payment_record.get('user_id')
        plan_gb = payment_record.get('plan_gb')
        days = payment_record.get('days')
        
        # Create a username based on user ID and current timestamp
        username = create_username_from_user_id(user_id)
        
        # Use APIClient to create a user
        api_client = APIClient()
        result = api_client.add_user(username, int(plan_gb), int(days))
        
        if result:
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
    elif status == 'pending':
        bot.answer_callback_query(call.id, text="Payment is still pending. Please complete the payment.")
    else:
        bot.answer_callback_query(call.id, text=f"Payment status: {status}")

# Webhook handler to process payment callbacks (implement if your payment gateway supports webhooks)
def process_payment_webhook(request_data):
    try:
        # This function would be called by your webhook endpoint
        payment_id = request_data.get('order_id')
        status = request_data.get('status')
        
        if payment_id and status == 'paid':
            payment_record = get_payment_record(payment_id)
            if payment_record and payment_record.get('status') != 'completed':
                # Process the payment as complete
                user_id = payment_record.get('user_id')
                plan_gb = payment_record.get('plan_gb')
                days = payment_record.get('days')
                
                # Create a username based on user ID and current timestamp
                username = create_username_from_user_id(user_id)
                
                # Use APIClient to create a user
                api_client = APIClient()
                result = api_client.add_user(username, int(plan_gb), int(days))
                
                if result:
                    # Get subscription URL
                    sub_url = api_client.get_subscription_url(username)
                    
                    # Update payment status
                    update_payment_status(payment_id, 'completed')
                    
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
    except Exception as e:
        print(f"Error processing webhook: {str(e)}")
        return False