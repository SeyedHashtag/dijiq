from telebot import types
from utils.command import bot, is_admin
from utils.common import create_main_markup
from utils.payment_records import load_payments
from utils.receipt_checker import (
    RECEIPT_TYPE_REGULAR,
    RECEIPT_TYPE_SETTLEMENT,
    add_checker_settlement,
    build_receipt_checker_stats,
    calculate_checker_share_amount_toman,
    get_checker_settlements,
    get_receipt_checker_types,
    get_receipt_checker_user_id,
    get_receipt_checker_share_percent,
    get_receipt_type_label,
    normalize_toman_amount,
    normalize_receipt_types,
    parse_receipt_checker_share_percent,
)
from utils.currency_format import format_toman_amount
import os
import datetime
from dotenv import load_dotenv, set_key

# FIX: Go up one level ('..') to find the root .env file
# This prevents creating a duplicate .env inside your handlers/utils folder
env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.env'))
CHECKER_SETTLEMENT_INPUT_STATE = {}

def create_cancel_markup():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(types.KeyboardButton("❌ Cancel"))
    return markup

def create_payment_method_selection_markup():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(types.KeyboardButton("💳 Crypto"), types.KeyboardButton("💳 Main Card"))
    markup.row(types.KeyboardButton("💳 Checker Card"), types.KeyboardButton("🔀 Card to Card Mode"))
    markup.row(types.KeyboardButton("💱 Exchange Rate"), types.KeyboardButton("🏢 Reseller Settlement Threshold"))
    markup.row(types.KeyboardButton("👤 Receipt Checker"), types.KeyboardButton("📋 Checker Receipt Types"))
    markup.row(types.KeyboardButton("📊 Checker Stats"), types.KeyboardButton("💸 Checker Share"))
    markup.row(types.KeyboardButton("❌ Cancel"))
    return markup

@bot.message_handler(func=lambda message: is_admin(message.from_user.id) and message.text == '💳 Payment Settings')
def payment_settings(message):
    msg = bot.reply_to(
        message, 
        "Please select a payment method to configure:",
        reply_markup=create_payment_method_selection_markup()
    )
    bot.register_next_step_handler(msg, process_payment_method_selection)

def process_payment_method_selection(message):
    if message.text == "❌ Cancel":
        bot.reply_to(message, "Operation canceled.", reply_markup=create_main_markup(is_admin=True))
        return

    if message.text == "💳 Crypto":
        setup_crypto(message)
    elif message.text in ("💳 Card to Card (Iran)", "💳 Main Card"):
        setup_card_to_card(message, "main")
    elif message.text == "💳 Checker Card":
        setup_card_to_card(message, "checker")
    elif message.text == "🔀 Card to Card Mode":
        setup_card_to_card_mode(message)
    elif message.text == "💱 Exchange Rate":
        setup_exchange_rate(message)
    elif message.text == "🏢 Reseller Settlement Threshold":
        setup_reseller_settlement_threshold(message)
    elif message.text == "👤 Receipt Checker":
        setup_receipt_checker(message)
    elif message.text == "📋 Checker Receipt Types":
        setup_receipt_checker_types(message)
    elif message.text == "📊 Checker Stats":
        show_receipt_checker_stats(message)
    elif message.text == "💸 Checker Share":
        setup_receipt_checker_share(message)
    else:
        bot.reply_to(message, "Invalid selection. Please try again.", reply_markup=create_main_markup(is_admin=True))

def setup_crypto(message):
    load_dotenv(env_path, override=True)
    
    current_merchant_id = os.getenv('CRYPTO_MERCHANT_ID')
    current_api_key = os.getenv('CRYPTO_API_KEY')
    
    status_text = "Current Crypto Settings:\n"
    status_text += f"Merchant ID: {'✅ Configured' if current_merchant_id else '❌ Not configured'}\n"
    status_text += f"API Key: {'✅ Configured' if current_api_key else '❌ Not configured'}\n\n"
    status_text += "Please enter your Crypto Merchant ID:"
    
    msg = bot.reply_to(
        message, 
        status_text,
        reply_markup=create_cancel_markup()
    )
    bot.register_next_step_handler(msg, process_merchant_id)

def process_merchant_id(message):
    if message.text == "❌ Cancel":
        bot.reply_to(message, "Operation canceled.", reply_markup=create_main_markup(is_admin=True))
        return

    merchant_id = message.text.strip()
    
    if not merchant_id:
        msg = bot.reply_to(
            message,
            "Merchant ID cannot be empty. Please enter a valid Merchant ID:",
            reply_markup=create_cancel_markup()
        )
        bot.register_next_step_handler(msg, process_merchant_id)
        return

    msg = bot.reply_to(
        message,
        "Now enter your Crypto API Key:",
        reply_markup=create_cancel_markup()
    )
    bot.register_next_step_handler(msg, process_api_key, merchant_id)

def process_api_key(message, merchant_id):
    if message.text == "❌ Cancel":
        bot.reply_to(message, "Operation canceled.", reply_markup=create_main_markup(is_admin=True))
        return

    api_key = message.text.strip()
    
    if not api_key:
        msg = bot.reply_to(
            message,
            "API Key cannot be empty. Please enter a valid API Key:",
            reply_markup=create_cancel_markup()
        )
        bot.register_next_step_handler(msg, process_api_key, merchant_id)
        return

    try:
        if not os.path.exists(env_path):
            with open(env_path, 'w') as f:
                pass
        
        # Write to file
        set_key(env_path, 'CRYPTO_MERCHANT_ID', merchant_id)
        set_key(env_path, 'CRYPTO_API_KEY', api_key)
        
        # Reload immediately with override=True so the bot uses new values
        load_dotenv(env_path, override=True)
        
        bot.reply_to(
            message,
            "✅ Crypto credentials have been updated successfully!",
            reply_markup=create_main_markup(is_admin=True)
        )
    except Exception as e:
        bot.reply_to(
            message,
            f"❌ Error updating Crypto credentials: {str(e)}",
            reply_markup=create_main_markup(is_admin=True)
        )

def setup_card_to_card(message, slot="main"):
    load_dotenv(env_path, override=True)
    env_key = 'CARD_TO_CARD_CHECKER_NUMBER' if slot == "checker" else 'CARD_TO_CARD_NUMBER'
    slot_label = "Checker" if slot == "checker" else "Main"
    current_card_number = os.getenv(env_key)
    
    status_text = f"Current {slot_label} Card to Card Settings:\n"
    status_text += f"{slot_label} Card Number: {current_card_number if current_card_number else '❌ Not configured'}\n\n"
    status_text += f"Please enter the {slot_label.lower()} card number for 'Card to Card' payments:"
    
    msg = bot.reply_to(
        message, 
        status_text,
        reply_markup=create_cancel_markup()
    )
    bot.register_next_step_handler(msg, process_card_to_card_number, slot)

def process_card_to_card_number(message, slot="main"):
    if message.text == "❌ Cancel":
        bot.reply_to(message, "Operation canceled.", reply_markup=create_main_markup(is_admin=True))
        return

    card_number = message.text.strip()
    env_key = 'CARD_TO_CARD_CHECKER_NUMBER' if slot == "checker" else 'CARD_TO_CARD_NUMBER'
    slot_label = "Checker" if slot == "checker" else "Main"
    
    if not card_number:
        msg = bot.reply_to(
            message,
            "Card number cannot be empty. Please enter a valid card number:",
            reply_markup=create_cancel_markup()
        )
        bot.register_next_step_handler(msg, process_card_to_card_number, slot)
        return

    try:
        if not os.path.exists(env_path):
            with open(env_path, 'w') as f:
                pass
        
        set_key(env_path, env_key, card_number)
        load_dotenv(env_path, override=True)
        
        bot.reply_to(
            message,
            f"✅ {slot_label} Card to Card number has been updated successfully!",
            reply_markup=create_main_markup(is_admin=True)
        )
    except Exception as e:
        bot.reply_to(
            message,
            f"❌ Error updating {slot_label} Card to Card number: {str(e)}",
            reply_markup=create_main_markup(is_admin=True)
        )


def setup_receipt_checker(message):
    load_dotenv(env_path, override=True)
    current_checker_id = os.getenv('RECEIPT_CHECKER_USER_ID', '').strip()
    status_text = "Current Receipt Checker Settings:\n"
    status_text += f"Checker User ID: {current_checker_id if current_checker_id else '❌ Not configured'}\n\n"
    status_text += "Please enter the numeric Telegram user ID for the receipt checker:"

    msg = bot.reply_to(message, status_text, reply_markup=create_cancel_markup())
    bot.register_next_step_handler(msg, process_receipt_checker_id)


def process_receipt_checker_id(message):
    if message.text == "❌ Cancel":
        bot.reply_to(message, "Operation canceled.", reply_markup=create_main_markup(is_admin=True))
        return

    checker_id = message.text.strip()
    if not checker_id.isdigit():
        msg = bot.reply_to(
            message,
            "Checker user ID must be numeric. Please enter a valid Telegram user ID:",
            reply_markup=create_cancel_markup()
        )
        bot.register_next_step_handler(msg, process_receipt_checker_id)
        return

    try:
        if not os.path.exists(env_path):
            with open(env_path, 'w') as f:
                pass
        set_key(env_path, 'RECEIPT_CHECKER_USER_ID', checker_id)
        load_dotenv(env_path, override=True)
        bot.reply_to(
            message,
            "✅ Receipt checker has been updated successfully!",
            reply_markup=create_main_markup(is_admin=True)
        )
    except Exception as e:
        bot.reply_to(
            message,
            f"❌ Error updating receipt checker: {str(e)}",
            reply_markup=create_main_markup(is_admin=True)
        )


def setup_receipt_checker_types(message):
    checker_id = get_receipt_checker_user_id()
    current_types = get_receipt_checker_types()
    current_label = ", ".join(get_receipt_type_label(t) for t in current_types) if current_types else "❌ None"
    checker_label = checker_id if checker_id is not None else "❌ Not configured"
    text = (
        "📋 Checker Receipt Types\n\n"
        f"Checker User ID: {checker_label}\n"
        f"Current Types: {current_label}\n\n"
        "Select which receipts should also go to the checker:"
    )
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("Regular Customers", callback_data="checker_types:regular"),
        types.InlineKeyboardButton("Reseller Settlements", callback_data="checker_types:settlement"),
        types.InlineKeyboardButton("Both", callback_data="checker_types:both"),
        types.InlineKeyboardButton("None", callback_data="checker_types:none"),
    )
    bot.reply_to(message, text, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith('checker_types:'))
def handle_receipt_checker_type_selection(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, text="Not authorized.")
        return

    selection = call.data.split(':')[1]
    if selection == "both":
        receipt_types = [RECEIPT_TYPE_REGULAR, RECEIPT_TYPE_SETTLEMENT]
    elif selection == "none":
        receipt_types = []
    else:
        receipt_types = normalize_receipt_types(selection)

    try:
        if not os.path.exists(env_path):
            with open(env_path, 'w') as f:
                pass
        set_key(env_path, 'RECEIPT_CHECKER_TYPES', ",".join(receipt_types))
        load_dotenv(env_path, override=True)
        label = ", ".join(get_receipt_type_label(t) for t in receipt_types) if receipt_types else "None"
        bot.edit_message_text(
            f"✅ Checker receipt types updated to: {label}",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id
        )
    except Exception as e:
        bot.answer_callback_query(call.id, text=f"Error: {str(e)}")


def setup_receipt_checker_share(message):
    current_percent = get_receipt_checker_share_percent()
    text = (
        "💸 Checker Share\n\n"
        f"Current Share: {current_percent:.2f}%\n\n"
        "Enter the checker share percentage from approved checker-routed receipts (0 to 100):"
    )
    msg = bot.reply_to(message, text, reply_markup=create_cancel_markup())
    bot.register_next_step_handler(msg, process_receipt_checker_share)


def process_receipt_checker_share(message):
    if message.text == "❌ Cancel":
        bot.reply_to(message, "Operation canceled.", reply_markup=create_main_markup(is_admin=True))
        return

    raw_value = message.text.strip()
    try:
        percent = float(raw_value)
        if percent < 0 or percent > 100:
            raise ValueError("Checker share must be between 0 and 100.")
    except (TypeError, ValueError):
        msg = bot.reply_to(
            message,
            "Invalid percentage. Please enter a number from 0 to 100:",
            reply_markup=create_cancel_markup()
        )
        bot.register_next_step_handler(msg, process_receipt_checker_share)
        return

    percent = parse_receipt_checker_share_percent(percent)

    try:
        if not os.path.exists(env_path):
            with open(env_path, 'w') as f:
                pass
        set_key(env_path, 'RECEIPT_CHECKER_SHARE_PERCENT', f"{percent:.2f}")
        load_dotenv(env_path, override=True)
        bot.reply_to(
            message,
            f"✅ Checker share has been updated to {percent:.2f}%.",
            reply_markup=create_main_markup(is_admin=True)
        )
    except Exception as e:
        bot.reply_to(
            message,
            f"❌ Error updating checker share: {str(e)}",
            reply_markup=create_main_markup(is_admin=True)
        )


def _format_usd(value):
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return "0.00"


def _format_toman(value):
    try:
        return format_toman_amount(value)
    except Exception:
        return "0"


def _parse_toman_amount(value):
    try:
        return float(str(value).strip().replace(',', ''))
    except (TypeError, ValueError):
        return None


def _format_share_percent(value):
    try:
        percent = float(value)
    except (TypeError, ValueError):
        percent = 0.0
    return str(int(percent)) if percent.is_integer() else f"{percent:.2f}"


def _format_checker_stats_text(stats, title="📊 Receipt Checker Stats", include_checker_details=True):
    checker_id = stats.get('checker_id')
    checker_types = stats.get('checker_types') or []
    type_label = ", ".join(get_receipt_type_label(t) for t in checker_types) if checker_types else "None"
    checker_label = checker_id if checker_id is not None else "Not configured"
    share_percent_label = _format_share_percent(stats.get('share_percent'))
    text = f"{title}\n\n"

    if not include_checker_details:
        text += (
            f"Paid (30 days): {_format_toman(stats.get('paid_last_30_days'))} T\n"
            f"Open Account: {_format_toman(stats.get('open_account_total'))} T\n"
            f"Balance ({share_percent_label}%): {_format_toman(stats.get('unpaid_total'))} T\n\n"
        )
    else:
        text += (
            f"Checker User ID: {checker_label}\n"
            f"Enabled Types: {type_label}\n"
            f"Share: {stats.get('share_percent', 0):.2f}%\n\n"
        )

        text += (
            "Financial Summary\n"
            f"Open Account Base: {_format_toman(stats.get('open_account_total'))} Tomans\n"
            f"Checker Balance ({share_percent_label}%): {_format_toman(stats.get('unpaid_total'))} Tomans\n"
            f"Paid to Checker: {_format_toman(stats.get('paid_total'))} Tomans\n"
            f"Paid Last 30 Days: {_format_toman(stats.get('paid_last_30_days'))} Tomans\n"
            f"Approved Total: {_format_toman(stats.get('approved_total'))} Tomans\n\n"
        )

        text += "Receipt Types\n"
        for receipt_type in (RECEIPT_TYPE_REGULAR, RECEIPT_TYPE_SETTLEMENT):
            item = stats['types'][receipt_type]
            text += (
                f"{get_receipt_type_label(receipt_type)}\n"
                f"Pending: {item['pending']}\n"
                f"Approved: {item['approved']} ({_format_toman(item['approved_total'])} Tomans)\n"
                f"Rejected: {item['rejected']}\n"
                f"Checker Share: {_format_toman(item['checker_owed_total'])} Tomans\n\n"
            )

        if stats.get('approved_total_usd') or stats.get('owed_total_usd') or stats.get('paid_total_usd'):
            text += (
                "Legacy USD\n"
                f"Legacy USD Approved: ${_format_usd(stats.get('approved_total_usd'))}\n"
                f"Legacy USD Owed: ${_format_usd(stats.get('owed_total_usd'))}\n"
                f"Legacy USD Paid: ${_format_usd(stats.get('paid_total_usd'))}\n"
            )
        if stats.get('legacy_estimated_count'):
            text += f"Legacy Estimated Receipts: {stats.get('legacy_estimated_count')}\n"
        text += "\n"

    latest_review = stats.get('latest_review')
    if latest_review:
        text += (
            "Latest Review\n"
            f"Payment ID: {latest_review.get('payment_id')}\n"
            f"Type: {get_receipt_type_label(latest_review.get('receipt_type'))}\n"
            f"Action: {latest_review.get('reviewed_action', 'N/A')}\n"
            f"Reviewer ID: {latest_review.get('reviewed_by_user_id', 'N/A')}\n"
            f"Time: {latest_review.get('reviewed_at')}"
        )
    else:
        text += "Latest Review\nNo routed receipts reviewed yet."

    return text


def _build_checker_stats_markup(is_admin_view):
    markup = types.InlineKeyboardMarkup(row_width=1)
    if is_admin_view:
        markup.add(
            types.InlineKeyboardButton("💸 Settle Checker", callback_data="checker_settlement:start"),
            types.InlineKeyboardButton("📜 Settlement History", callback_data="checker_settlement:history"),
            types.InlineKeyboardButton("❌ Cancel", callback_data="checker_settlement:cancel"),
        )
    return markup


def show_receipt_checker_stats(message):
    stats = build_receipt_checker_stats(load_payments())
    bot.reply_to(
        message,
        _format_checker_stats_text(stats),
        reply_markup=_build_checker_stats_markup(is_admin_view=True)
    )


@bot.callback_query_handler(func=lambda call: call.data == 'checker_stats:my')
def handle_my_checker_stats(call):
    checker_id = get_receipt_checker_user_id()
    if checker_id is None or int(call.from_user.id) != checker_id:
        bot.answer_callback_query(call.id, text="Not authorized.")
        return

    stats = build_receipt_checker_stats(load_payments(), checker_id=checker_id)
    bot.send_message(
        call.message.chat.id,
        _format_checker_stats_text(stats, title="📊 My Stats", include_checker_details=False)
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith('checker_settlement:'))
def handle_checker_settlement_callback(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, text="Not authorized.")
        return

    action = call.data.split(':', 1)[1]
    if action == 'cancel':
        CHECKER_SETTLEMENT_INPUT_STATE.pop(call.from_user.id, None)
        try:
            bot.edit_message_reply_markup(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=None
            )
        except Exception:
            pass
        bot.answer_callback_query(call.id, text="Canceled.")
        return

    stats = build_receipt_checker_stats(load_payments())

    if action == 'history':
        settlements = get_checker_settlements(stats.get('checker_id'))
        if not settlements:
            bot.answer_callback_query(call.id, text="No checker settlement history.")
            return
        text = "📜 Checker Settlement History\n\n"
        for item in settlements[-10:][::-1]:
            amount_toman = item.get('amount_toman')
            open_account_amount_toman = item.get('open_account_amount_toman')
            unpaid_after_toman = item.get('unpaid_after_toman')
            if amount_toman is not None:
                if open_account_amount_toman is not None:
                    amount_line = (
                        f"Open Account Base: {_format_toman(open_account_amount_toman)} Tomans\n"
                        f"Checker Payout: {_format_toman(amount_toman)} Tomans\n"
                    )
                else:
                    amount_line = f"Checker Payout: {_format_toman(amount_toman)} Tomans\n"
            else:
                amount_line = f"Amount: ${_format_usd(item.get('amount'))} (legacy USD)\n"
            if unpaid_after_toman is not None:
                unpaid_after_line = f"Unpaid After: {_format_toman(unpaid_after_toman)} Tomans\n\n"
            else:
                unpaid_after_line = f"Unpaid After: ${_format_usd(item.get('unpaid_after'))} (legacy USD)\n\n"
            text += (
                f"ID: {item.get('id')}\n"
                f"{amount_line}"
                f"Admin: {item.get('admin_user_id')}\n"
                f"Time: {item.get('created_at')}\n"
                f"{unpaid_after_line}"
            )
        bot.send_message(call.message.chat.id, text)
        return

    if action == 'start':
        unpaid_total = float(stats.get('unpaid_total', 0.0) or 0.0)
        open_account_total = float(stats.get('open_account_total', 0.0) or 0.0)
        if unpaid_total <= 0:
            bot.answer_callback_query(call.id, text="No unpaid checker balance.")
            return
        if open_account_total <= 0:
            bot.answer_callback_query(call.id, text="No open account base available.")
            return
        CHECKER_SETTLEMENT_INPUT_STATE[call.from_user.id] = {
            'state': 'waiting_open_account_amount',
            'checker_id': stats.get('checker_id'),
            'unpaid_total': unpaid_total,
            'open_account_total': open_account_total,
        }
        bot.send_message(
            call.message.chat.id,
            f"Enter Open Account base amount up to {_format_toman(open_account_total)} Tomans:",
            reply_markup=create_cancel_markup()
        )
        return

    if action.startswith('confirm:'):
        raw_base_amount = action.split(':', 1)[1]
        base_amount = _parse_toman_amount(raw_base_amount)
        if base_amount is None:
            bot.answer_callback_query(call.id, text="Invalid Open Account amount.")
            return
        base_amount = normalize_toman_amount(base_amount)
        unpaid_total = float(stats.get('unpaid_total', 0.0) or 0.0)
        open_account_total = float(stats.get('open_account_total', 0.0) or 0.0)
        if base_amount <= 0 or base_amount > open_account_total:
            bot.answer_callback_query(call.id, text="Open Account amount is outside the available base.")
            return
        payout_amount = calculate_checker_share_amount_toman(base_amount, stats.get('share_percent'))
        if payout_amount <= 0 or payout_amount > unpaid_total:
            bot.answer_callback_query(call.id, text="Calculated checker payout is outside the unpaid balance.")
            return
        checkpoint = add_checker_settlement(
            payout_amount,
            call.from_user.id,
            stats,
            checker_id=stats.get('checker_id'),
            open_account_amount=base_amount,
        )
        CHECKER_SETTLEMENT_INPUT_STATE.pop(call.from_user.id, None)
        bot.edit_message_text(
            (
                "✅ Checker settlement checkpoint saved.\n\n"
                f"Open Account Base: {_format_toman(checkpoint.get('open_account_amount_toman'))} Tomans\n"
                f"Checker Payout: {_format_toman(checkpoint.get('amount_toman'))} Tomans\n"
                f"Unpaid Before: {_format_toman(checkpoint.get('unpaid_before_toman'))} Tomans\n"
                f"Unpaid After: {_format_toman(checkpoint.get('unpaid_after_toman'))} Tomans\n"
                f"Checkpoint ID: {checkpoint.get('id')}"
            ),
            chat_id=call.message.chat.id,
            message_id=call.message.message_id
        )


@bot.message_handler(func=lambda message: is_admin(message.from_user.id) and CHECKER_SETTLEMENT_INPUT_STATE.get(message.from_user.id, {}).get('state') == 'waiting_open_account_amount')
def process_checker_settlement_amount(message):
    if message.text == "❌ Cancel":
        CHECKER_SETTLEMENT_INPUT_STATE.pop(message.from_user.id, None)
        bot.reply_to(message, "Operation canceled.", reply_markup=create_main_markup(is_admin=True))
        return

    base_amount = _parse_toman_amount(message.text)
    if base_amount is None:
        bot.reply_to(message, "Invalid amount. Please enter a numeric Open Account base amount:", reply_markup=create_cancel_markup())
        return
    base_amount = normalize_toman_amount(base_amount)

    stats = build_receipt_checker_stats(load_payments())
    unpaid_total = float(stats.get('unpaid_total', 0.0) or 0.0)
    open_account_total = float(stats.get('open_account_total', 0.0) or 0.0)
    if base_amount <= 0 or base_amount > open_account_total:
        bot.reply_to(
            message,
            f"Open Account base must be greater than 0 and no more than {_format_toman(open_account_total)} Tomans.",
            reply_markup=create_cancel_markup()
        )
        return
    payout_amount = calculate_checker_share_amount_toman(base_amount, stats.get('share_percent'))
    if payout_amount <= 0 or payout_amount > unpaid_total:
        bot.reply_to(
            message,
            "Calculated checker payout must be greater than 0 and no more than the current checker balance.",
            reply_markup=create_cancel_markup()
        )
        return

    unpaid_after = max(0.0, unpaid_total - payout_amount)
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("✅ Confirm", callback_data=f"checker_settlement:confirm:{base_amount:.0f}"),
        types.InlineKeyboardButton("❌ Cancel", callback_data="checker_settlement:cancel"),
    )
    bot.reply_to(
        message,
        (
            "Confirm checker settlement checkpoint:\n\n"
            f"Open Account Base: {_format_toman(base_amount)} Tomans\n"
            f"Checker Payout ({_format_share_percent(stats.get('share_percent'))}%): {_format_toman(payout_amount)} Tomans\n"
            f"Approved Total Snapshot: {_format_toman(stats.get('approved_total'))} Tomans\n"
            f"Unpaid Before: {_format_toman(unpaid_total)} Tomans\n"
            f"Unpaid After: {_format_toman(unpaid_after)} Tomans"
        ),
        reply_markup=markup
    )


def setup_exchange_rate(message):
    load_dotenv(env_path, override=True)
    current_exchange_rate = os.getenv('EXCHANGE_RATE')
    
    status_text = "Current Exchange Rate Settings:\n"
    status_text += f"Exchange Rate (USD to Toman): {current_exchange_rate if current_exchange_rate else '❌ Not configured'}\n\n"
    status_text += "Please enter the exchange rate (e.g., 100 for 1 USD = 100 Tomans):"
    
    msg = bot.reply_to(
        message,
        status_text,
        reply_markup=create_cancel_markup()
    )
    bot.register_next_step_handler(msg, process_exchange_rate)


def process_exchange_rate(message):
    if message.text == "❌ Cancel":
        bot.reply_to(message, "Operation canceled.", reply_markup=create_main_markup(is_admin=True))
        return

    exchange_rate = message.text.strip()
    
    if not exchange_rate:
        msg = bot.reply_to(
            message,
            "Exchange rate cannot be empty. Please enter a valid exchange rate:",
            reply_markup=create_cancel_markup()
        )
        bot.register_next_step_handler(msg, process_exchange_rate)
        return

    if not exchange_rate.isdigit():
        msg = bot.reply_to(
            message,
            "Exchange rate must be a number. Please enter a valid exchange rate:",
            reply_markup=create_cancel_markup()
        )
        bot.register_next_step_handler(msg, process_exchange_rate)
        return

    try:
        if not os.path.exists(env_path):
            with open(env_path, 'w') as f:
                pass
        
        set_key(env_path, 'EXCHANGE_RATE', exchange_rate)
        load_dotenv(env_path, override=True)
        
        bot.reply_to(
            message,
            "✅ Exchange rate has been updated successfully!",
            reply_markup=create_main_markup(is_admin=True)
        )
    except Exception as e:
        bot.reply_to(
            message,
            f"❌ Error updating exchange rate: {str(e)}",
            reply_markup=create_main_markup(is_admin=True)
        )


MODE_LABELS = {
    'on': '✅ On (All Customers)',
    'off': '❌ Off (Disabled)',
    'previous_customers': '👤 Previous Customers Only'
}

def setup_card_to_card_mode(message):
    load_dotenv(env_path, override=True)
    current_mode = os.getenv('CARD_TO_CARD_MODE', 'on')
    current_label = MODE_LABELS.get(current_mode, MODE_LABELS['on'])

    status_text = (
        "🔀 Card to Card Mode Settings\n\n"
        f"Current Mode: {current_label}\n\n"
        "Select a new mode:"
    )

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("✅ On (All Customers)", callback_data="c2c_mode:on"),
        types.InlineKeyboardButton("❌ Off (Disabled)", callback_data="c2c_mode:off"),
        types.InlineKeyboardButton("👤 Previous Customers Only", callback_data="c2c_mode:previous_customers")
    )

    bot.reply_to(
        message,
        status_text,
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('c2c_mode:'))
def handle_card_to_card_mode_selection(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, text="Not authorized.")
        return

    mode = call.data.split(':')[1]
    if mode not in ('on', 'off', 'previous_customers'):
        bot.answer_callback_query(call.id, text="Invalid mode.")
        return

    try:
        if not os.path.exists(env_path):
            with open(env_path, 'w') as f:
                pass

        set_key(env_path, 'CARD_TO_CARD_MODE', mode)
        load_dotenv(env_path, override=True)

        mode_label = MODE_LABELS.get(mode, mode)
        bot.edit_message_text(
            f"✅ Card to Card mode updated to: {mode_label}",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id
        )
    except Exception as e:
        bot.answer_callback_query(call.id, text=f"Error: {str(e)}")

def setup_reseller_settlement_threshold(message):
    load_dotenv(env_path, override=True)
    current_threshold = os.getenv('RESELLER_SETTLEMENT_THRESHOLD', '2.0')
    
    status_text = "Current Reseller Settlement Threshold:\n"
    status_text += f"Amount: {current_threshold} USD\n\n"
    status_text += "Please enter the new threshold amount in USD (e.g., 2.0 or 5.5):"
    
    msg = bot.reply_to(
        message,
        status_text,
        reply_markup=create_cancel_markup()
    )
    bot.register_next_step_handler(msg, process_reseller_settlement_threshold)

def process_reseller_settlement_threshold(message):
    if message.text == "❌ Cancel":
        bot.reply_to(message, "Operation canceled.", reply_markup=create_main_markup(is_admin=True))
        return

    threshold_str = message.text.strip()
    
    if not threshold_str:
        msg = bot.reply_to(
            message,
            "Threshold cannot be empty. Please enter a valid number:",
            reply_markup=create_cancel_markup()
        )
        bot.register_next_step_handler(msg, process_reseller_settlement_threshold)
        return

    try:
        threshold_val = float(threshold_str)
        if threshold_val < 0:
            raise ValueError("Threshold cannot be negative.")
    except ValueError:
        msg = bot.reply_to(
            message,
            "Invalid amount. Please enter a valid positive number:",
            reply_markup=create_cancel_markup()
        )
        bot.register_next_step_handler(msg, process_reseller_settlement_threshold)
        return

    try:
        if not os.path.exists(env_path):
            with open(env_path, 'w') as f:
                pass
        
        set_key(env_path, 'RESELLER_SETTLEMENT_THRESHOLD', str(threshold_val))
        load_dotenv(env_path, override=True)
        
        bot.reply_to(
            message,
            "✅ Reseller Settlement Threshold has been updated successfully!",
            reply_markup=create_main_markup(is_admin=True)
        )
    except Exception as e:
        bot.reply_to(
            message,
            f"❌ Error updating threshold: {str(e)}",
            reply_markup=create_main_markup(is_admin=True)
        )
