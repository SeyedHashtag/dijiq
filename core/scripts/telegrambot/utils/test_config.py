import json
import os
import datetime
from telebot import types
from utils.command import bot, is_admin
from utils.common import create_main_markup
from utils.api_client import APIClient
from utils.translations import BUTTON_TRANSLATIONS, get_message_text
from utils.language import get_user_language
import qrcode
import io
import logging
from utils.username_utils import (
    allocate_username,
    extract_existing_usernames,
    build_user_note,
    format_username_timestamp,
)

TEST_CONFIGS_FILE = '/etc/dijiq/core/scripts/telegrambot/test_configs.json'

def load_test_configs():
    try:
        if os.path.exists(TEST_CONFIGS_FILE):
            with open(TEST_CONFIGS_FILE, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def save_test_configs(configs):
    os.makedirs(os.path.dirname(TEST_CONFIGS_FILE), exist_ok=True)
    with open(TEST_CONFIGS_FILE, 'w') as f:
        json.dump(configs, f, indent=4)

def has_used_test_config(user_id):
    configs = load_test_configs()
    key = str(user_id)
    if key not in configs:
        return False
    entry = configs[key]
    reset_at_str = entry.get('reset_at')
    if reset_at_str:
        # User was reset — check if they have received a new test config since the reset
        used_at_str = entry.get('used_at')
        if used_at_str:
            try:
                used_at = datetime.datetime.strptime(used_at_str, '%Y-%m-%d %H:%M:%S')
                reset_at = datetime.datetime.strptime(reset_at_str, '%Y-%m-%d %H:%M:%S')
                # If used_at is older than reset_at, the user has not yet collected their new test config
                if used_at <= reset_at:
                    return False
            except Exception:
                return False
    return True

def mark_test_config_used(user_id, username=None, language=None, telegram_username=None):
    configs = load_test_configs()
    key = str(user_id)
    # Preserve existing history fields (reset_at, reset_count, original used_at, etc.)
    existing = configs.get(key, {})
    entry = dict(existing)
    entry['used_at'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    entry['telegram_id'] = user_id
    if username:
        entry['username'] = username
    if language:
        entry['language'] = language
    if telegram_username:
        entry['telegram_username'] = telegram_username

    configs[key] = entry
    save_test_configs(configs)


def reset_test_users(mode='expired'):
    """
    Mark test users as eligible to receive a new test config.

    mode='expired'  — only reset users whose test config has expired (>30 days old)
    mode='all'      — reset every user in the database

    Returns the number of users that were reset.
    """
    configs = load_test_configs()
    now = datetime.datetime.now()
    reset_ts = now.strftime('%Y-%m-%d %H:%M:%S')
    count = 0
    for key, entry in configs.items():
        # Skip users who are already in a reset-eligible state
        if not has_used_test_config(key):
            continue
        if mode == 'expired':
            used_at_str = entry.get('used_at')
            if not used_at_str:
                continue
            try:
                used_at = datetime.datetime.strptime(used_at_str, '%Y-%m-%d %H:%M:%S')
            except Exception:
                continue
            if (now - used_at).days < 30:
                continue  # Config still active, skip
        entry['reset_at'] = reset_ts
        entry['reset_count'] = entry.get('reset_count', 0) + 1
        count += 1
    save_test_configs(configs)
    return count

@bot.message_handler(func=lambda message: any(
    message.text == translations["test_config"] 
    for translations in BUTTON_TRANSLATIONS.values()
))
def test_config(message):
    user_id = message.from_user.id
      # Check if user has already used a test config
    if has_used_test_config(user_id):
        language = get_user_language(user_id)
        bot.reply_to(
            message,
            get_message_text(language, "test_config_used"),
            reply_markup=create_main_markup(is_admin=False, user_id=user_id)
        )
        return
    
    # Ask for confirmation
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ Yes, create my test config", callback_data="confirm_test_config"),
        types.InlineKeyboardButton("❌ No, cancel", callback_data="cancel_test_config")
    )
    
    bot.reply_to(
        message,
        "🎁 You're about to create a free test configuration (1GB for 30 days). Would you like to continue?",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data == "cancel_test_config")
def handle_cancel_test_config(call):
    bot.answer_callback_query(call.id)
    bot.edit_message_text(
        "❌ Test config creation cancelled.",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id
    )

@bot.callback_query_handler(func=lambda call: call.data == "confirm_test_config")
def handle_confirm_test_config(call):
    user_id = call.from_user.id
    language = get_user_language(user_id)
    # Double check if user has already used a test config
    if has_used_test_config(user_id):
        bot.answer_callback_query(call.id)
        bot.edit_message_text(
            get_message_text(language, "test_config_used"),
            chat_id=call.message.chat.id,
            message_id=call.message.message_id
        )
        return

    # Display processing message
    bot.answer_callback_query(call.id)
    bot.edit_message_text(
        "⏳ Creating your test configuration...",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id
    )

    create_test_config(user_id, call.message.chat.id, is_automatic=False, language=language, telegram_username=call.from_user.username)

def create_test_config(user_id, chat_id, is_automatic=False, language=None, telegram_username=None):
    # Double check if user has already used a test config
    if has_used_test_config(user_id):
        return False

    # Constants for test config
    TEST_TRAFFIC_GB = 1  # 1 GB
    TEST_DAYS = 30       # 30 days

    api_client = APIClient()
    existing_usernames = extract_existing_usernames(api_client.get_users())
    username = allocate_username("t", user_id, existing_usernames)
    note_payload = build_user_note(
        username=username,
        traffic_limit=TEST_TRAFFIC_GB,
        expiration_days=TEST_DAYS,
        unlimited=True,
        note_text="test_config",
    )

    result = api_client.add_user(
        username,
        TEST_TRAFFIC_GB,
        TEST_DAYS,
        unlimited=True,
        note=note_payload,
    )
    if result is None:
        result = api_client.add_user(username, TEST_TRAFFIC_GB, TEST_DAYS, unlimited=True)
        if result is not None:
            logging.getLogger("dijiq.usernames").warning(
                "Created test user without note fallback. user_id=%s username=%s",
                user_id,
                username,
            )

    if result:
        # Mark the test config as used (save username as well)
        mark_test_config_used(user_id, username=username, language=language, telegram_username=telegram_username)

        # Get user URI from API
        user_uri_data = api_client.get_user_uri(username)
        if user_uri_data and 'normal_sub' in user_uri_data:
            sub_url = user_uri_data['normal_sub']
            ipv4_url = user_uri_data.get('ipv4', '')

            # Create QR code for subscription URL
            qr = qrcode.make(sub_url)
            bio = io.BytesIO()
            qr.save(bio, 'PNG')
            bio.seek(0)

            # Format success message
            if is_automatic:
                prefix = "🎁 Your free test configuration (1GB - 30 days) has been created automatically!\n\n"
            else:
                prefix = "✅ Your test configuration has been created successfully!\n\n"

            success_message = prefix
            success_message += (
                f"📊 Test Plan Details:\n"
                f"- 🔹 Data: {TEST_TRAFFIC_GB} GB\n"
                f"- 🔹 Duration: {TEST_DAYS} days\n"
                f"- 🔹 Unlimited Devices: Yes\n"
                f"- 🔹 Username: `{username}`\n\n"
            )

            if ipv4_url:
                success_message += f"IPv4 URL: `{ipv4_url}`\n\n"

            success_message += (
                f"Subscription URL:\n`{sub_url}`\n\n"
                f"Scan the QR code to configure your VPN client."
            )
            # Send the QR code with config details
            bot.send_photo(
                chat_id,
                photo=bio,
                caption=success_message,
                parse_mode="Markdown"
            )
        else:
            bot.send_message(
                chat_id,
                f"✅ Your test configuration has been created, but the subscription URL could not be generated. Please contact support.",
                parse_mode="Markdown"
            )
        return True
    else:
        if not is_automatic:
            bot.send_message(
                chat_id,
                "❌ Failed to create test configuration. Please try again later or contact support.",
                parse_mode="Markdown"
            )
        return False


# ─── Admin: Reset Test Accounts ───────────────────────────────────────────────

@bot.message_handler(func=lambda message: is_admin(message.from_user.id) and message.text == '🧪 Manage Test Accounts')
def reset_test_accounts_menu(message):
    """Admin command: show reset mode selection."""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("⏰ Reset Expired Only", callback_data="reset_test:expired"),
        types.InlineKeyboardButton("♻️ Reset All", callback_data="reset_test:all"),
    )
    markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data="reset_test:cancel"))
    bot.reply_to(
        message,
        "🔄 *Reset Test Account Eligibility*\n\n"
        "Choose which users to reset:\n"
        "• *Expired Only* — users whose 30-day test config has already expired\n"
        "• *Reset All* — every user in the database (including active ones)\n\n"
        "The `test_configs.json` database is *kept intact* for broadcasting.",
        reply_markup=markup,
        parse_mode="Markdown"
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("reset_test:"))
def handle_reset_test_selection(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ Unauthorized")
        return

    mode = call.data.split(":", 1)[1]

    if mode == "cancel":
        bot.answer_callback_query(call.id)
        bot.edit_message_text(
            "❌ Reset cancelled.",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id
        )
        return

    # Ask for confirmation before proceeding
    label = "expired users only" if mode == "expired" else "ALL users"
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✅ Confirm", callback_data=f"reset_test_confirm:{mode}"),
        types.InlineKeyboardButton("❌ Cancel", callback_data="reset_test:cancel"),
    )
    bot.answer_callback_query(call.id)
    bot.edit_message_text(
        f"⚠️ You are about to reset test eligibility for *{label}*.\n\n"
        "The original database entries will be preserved. Reset users will be able to request a new test config.",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=markup,
        parse_mode="Markdown"
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("reset_test_confirm:"))
def handle_reset_test_confirm(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ Unauthorized")
        return

    mode = call.data.split(":", 1)[1]
    bot.answer_callback_query(call.id)

    count = reset_test_users(mode=mode)

    label = "expired" if mode == "expired" else "all"
    bot.edit_message_text(
        f"✅ *Reset complete!*\n\n"
        f"• Mode: `{label}`\n"
        f"• Users reset: *{count}*\n\n"
        f"These users can now request a new test config. "
        f"Their entries in the database are preserved for broadcasting.",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        parse_mode="Markdown"
    )
