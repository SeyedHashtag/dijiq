import json
import datetime
from telebot import types
from utils.command import bot, ADMIN_USER_IDS, is_admin
from utils.common import create_main_markup
from utils.edit_plans import load_plans
from utils.payments import CryptoPayment
from utils.payment_records import (
    add_payment_record,
    update_payment_status,
    get_payment_record,
    load_payments,
    claim_payment_for_processing,
    get_user_payments,
)
from utils.api_client import APIClient
from utils.translations import BUTTON_TRANSLATIONS, get_message_text, get_button_text
from utils.language import get_user_language
from utils.referral import add_referral_reward
from utils.reseller import evaluate_reseller_debt_policies, DEBT_WARNING_THRESHOLD, DEBT_SUSPEND_THRESHOLD
import qrcode
import io
import os
from dotenv import load_dotenv
import uuid
import logging
from utils.username_utils import (
    allocate_username,
    build_user_note,
    extract_existing_usernames,
    format_username_timestamp,
)

# New: Global dictionary for user states
user_data = {}


def _debt_state_label_key(debt_state):
    if debt_state == 'suspended':
        return 'debt_state_suspended'
    if debt_state == 'warning':
        return 'debt_state_warning'
    return 'debt_state_active'

def create_sale_username(api_client, user_id):
    users = api_client.get_users()
    return allocate_username("s", user_id, extract_existing_usernames(users))


def create_sale_user_with_note(api_client, user_id, plan_gb, days, unlimited):
    username = create_sale_username(api_client, user_id)
    note_payload = build_user_note(
        username=username,
        traffic_limit=plan_gb,
        expiration_days=days,
        unlimited=unlimited,
        note_text="sale",
        timestamp=format_username_timestamp(),
    )
    result = api_client.add_user(
        username,
        int(plan_gb),
        int(days),
        unlimited=unlimited,
        note=note_payload,
    )
    if result is None:
        result = api_client.add_user(username, int(plan_gb), int(days), unlimited=unlimited)
        if result is not None:
            logging.getLogger("dijiq.usernames").warning(
                "Created sale user without note fallback. user_id=%s username=%s",
                user_id,
                username,
            )
    return username, result

def send_admin_payment_notification(user_id, username, plan_gb, price, payment_id, payment_method, telegram_username=None):
    """Send a notification to all admins about a successful payment"""
    try:
        for admin_id in ADMIN_USER_IDS:
            admin_language = get_user_language(admin_id)
            notification_message = (
                f"💰 <b>{get_message_text(admin_language, 'payment_notification_title')}</b>\n\n"
                f"✅ <b>{get_message_text(admin_language, 'successful_payment_received')}</b>\n\n"
                f"👤 <b>{get_message_text(admin_language, 'user_id')}:</b> <code>{user_id}</code>\n"
            )
            
            if telegram_username:
                 notification_message += f"📱 <b>Telegram Username:</b> @{telegram_username}\n"
            
            notification_message += (
                f"📱 <b>{get_message_text(admin_language, 'username')}:</b> <code>{username}</code>\n"
                f"📊 <b>{get_message_text(admin_language, 'plan_size')}:</b> {plan_gb} GB\n"
                f"💵 <b>{get_message_text(admin_language, 'amount')}:</b> ${price}\n"
                f"💳 <b>{get_message_text(admin_language, 'payment_method_label')}:</b> {payment_method}\n"
                f"🔑 <b>{get_message_text(admin_language, 'payment_id_label')}:</b> <code>{payment_id}</code>\n"
                f"📅 <b>{get_message_text(admin_language, 'timestamp')}:</b> {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
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

def show_plans(chat_id, user_id, message_id=None):
    language = get_user_language(user_id)
    plans = load_plans()
    sorted_plans = sorted(plans.items(), key=lambda x: int(x[0]))
    markup = types.InlineKeyboardMarkup(row_width=1)
    for gb, details in sorted_plans:
        if details.get('target', 'both') == 'reseller':
            continue
        unlimited_text = get_message_text(language, "unlimited_users") if details.get("unlimited") else get_message_text(language, "single_user")
        button_text = f"{gb} GB - ${details['price']} - {details['days']} " + get_message_text(language, "days") + f"{unlimited_text}"
        markup.add(types.InlineKeyboardButton(button_text, callback_data=f"purchase:{gb}"))
    
    text = get_message_text(language, "select_plan")
    
    if message_id:
        bot.edit_message_text(
            text,
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=markup
        )
    else:
        bot.send_message(
            chat_id,
            text,
            reply_markup=markup
        )

@bot.message_handler(func=lambda message: any(
    message.text == get_button_text(get_user_language(message.from_user.id), "purchase_plan") for lang in BUTTON_TRANSLATIONS
))
def purchase_plan(message):
    show_plans(message.chat.id, message.from_user.id)

@bot.callback_query_handler(func=lambda call: call.data == "back_to_plans")
def back_to_plans(call):
    try:
        bot.answer_callback_query(call.id)
        show_plans(call.message.chat.id, call.from_user.id, call.message.message_id)
    except Exception as e:
        print(f"Error in back_to_plans: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('purchase:'))
def handle_purchase_selection(call):
    try:
        bot.answer_callback_query(call.id)
        user_id = call.from_user.id
        language = get_user_language(user_id)
        plan_gb = call.data.split(':')[1]
        plans = load_plans()
        if plan_gb in plans:
            plan = plans[plan_gb]
            if plan.get('target', 'both') == 'reseller':
                bot.answer_callback_query(call.id, text='This plan is for resellers only.')
                return
            unlimited_text = "Yes" if plan.get("unlimited") else "No"
            message = get_message_text(language, "plan_details")
            message += get_message_text(language, "data").format(plan_gb=plan_gb)
            message += get_message_text(language, "price").format(price=plan['price'])
            message += get_message_text(language, "duration").format(days=plan['days'])
            message += get_message_text(language, "unlimited").format(unlimited_text=unlimited_text)
            message += get_message_text(language, "select_payment_method")

            # Check configured payment methods
            env_path = os.path.join(os.path.dirname(__file__), '.env')
            load_dotenv(env_path)
            crypto_configured = all(os.getenv(key) for key in ['CRYPTO_MERCHANT_ID', 'CRYPTO_API_KEY'])
            card_to_card_configured = os.getenv('CARD_TO_CARD_NUMBER')
            card_to_card_mode = os.getenv('CARD_TO_CARD_MODE', 'on')
            
            # Always show card-to-card if configured
            show_card_to_card = bool(card_to_card_configured)
            
            markup = types.InlineKeyboardMarkup(row_width=1)
            methods_count = 0
            if crypto_configured:
                markup.add(types.InlineKeyboardButton(get_button_text(language, "crypto"), callback_data=f"payment_method:crypto:{plan_gb}"))
                methods_count += 1
            if show_card_to_card:
                markup.add(types.InlineKeyboardButton(get_button_text(language, "card_to_card"), callback_data=f"payment_method:card_to_card:{plan_gb}"))
                methods_count += 1
            
            if methods_count == 0:
                 bot.answer_callback_query(call.id, text=get_message_text(language, "no_payment_methods"))
                 return

            markup.add(types.InlineKeyboardButton(get_button_text(language, "back"), callback_data="back_to_plans")) 

            bot.edit_message_text(
                message,
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=markup
            )
        else:
            bot.answer_callback_query(call.id, text=get_message_text(language, "plan_not_found"))
    except Exception as e:
        user_id = call.from_user.id
        language = get_user_language(user_id)
        bot.answer_callback_query(call.id, text=get_message_text(language, "error_occurred").format(error=str(e)))

@bot.callback_query_handler(func=lambda call: call.data == "cancel_purchase")
def handle_cancel_purchase(call):
    user_id = call.from_user.id
    language = get_user_language(user_id)
    bot.answer_callback_query(call.id)
    bot.delete_message(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id
    )
    # New: Clear user state if it exists (prevents lingering receipt waiting mode)
    if user_id in user_data:
        del user_data[user_id]
    bot.send_message(
        chat_id=call.message.chat.id,
        text=get_message_text(language, "purchase_canceled")
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('payment_method:'))
def handle_payment_method_selection(call, data=None):
    try:
        user_id = call.from_user.id
        language = get_user_language(user_id)
        callback_data = data if data else call.data
        _, method, plan_gb = callback_data.split(':')
        if method == 'crypto':
            handle_crypto_payment(call, plan_gb)
        elif method == 'card_to_card':
            env_path = os.path.join(os.path.dirname(__file__), '.env')
            load_dotenv(env_path)
            card_to_card_mode = os.getenv('CARD_TO_CARD_MODE', 'on')
            if card_to_card_mode == 'previous_customers':
                try:
                    user_payments = get_user_payments(user_id)
                    has_completed = any(
                        p.get('status') == 'completed' for p in user_payments.values()
                    )
                    if not has_completed:
                        bot.answer_callback_query(call.id, text=get_message_text(language, "card_to_card_second_purchase"), show_alert=False)
                        return
                except Exception as e:
                    logging.getLogger('dijiq.payments').warning(
                        f"Failed to determine previous customer status for user {user_id}: {e}"
                    )
            handle_card_to_card_payment(call, plan_gb)
        else:
            bot.answer_callback_query(call.id, text=get_message_text(language, "invalid_payment_method"))
    except Exception as e:
        user_id = call.from_user.id
        language = get_user_language(user_id)
        bot.answer_callback_query(call.id, text=get_message_text(language, "error_occurred").format(error=str(e)))

def handle_crypto_payment(call, plan_gb):
    try:
        user_id = call.from_user.id
        language = get_user_language(user_id)
        plans = load_plans()
        if plan_gb in plans:
            plan = plans[plan_gb]
            if plan.get(\'target\', \'both\') == \'reseller\':
                bot.answer_callback_query(call.id, text=\'This plan is for resellers only.\')
                return
            payment_handler = CryptoPayment()
            payment_response = payment_handler.create_payment(
                plan['price'], plan_gb, user_id
            )
            if "error" in payment_response:
                bot.edit_message_text(
                    get_message_text(language, "error_creating_payment").format(error=payment_response['error']),
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id
                )
                return
            payment_data = payment_response.get('result', {})
            payment_id = payment_data.get('uuid')
            payment_url = payment_data.get('url')
            gateway_order_id = payment_data.get('order_id')
            if not payment_id or not payment_url:
                bot.edit_message_text(
                    get_message_text(language, "invalid_payment_response"),
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id
                )
                return
            payment_record = {
                'user_id': user_id,
                'plan_gb': plan_gb,
                'price': plan['price'],
                'days': plan['days'],
                'unlimited': plan.get('unlimited', False),
                'payment_id': payment_id,
                'order_id': gateway_order_id,
                'status': 'pending',
                'payment_method': 'Crypto'
            }
            add_payment_record(payment_id, payment_record)
            qr = qrcode.make(payment_url)
            bio = io.BytesIO()
            qr.save(bio, 'PNG')
            bio.seek(0)
            payment_message = get_message_text(language, "payment_instructions").format(price=plan['price'], payment_url=payment_url, payment_id=payment_id)
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton(get_button_text(language, "payment_link"), url=payment_url),
                types.InlineKeyboardButton(get_button_text(language, "check_status"), callback_data=f"check_payment:{payment_id}")
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
            bot.answer_callback_query(call.id, text=get_message_text(language, "plan_not_found"))
    except Exception as e:
        user_id = call.from_user.id
        language = get_user_language(user_id)
        bot.answer_callback_query(call.id, text=get_message_text(language, "error_processing_payment").format(error=str(e)))

def handle_card_to_card_payment(call, plan_gb):
    try:
        user_id = call.from_user.id
        language = get_user_language(user_id)
        env_path = os.path.join(os.path.dirname(__file__), '.env')
        load_dotenv(env_path)
        card_number = os.getenv('CARD_TO_CARD_NUMBER')
        exchange_rate = os.getenv('EXCHANGE_RATE', '1')
        if not card_number:
            bot.edit_message_text(
                get_message_text(language, "card_to_card_not_configured"),
                chat_id=call.message.chat.id,
                message_id=call.message.message_id
            )
            return
        plans = load_plans()
        plan = plans[plan_gb]
        price = plan['price']
        # Convert price to tomans using the exchange rate
        price_in_tomans = float(price) * float(exchange_rate)
        message = get_message_text(language, "card_to_card_payment").format(price=price_in_tomans, card_number=card_number)
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(get_button_text(language, "cancel"), callback_data="cancel_purchase"))
        bot.edit_message_text(
            message,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="Markdown",
            reply_markup=markup
        )
        # New: Set user state instead of registering next_step_handler
        user_data[user_id] = {
            'state': 'waiting_receipt',
            'plan_gb': plan_gb,
            'price': price,
            'receipt_prompt_message_id': call.message.message_id,
        }
    except Exception as e:
        user_id = call.from_user.id
        language = get_user_language(user_id)
        bot.answer_callback_query(call.id, text=get_message_text(language, "error_occurred").format(error=str(e)))

# Modified: Remove photo check and re-registration; assume called only on photos
def process_receipt_photo(message, plan_gb, price):
    try:
        user_id = message.from_user.id
        language = get_user_language(user_id)
        receipt_prompt_message_id = None
        if user_id in user_data:
            receipt_prompt_message_id = user_data[user_id].get('receipt_prompt_message_id')
        file_id = message.photo[-1].file_id
        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        payment_id = str(uuid.uuid4())
        uploads_dir = 'uploads'
        if not os.path.exists(uploads_dir):
            os.makedirs(uploads_dir)
        photo_path = os.path.join(uploads_dir, f"{payment_id}.jpg")
        with open(photo_path, 'wb') as new_file:
            new_file.write(downloaded_file)
        
        if plan_gb == 'Settlement':
             payment_record = {
                'user_id': user_id,
                'plan_gb': plan_gb,
                'price': price,
                'days': 0,
                'payment_id': payment_id,
                'status': 'pending_approval',
                'receipt_path': photo_path,
                'type': 'settlement',
                'payment_method': 'Card to Card'
            }
        else:
            plans = load_plans()
            plan = plans[plan_gb]
            payment_record = {
                'user_id': user_id,
                'plan_gb': plan_gb,
                'price': price,
                'days': plan['days'],
                'unlimited': plan.get('unlimited', False),
                'payment_id': payment_id,
                'status': 'pending_approval',
                'receipt_path': photo_path,
                'payment_method': 'Card to Card'
            }
            
        add_payment_record(payment_id, payment_record)
        notification_message = (
            f"⏳ New Pending Payment\n\n"
            f"A user has submitted a receipt for a 'Card to Card' payment.\n\n"
            f"👤 <b>User ID:</b> <code>{user_id}</code>\n"
        )
        if message.from_user.username:
            notification_message += f"📱 <b>Telegram Username:</b> @{message.from_user.username}\n"
            
        notification_message += (
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
        if receipt_prompt_message_id:
            try:
                bot.edit_message_reply_markup(
                    chat_id=message.chat.id,
                    message_id=receipt_prompt_message_id,
                    reply_markup=None
                )
            except Exception:
                pass
        bot.reply_to(message, get_message_text(language, "receipt_submitted"))
        # New: Clear state after processing
        if user_id in user_data:
            del user_data[user_id]
    except Exception as e:
        user_id = message.from_user.id
        language = get_user_language(user_id)
        bot.reply_to(message, get_message_text(language, "error_occurred").format(error=str(e)))

# New: State-aware handler for photos
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    user_id = message.from_user.id
    if user_id in user_data and user_data[user_id]['state'] == 'waiting_receipt':
        plan_gb = user_data[user_id]['plan_gb']
        price = user_data[user_id]['price']
        process_receipt_photo(message, plan_gb, price)
    # Optional: Handle non-state photos if needed (e.g., ignore or reply)

# New: Handler for text messages while waiting for receipt (reminds without looping)
@bot.message_handler(func=lambda message: message.from_user.id in user_data and user_data[message.from_user.id]['state'] == 'waiting_receipt')
def handle_text_while_waiting(message):
    language = get_user_language(message.from_user.id)
    cancel_callback = user_data[message.from_user.id].get('cancel_callback', 'cancel_purchase')
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(get_button_text(language, "cancel"), callback_data=cancel_callback))
    bot.reply_to(message, get_message_text(language, "upload_receipt"), reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_approval:'))
def handle_admin_approval(call):
    try:
        user_id = call.from_user.id
        language = get_user_language(user_id)
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, text=get_message_text(language, "not_authorized"))
            return
        _, action, payment_id = call.data.split(':')
        payment_record = get_payment_record(payment_id)
        if not payment_record:
            bot.answer_callback_query(call.id, text=get_message_text(language, "payment_record_not_found"))
            return
        if payment_record['status'] != 'pending_approval':
            bot.answer_callback_query(call.id, text=get_message_text(language, "payment_already_processed").format(status=payment_record['status']))
            return
        if action == 'approve':
            if payment_record.get('type') == 'settlement' or payment_record.get('plan_gb') == 'Settlement':
                 from utils.reseller import apply_reseller_payment
                 apply_reseller_payment(payment_record['user_id'], payment_record.get('price', 0))
                 update_payment_status(payment_id, 'completed')
                 
                 user_to_notify = payment_record['user_id']
                 user_language = get_user_language(user_to_notify)
                 
                 telegram_username = None
                 try:
                    chat = bot.get_chat(user_to_notify)
                    telegram_username = chat.username
                 except:
                    pass

                 send_admin_payment_notification(
                    user_to_notify, 
                    "Settlement", 
                    "Settlement", 
                    payment_record['price'], 
                    payment_id, 
                    payment_record.get('payment_method', 'Card to Card'), 
                    telegram_username=telegram_username
                )

                 bot.send_message(user_to_notify, get_message_text(user_language, "settlement_payment_approved"))
                 bot.edit_message_caption(caption=f"✅ Settlement Payment {payment_id} approved by {call.from_user.first_name}.", chat_id=call.message.chat.id, message_id=call.message.message_id)
                 return

            user_to_notify = payment_record['user_id']
            user_language = get_user_language(user_to_notify)
            plan_gb = payment_record['plan_gb']
            days = payment_record['days']
            
            unlimited = payment_record.get('unlimited')
            if unlimited is None:
                 plans = load_plans()
                 if plan_gb in plans:
                     unlimited = plans[plan_gb].get('unlimited', False)
                 else:
                     unlimited = False
            
            api_client = APIClient()
            username, result = create_sale_user_with_note(
                api_client,
                user_to_notify,
                plan_gb,
                days,
                unlimited,
            )
            if result:
                update_payment_status(payment_id, 'completed')
                add_referral_reward(payment_record['user_id'], payment_record['price'])
                
                telegram_username = None
                try:
                    chat = bot.get_chat(user_to_notify)
                    telegram_username = chat.username
                except:
                    pass
                    
                send_admin_payment_notification(
                    user_to_notify, 
                    username, 
                    plan_gb, 
                    payment_record['price'], 
                    payment_id, 
                    payment_record.get('payment_method', 'Card to Card'), 
                    telegram_username=telegram_username
                )

                user_uri_data = api_client.get_user_uri(username)
                if user_uri_data and 'normal_sub' in user_uri_data:
                    sub_url = user_uri_data['normal_sub']
                    ipv4_url = user_uri_data.get('ipv4', '')
                    ipv4_info = f"IPv4 URL: `{ipv4_url}`\n\n" if ipv4_url else ""

                    qr = qrcode.make(sub_url)
                    bio = io.BytesIO()
                    qr.save(bio, 'PNG')
                    bio.seek(0)
                    success_message = get_message_text(user_language, "payment_approved").format(plan_gb=plan_gb, days=days, username=username, sub_url=sub_url, ipv4_info=ipv4_info)
                    bot.send_photo(
                        user_to_notify,
                        photo=bio,
                        caption=success_message,
                        parse_mode="Markdown"
                    )
                else:
                    bot.send_message(user_to_notify, get_message_text(user_language, "payment_approved_no_url"))
                bot.edit_message_caption(caption=f"✅ Payment {payment_id} approved by {call.from_user.first_name}.", chat_id=call.message.chat.id, message_id=call.message.message_id)
            else:
                bot.answer_callback_query(call.id, text=get_message_text(language, "failed_to_create_user"))
                bot.send_message(user_to_notify, get_message_text(user_language, "payment_approved_user_error"))
        elif action == 'reject':
            update_payment_status(payment_id, 'rejected')
            user_to_notify = payment_record['user_id']
            user_language = get_user_language(user_to_notify)
            
            if payment_record.get('type') == 'settlement' or payment_record.get('plan_gb') == 'Settlement':
                 bot.send_message(user_to_notify, get_message_text(user_language, "settlement_payment_rejected"))
            else:
                 bot.send_message(user_to_notify, get_message_text(user_language, "payment_rejected"))
                 
            bot.edit_message_caption(caption=f"❌ Payment {payment_id} rejected by {call.from_user.first_name}.", chat_id=call.message.chat.id, message_id=call.message.message_id)
    except Exception as e:
        user_id = call.from_user.id
        language = get_user_language(user_id)
        bot.answer_callback_query(call.id, text=get_message_text(language, "error_occurred").format(error=str(e)))

@bot.callback_query_handler(func=lambda call: call.data.startswith('check_payment:'))
def handle_check_payment(call):
    user_id = call.from_user.id
    language = get_user_language(user_id)
    payment_id = call.data.split(':')[1]
    payment_record = get_payment_record(payment_id)
    if not payment_record:
        bot.answer_callback_query(call.id, text=get_message_text(language, "payment_record_not_found"))
        return
    if payment_record.get('status') == 'completed':
        bot.answer_callback_query(call.id, text=get_message_text(language, "payment_already_processed").format(status='completed'))
        return
    if payment_record.get('status') == 'processing':
        bot.answer_callback_query(call.id, text=get_message_text(language, "payment_already_processed").format(status='processing'))
        return
    payment_handler = CryptoPayment()
    payment_status_response = payment_handler.check_payment_status(payment_id)
    if "error" in payment_status_response:
        bot.answer_callback_query(call.id, text=get_message_text(language, "error_checking_payment").format(error=payment_status_response['error']))
        return
    payment_status_data = payment_status_response.get('result', {})
    status = payment_status_data.get('status') or payment_status_data.get('payment_status') or payment_status_data.get('paymentStatus')
    if status and status.lower() == 'paid':
        if not claim_payment_for_processing(payment_id, allowed_statuses={'pending'}):
            latest_record = get_payment_record(payment_id) or {}
            latest_status = latest_record.get('status', 'unknown')
            bot.answer_callback_query(call.id, text=get_message_text(language, "payment_already_processed").format(status=latest_status))
            return

        payment_record = get_payment_record(payment_id) or payment_record
        user_id = payment_record.get('user_id')
        plan_gb = payment_record.get('plan_gb')
        
        if payment_record.get('type') == 'settlement' or plan_gb == 'Settlement':
             from utils.reseller import apply_reseller_payment
             apply_reseller_payment(user_id, payment_record.get('price', 0))
             update_payment_status(payment_id, 'completed')
             bot.send_message(
                call.message.chat.id,
                get_message_text(language, "debt_cleared"),
                parse_mode="Markdown"
            )
             return

        days = payment_record.get('days')
        price = payment_record.get('price')
        
        unlimited = payment_record.get('unlimited')
        if unlimited is None:
                plans = load_plans()
                if plan_gb in plans:
                    unlimited = plans[plan_gb].get('unlimited', False)
                else:
                    unlimited = False
        
        api_client = APIClient()
        username, result = create_sale_user_with_note(
            api_client,
            user_id,
            plan_gb,
            days,
            unlimited,
        )
        if result:
            send_admin_payment_notification(user_id, username, plan_gb, price, payment_id, "Crypto", telegram_username=call.from_user.username)
            add_referral_reward(user_id, price)
            user_uri_data = api_client.get_user_uri(username)
            update_payment_status(payment_id, 'completed')
            if user_uri_data and 'normal_sub' in user_uri_data:
                sub_url = user_uri_data['normal_sub']
                ipv4_url = user_uri_data.get('ipv4', '')
                ipv4_info = f"IPv4 URL: `{ipv4_url}`\n\n" if ipv4_url else ""

                qr = qrcode.make(sub_url)
                bio = io.BytesIO()
                qr.save(bio, 'PNG')
                bio.seek(0)
                success_message = get_message_text(language, "payment_completed").format(plan_gb=plan_gb, username=username, sub_url=sub_url, ipv4_info=ipv4_info)
                bot.send_photo(
                    call.message.chat.id,
                    photo=bio,
                    caption=success_message,
                    parse_mode="Markdown"
                )
            else:
                bot.send_message(
                    call.message.chat.id,
                    get_message_text(language, "payment_completed_no_url"),
                    parse_mode="Markdown"
                )
        else:
            bot.send_message(
                call.message.chat.id,
                get_message_text(language, "payment_completed_user_error"),
                parse_mode="Markdown"
            )
    elif status and status.lower() == 'pending':
        bot.answer_callback_query(call.id, text=get_message_text(language, "payment_pending"))
    else:
        bot.answer_callback_query(call.id, text=get_message_text(language, "payment_status").format(status=status or 'unknown'))
    try:
        import logging
        logging.getLogger('dijiq.payments').debug(f"Check payment response for {payment_id}: {payment_status_response}")
    except Exception:
        pass

def process_payment_webhook(request_data):
    try:
        status = request_data.get('status') or request_data.get('payment_status') or request_data.get('paymentStatus')
        payments = load_payments()
        record_key = None
        if request_data.get('uuid'):
            record_key = request_data.get('uuid')
        elif request_data.get('order_id'):
            incoming_order = request_data.get('order_id')
            for k, v in payments.items():
                if v.get('order_id') == incoming_order or v.get('payment_id') == incoming_order:
                    record_key = k
                    break
        if not record_key:
            return False
        if status and status.lower() == 'paid':
            payment_record = get_payment_record(record_key)
            if payment_record and payment_record.get('status') == 'pending':
                user_id = payment_record.get('user_id')
                user_language = get_user_language(user_id)
                plan_gb = payment_record.get('plan_gb')
                
                if payment_record.get('type') == 'settlement' or plan_gb == 'Settlement':
                     from utils.reseller import apply_reseller_payment
                     apply_reseller_payment(user_id, payment_record.get('price', 0))
                     update_payment_status(record_key, 'completed')
                     bot.send_message(
                        user_id,
                        get_message_text(user_language, "debt_cleared"),
                        parse_mode="Markdown"
                     )
                     return True

                days = payment_record.get('days')
                price = payment_record.get('price')
                
                unlimited = payment_record.get('unlimited')
                if unlimited is None:
                    plans = load_plans()
                    if plan_gb in plans:
                        unlimited = plans[plan_gb].get('unlimited', False)
                    else:
                        unlimited = False
                
                api_client = APIClient()
                username, result = create_sale_user_with_note(
                    api_client,
                    user_id,
                    plan_gb,
                    days,
                    unlimited,
                )
                if result:
                    payment_method = "Crypto" if "order_id" in payment_record else "Card to Card"
                    telegram_username = None
                    try:
                        chat = bot.get_chat(user_id)
                        telegram_username = chat.username
                    except:
                        pass
                    send_admin_payment_notification(user_id, username, plan_gb, price, record_key, payment_method, telegram_username=telegram_username)
                    add_referral_reward(user_id, price)
                    
                    user_uri_data = api_client.get_user_uri(username)
                    sub_url = user_uri_data.get('normal_sub') if user_uri_data else None
                    ipv4_url = user_uri_data.get('ipv4', '') if user_uri_data else ''
                    ipv4_info = f"IPv4 URL: `{ipv4_url}`\n\n" if ipv4_url else ""
                    
                    update_payment_status(record_key, 'completed')
                    success_message = get_message_text(user_language, "payment_completed").format(plan_gb=plan_gb, username=username, sub_url=sub_url, ipv4_info=ipv4_info)
                    bot.send_message(
                        user_id,
                        success_message,
                        parse_mode="Markdown"
                    )
                    if sub_url:
                        qr = qrcode.make(sub_url)
                        bio = io.BytesIO()
                        qr.save(bio, 'PNG')
                        bio.seek(0)
                        bot.send_photo(
                            user_id,
                            photo=bio,
                            caption=get_message_text(user_language, "scan_qr_code")
                        )
                    return True
                else:
                    bot.send_message(
                        user_id,
                        get_message_text(user_language, "payment_completed_user_error"),
                        parse_mode="Markdown"
                    )
                    return False
            return False
        return False
    except Exception as e:
        print(f"Error processing webhook: {str(e)}")
        return False

def check_pending_payments():
    try:
        payments = load_payments()
        payment_handler = CryptoPayment()
        
        for payment_id, record in payments.items():
            if record.get('status') == 'pending':
                # Check if payment is not too old (e.g., > 24 hours) — mark as expired
                created_at_str = record.get('created_at')
                if created_at_str:
                    try:
                        created_at = datetime.datetime.strptime(created_at_str, '%Y-%m-%d %H:%M:%S')
                        if datetime.datetime.now() - created_at > datetime.timedelta(hours=24):
                            update_payment_status(payment_id, 'expired')
                            continue
                    except ValueError:
                        pass

                # Check status
                try:
                    response = payment_handler.check_payment_status(payment_id)
                    if "error" in response:
                        continue
                        
                    result = response.get('result', {})
                    status = result.get('status') or result.get('payment_status') or result.get('paymentStatus')
                    
                    if status and status.lower() == 'paid':
                        # Process payment
                        user_id = record.get('user_id')
                        plan_gb = record.get('plan_gb')
                        
                        if record.get('type') == 'settlement' or plan_gb == 'Settlement':
                             from utils.reseller import apply_reseller_payment
                             apply_reseller_payment(user_id, record.get('price', 0))
                             update_payment_status(payment_id, 'completed')
                             try:
                                user_language = get_user_language(user_id)
                                bot.send_message(
                                    user_id,
                                    get_message_text(user_language, "debt_cleared"),
                                    parse_mode="Markdown"
                                )
                             except:
                                 pass
                             continue

                        days = record.get('days')
                        price = record.get('price')
                        
                        unlimited = record.get('unlimited')
                        if unlimited is None:
                            plans = load_plans()
                            if plan_gb in plans:
                                unlimited = plans[plan_gb].get('unlimited', False)
                            else:
                                unlimited = False
                        
                        api_client = APIClient()
                        username, add_result = create_sale_user_with_note(
                            api_client,
                            user_id,
                            plan_gb,
                            days,
                            unlimited,
                        )
                        
                        if add_result:
                            telegram_username = None
                            try:
                                chat = bot.get_chat(user_id)
                                telegram_username = chat.username
                            except:
                                pass
                            send_admin_payment_notification(user_id, username, plan_gb, price, payment_id, "Crypto", telegram_username=telegram_username)
                            add_referral_reward(user_id, price)
                            user_uri_data = api_client.get_user_uri(username)
                            
                            update_payment_status(payment_id, 'completed')
                            
                            user_language = get_user_language(user_id)
                            
                            if user_uri_data and 'normal_sub' in user_uri_data:
                                sub_url = user_uri_data['normal_sub']
                                ipv4_url = user_uri_data.get('ipv4', '')
                                ipv4_info = f"IPv4 URL: `{ipv4_url}`\n\n" if ipv4_url else ""

                                qr = qrcode.make(sub_url)
                                bio = io.BytesIO()
                                qr.save(bio, 'PNG')
                                bio.seek(0)
                                success_message = get_message_text(user_language, "payment_completed").format(plan_gb=plan_gb, username=username, sub_url=sub_url, ipv4_info=ipv4_info)
                                try:
                                    bot.send_photo(
                                        user_id,
                                        photo=bio,
                                        caption=success_message,
                                        parse_mode="Markdown"
                                    )
                                except Exception as e:
                                    print(f"Failed to send success message to user {user_id}: {e}")
                            else:
                                try:
                                    bot.send_message(
                                        user_id,
                                        get_message_text(user_language, "payment_completed_no_url"),
                                        parse_mode="Markdown"
                                    )
                                except Exception as e:
                                    print(f"Failed to send success message to user {user_id}: {e}")
                except Exception as e:
                    print(f"Error checking pending payment {payment_id}: {e}")

        # Also run reseller debt reminders/escalations on the same monitoring cycle.
        debt_events = evaluate_reseller_debt_policies()
        for event in debt_events:
            try:
                reseller_id = int(event['user_id'])
            except (TypeError, ValueError):
                continue

            debt = float(event.get('debt', 0.0))
            debt_state = str(event.get('debt_state', 'active'))
            debt_age_days = int(event.get('debt_age_days', 0))
            unlock_amount = float(event.get('unlock_amount', 0.0))

            if event.get('notify_user'):
                try:
                    user_language = get_user_language(reseller_id)
                    if debt_state == 'suspended':
                        user_message = get_message_text(user_language, "reseller_debt_reminder_suspended").format(
                            debt=debt,
                            debt_age_days=debt_age_days,
                            unlock_amount=unlock_amount
                        )
                    else:
                        user_message = get_message_text(user_language, "reseller_debt_reminder_warning").format(
                            debt=debt,
                            debt_age_days=debt_age_days,
                            suspend_threshold=DEBT_SUSPEND_THRESHOLD
                        )

                    markup = types.InlineKeyboardMarkup()
                    markup.add(
                        types.InlineKeyboardButton(
                            get_button_text(user_language, "settle_debt"),
                            callback_data=f"reseller:settle:{debt:.2f}"
                        )
                    )
                    bot.send_message(reseller_id, user_message, reply_markup=markup)
                except Exception:
                    pass

            if event.get('notify_admin'):
                for admin_id in ADMIN_USER_IDS:
                    try:
                        admin_language = get_user_language(admin_id)
                        state_text = get_message_text(admin_language, _debt_state_label_key(debt_state))
                        admin_message = get_message_text(admin_language, "reseller_debt_threshold_crossed_admin").format(
                            reseller_id=reseller_id,
                            debt_state=state_text,
                            debt=debt,
                            debt_age_days=debt_age_days,
                            warning_threshold=DEBT_WARNING_THRESHOLD,
                            suspend_threshold=DEBT_SUSPEND_THRESHOLD
                        )
                        bot.send_message(admin_id, admin_message)
                    except Exception:
                        pass

    except Exception as e:
        print(f"Error in check_pending_payments: {e}")
