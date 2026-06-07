import io
import json
from datetime import datetime
from telebot import types
from utils.command import bot, ADMIN_USER_IDS, is_admin
from utils.referral import (
    get_or_create_referral_code, 
    get_referral_stats, 
    get_wallet_address, 
    set_wallet_address,
    process_withdrawal_request,
    build_withdrawal_audit_payload,
    get_eligible_referral_users,
    mark_referral_payout_paid
)
from utils.translations import BUTTON_TRANSLATIONS, get_message_text, get_button_text
from utils.language import get_user_language

ADMIN_REFERRAL_PAGE_SIZE = 8

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

def _admin_referral_page_count(total_items):
    if total_items <= 0:
        return 1
    return (total_items + ADMIN_REFERRAL_PAGE_SIZE - 1) // ADMIN_REFERRAL_PAGE_SIZE

def _admin_referral_clamped_page(page, total_items):
    try:
        page = int(page)
    except (TypeError, ValueError):
        page = 0
    total_pages = _admin_referral_page_count(total_items)
    return max(0, min(page, total_pages - 1))

def _build_admin_referral_list(page=0):
    eligible_users = get_eligible_referral_users()
    page = _admin_referral_clamped_page(page, len(eligible_users))
    total_pages = _admin_referral_page_count(len(eligible_users))
    start = page * ADMIN_REFERRAL_PAGE_SIZE
    page_users = eligible_users[start:start + ADMIN_REFERRAL_PAGE_SIZE]
    total_due = sum(user["available_balance"] for user in eligible_users)

    text = (
        "💰 *Referral Payouts*\n\n"
        f"Eligible Users: *{len(eligible_users)}*\n"
        f"Total Available: *${total_due:.2f}*\n"
        f"Page: *{page + 1}/{total_pages}*\n\n"
    )

    markup = types.InlineKeyboardMarkup(row_width=1)

    if not page_users:
        text += "No users currently have at least $2.00 available."
    else:
        text += "Select a user to review:"
        for user in page_users:
            wallet_icon = "✅" if user["has_wallet"] else "⚠️"
            button_text = (
                f"{user['user_id']} - ${user['available_balance']:.2f} "
                f"- {user['invited_count']} invites - {wallet_icon}"
            )
            markup.add(types.InlineKeyboardButton(
                button_text,
                callback_data=f"admin_referral:detail:{user['user_id']}:{page}"
            ))

    nav_buttons = []
    if page > 0:
        nav_buttons.append(types.InlineKeyboardButton("⬅️ Prev", callback_data=f"admin_referral:list:{page - 1}"))
    if page < total_pages - 1:
        nav_buttons.append(types.InlineKeyboardButton("Next ➡️", callback_data=f"admin_referral:list:{page + 1}"))
    if nav_buttons:
        markup.add(*nav_buttons)

    markup.add(types.InlineKeyboardButton("🔄 Refresh", callback_data=f"admin_referral:list:{page}"))
    return text, markup, page

def _build_admin_referral_detail(target_user_id, return_page=0):
    stats = get_referral_stats(target_user_id)
    wallet = get_wallet_address(target_user_id)
    available_balance = float(stats.get("available_balance", 0) or 0)
    total_earnings = float(stats.get("total_earnings", 0) or 0)
    invited_count = int(stats.get("count", 0) or 0)
    wallet_display = f"`{wallet}`" if wallet else "Not set"
    eligible_text = "Yes" if available_balance >= 2.0 else "No"

    text = (
        "💰 *Referral Payout Detail*\n\n"
        f"User ID: `{target_user_id}`\n"
        f"Invited Users: *{invited_count}*\n"
        f"Total Earnings: *${total_earnings:.2f}*\n"
        f"Available Balance: *${available_balance:.2f}*\n"
        f"Eligible: *{eligible_text}*\n"
        f"Wallet: {wallet_display}"
    )

    markup = types.InlineKeyboardMarkup(row_width=2)
    if available_balance >= 2.0 and wallet:
        markup.add(types.InlineKeyboardButton(
            "✅ Mark Paid",
            callback_data=f"admin_referral:confirm:{target_user_id}:{return_page}"
        ))
    markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data=f"admin_referral:list:{return_page}"))
    markup.add(types.InlineKeyboardButton("🔄 Refresh", callback_data=f"admin_referral:detail:{target_user_id}:{return_page}"))
    return text, markup

def _render_admin_referral_list(chat_id, message_id, page=0):
    text, markup, _ = _build_admin_referral_list(page)
    bot.edit_message_text(
        text,
        chat_id=chat_id,
        message_id=message_id,
        reply_markup=markup,
        parse_mode="Markdown"
    )

def _render_admin_referral_detail(chat_id, message_id, target_user_id, return_page=0):
    text, markup = _build_admin_referral_detail(target_user_id, return_page)
    bot.edit_message_text(
        text,
        chat_id=chat_id,
        message_id=message_id,
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda message: is_admin(message.from_user.id) and message.text == '💰 Referral Payouts')
def admin_referral_payouts_menu(message):
    text, markup, _ = _build_admin_referral_list(0)
    bot.reply_to(message, text, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_referral:"))
def handle_admin_referral_payouts(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ Unauthorized", show_alert=True)
        return

    parts = call.data.split(":")
    action = parts[1] if len(parts) > 1 else ""

    if action == "list" and len(parts) == 3:
        _render_admin_referral_list(call.message.chat.id, call.message.message_id, parts[2])
        bot.answer_callback_query(call.id)
        return

    if action == "detail" and len(parts) == 4:
        _render_admin_referral_detail(call.message.chat.id, call.message.message_id, parts[2], parts[3])
        bot.answer_callback_query(call.id)
        return

    if action == "confirm" and len(parts) == 4:
        target_user_id = parts[2]
        return_page = parts[3]
        stats = get_referral_stats(target_user_id)
        wallet = get_wallet_address(target_user_id)
        available_balance = float(stats.get("available_balance", 0) or 0)

        if available_balance < 2.0 or not wallet:
            reason = "Wallet missing." if not wallet else "User is no longer eligible."
            bot.answer_callback_query(call.id, reason, show_alert=True)
            _render_admin_referral_list(call.message.chat.id, call.message.message_id, return_page)
            return

        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("✅ Confirm Paid", callback_data=f"admin_referral:pay:{target_user_id}:{return_page}"),
            types.InlineKeyboardButton("❌ Cancel", callback_data=f"admin_referral:detail:{target_user_id}:{return_page}")
        )
        bot.edit_message_text(
            f"Confirm referral payout for user `{target_user_id}`?\n\nAmount: *${available_balance:.2f}*\nWallet: `{wallet}`",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=markup,
            parse_mode="Markdown"
        )
        bot.answer_callback_query(call.id)
        return

    if action == "pay" and len(parts) == 4:
        target_user_id = parts[2]
        return_page = parts[3]
        success, result = mark_referral_payout_paid(target_user_id, call.from_user.id)

        if not success:
            bot.answer_callback_query(call.id, result, show_alert=True)
            _render_admin_referral_list(call.message.chat.id, call.message.message_id, return_page)
            return

        bot.answer_callback_query(call.id, f"Marked paid: ${result['amount']:.2f}")
        _render_admin_referral_list(call.message.chat.id, call.message.message_id, return_page)
        return

    bot.answer_callback_query(call.id, "Invalid action.", show_alert=True)

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
    telegram_username = str(call.from_user.username or "").strip().lstrip("@")

    if not telegram_username:
        bot.answer_callback_query(
            call.id,
            get_message_text(language, "withdraw_requires_telegram_username"),
            show_alert=True
        )
        return
    
    success, result = process_withdrawal_request(user_id)
    
    if success:
        amount = result["amount"]
        wallet = result["wallet"]
        audit_payload = build_withdrawal_audit_payload(user_id, telegram_username, result)
        
        bot.answer_callback_query(call.id, "Request sent!")
        bot.edit_message_text(
            chat_id=call.message.chat.id, 
            message_id=call.message.message_id, 
            text=get_message_text(language, "withdraw_success"),
            parse_mode="Markdown"
        )
        
        # Notify Admins
        notify_admins_withdrawal(user_id, telegram_username, amount, wallet, result, audit_payload)
    else:
        bot.answer_callback_query(call.id, "Error!")
        bot.send_message(call.message.chat.id, get_message_text(language, "withdraw_failed").format(reason=result))
        show_referral_menu(user_id, call.message.chat.id)

def notify_admins_withdrawal(user_id, telegram_username, amount, wallet, withdrawal_data, audit_payload):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ Mark as Paid", callback_data=f"admin_pay_ref:{user_id}"))
    
    msg_text = get_message_text("en", "admin_withdraw_request").format(
        user_id=user_id,
        username=telegram_username,
        amount=amount,
        wallet=wallet,
        invited_count=withdrawal_data.get("invited_count", 0),
        total_earnings=withdrawal_data.get("total_earnings", 0),
        available_balance_after=withdrawal_data.get("available_balance_after", 0),
        requested_at=withdrawal_data.get("requested_at", "")
    )
    filename_time = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"withdrawal_request_{user_id}_{filename_time}.json"
    json_bytes = json.dumps(audit_payload, indent=2, ensure_ascii=False).encode("utf-8")
    
    for admin_id in ADMIN_USER_IDS:
        try:
            bot.send_message(admin_id, msg_text, reply_markup=markup, parse_mode="Markdown")
            json_file = io.BytesIO(json_bytes)
            json_file.name = filename
            bot.send_document(admin_id, json_file, caption=f"Withdrawal audit data for user {user_id}")
        except Exception as e:
            print(f"Failed to notify admin {admin_id}: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_pay_ref:"))
def handle_admin_mark_paid(call):
    user_id_admin = call.from_user.id
    if not is_admin(user_id_admin):
        return

    target_user_id = call.data.split(":", 1)[1]
    success, result = mark_referral_payout_paid(target_user_id, user_id_admin)
    audit_note = ""
    if success:
        audit_note = f"\nAudit recorded: `${result['amount']:.2f}`"
    else:
        audit_note = f"\nAudit not recorded: {result}"
    
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"{call.message.text}\n\n✅ **Paid by Admin {user_id_admin}**{audit_note}",
        reply_markup=None,
        parse_mode="Markdown"
    )
    bot.answer_callback_query(call.id, "Marked as paid." if success else f"Marked in message only: {result}")
