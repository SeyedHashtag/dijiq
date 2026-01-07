from telebot import types
from utils.command import bot, ADMIN_USER_IDS, is_admin
from utils.referral import (
    get_or_create_referral_code, 
    get_referral_stats, 
    get_wallet_address, 
    set_wallet_address,
    process_withdrawal_request
)
from utils.translations import BUTTON_TRANSLATIONS, get_message_text, get_button_text
from utils.language import get_user_language

@bot.message_handler(func=lambda message: any(
    message.text == get_button_text(get_user_language(message.from_user.id), "referral") for lang in BUTTON_TRANSLATIONS
))
def referral_menu(message):
    user_id = message.from_user.id
    show_referral_menu(user_id, message.chat.id)

def show_referral_menu(user_id, chat_id, message_id=None):
    language = get_user_language(user_id)
    
    code = get_or_create_referral_code(user_id)
    stats = get_referral_stats(user_id)
    wallet = get_wallet_address(user_id)
    
    try:
        bot_info = bot.get_me()
        bot_username = bot_info.username
    except Exception:
        bot_username = "YourBotName" # Fallback if API fails
    
    referral_link = f"https://t.me/{bot_username}?start={code}"
    
    wallet_info = get_message_text(language, "wallet_info").format(wallet=wallet) if wallet else get_message_text(language, "wallet_not_set")
    
    msg = get_message_text(language, "referral_stats").format(
        count=stats["count"],
        total_earnings=stats["total_earnings"],
        available_balance=stats["available_balance"],
        referral_link=referral_link,
        wallet_info=wallet_info
    )
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    set_wallet_btn = types.InlineKeyboardButton(get_button_text(language, "set_wallet"), callback_data="ref_set_wallet")
    
    buttons = [set_wallet_btn]
    
    if stats["available_balance"] >= 2.0 and wallet:
        withdraw_btn = types.InlineKeyboardButton(get_button_text(language, "withdraw"), callback_data="ref_withdraw")
        buttons.append(withdraw_btn)
        
    markup.add(*buttons)
    
    if message_id:
        bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=msg, reply_markup=markup, parse_mode="Markdown")
    else:
        bot.send_message(chat_id, msg, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "ref_set_wallet")
def handle_set_wallet(call):
    user_id = call.from_user.id
    language = get_user_language(user_id)
    
    msg = bot.send_message(call.message.chat.id, get_message_text(language, "enter_wallet"), parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_wallet_input)

def process_wallet_input(message):
    user_id = message.from_user.id
    language = get_user_language(user_id)
    wallet_address = message.text.strip()
    
    # Basic validation (optional: regex for LTC address)
    if len(wallet_address) < 10: 
        # Very basic check, can be improved
        bot.reply_to(message, "Invalid address length. Please try again.")
        return

    set_wallet_address(user_id, wallet_address)
    bot.reply_to(message, get_message_text(language, "wallet_updated"))
    
    # Show menu again
    show_referral_menu(user_id, message.chat.id)

@bot.callback_query_handler(func=lambda call: call.data == "ref_withdraw")
def handle_withdraw(call):
    user_id = call.from_user.id
    language = get_user_language(user_id)
    stats = get_referral_stats(user_id)
    wallet = get_wallet_address(user_id)
    
    if not wallet:
        bot.answer_callback_query(call.id, "Please set a wallet first.")
        return
        
    if stats["available_balance"] < 2.0:
        bot.answer_callback_query(call.id, "Minimum withdrawal is $2.00")
        return

    msg = get_message_text(language, "withdraw_confirm").format(
        amount=stats["available_balance"],
        wallet=wallet
    )
    
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton(get_button_text(language, "yes"), callback_data="ref_withdraw_confirm"),
        types.InlineKeyboardButton(get_button_text(language, "no"), callback_data="ref_withdraw_cancel")
    )
    
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=msg, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "ref_withdraw_cancel")
def handle_withdraw_cancel(call):
    user_id = call.from_user.id
    show_referral_menu(user_id, call.message.chat.id, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data == "ref_withdraw_confirm")
def handle_withdraw_confirm(call):
    user_id = call.from_user.id
    language = get_user_language(user_id)
    
    success, result = process_withdrawal_request(user_id)
    
    if success:
        amount = result["amount"]
        wallet = result["wallet"]
        
        bot.answer_callback_query(call.id, "Request sent!")
        bot.edit_message_text(
            chat_id=call.message.chat.id, 
            message_id=call.message.message_id, 
            text=get_message_text(language, "withdraw_success"),
            parse_mode="Markdown"
        )
        
        # Notify Admins
        notify_admins_withdrawal(user_id, amount, wallet)
    else:
        bot.answer_callback_query(call.id, "Error!")
        bot.send_message(call.message.chat.id, get_message_text(language, "withdraw_failed").format(reason=result))
        show_referral_menu(user_id, call.message.chat.id)

def notify_admins_withdrawal(user_id, amount, wallet):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ Mark as Paid", callback_data=f"admin_pay_ref:{user_id}"))
    
    msg_text = get_message_text("en", "admin_withdraw_request").format(
        user_id=user_id,
        amount=amount,
        wallet=wallet
    )
    
    for admin_id in ADMIN_USER_IDS:
        try:
            bot.send_message(admin_id, msg_text, reply_markup=markup, parse_mode="Markdown")
        except Exception as e:
            print(f"Failed to notify admin {admin_id}: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_pay_ref:"))
def handle_admin_mark_paid(call):
    user_id_admin = call.from_user.id
    if not is_admin(user_id_admin):
        return

    # Extract user_id from callback data if needed, but we just want to update the message
    # target_user_id = call.data.split(":")[1]
    
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"{call.message.text}\n\n✅ **Paid by Admin {user_id_admin}**",
        reply_markup=None,
        parse_mode="Markdown"
    )
    bot.answer_callback_query(call.id, "Marked as paid.")