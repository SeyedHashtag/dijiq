import json
import os
import datetime
import time
from telebot import types
from utils.command import bot, is_admin
from utils.common import create_main_markup
from utils.api_client import MultiServerAPI
from utils.translations import BUTTON_TRANSLATIONS, get_message_text
from utils.language import get_user_language
import qrcode
import io
import logging
from utils.username_utils import (
    allocate_username,
    build_user_note,
)

TEST_CONFIGS_FILE = '/etc/dijiq/core/scripts/telegrambot/test_configs.json'
TEST_SETTINGS_FILE = '/etc/dijiq/core/scripts/telegrambot/test_settings.json'
TEST_WAITING_LIST_FILE = '/etc/dijiq/core/scripts/telegrambot/waiting_test_users.json'
TEST_TRAFFIC_GB = 1
TEST_DAYS = 30

def load_test_settings():
    try:
        if os.path.exists(TEST_SETTINGS_FILE):
            with open(TEST_SETTINGS_FILE, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    return {"creation_disabled": False}

def save_test_settings(settings):
    os.makedirs(os.path.dirname(TEST_SETTINGS_FILE), exist_ok=True)
    try:
        with open(TEST_SETTINGS_FILE, 'w') as f:
            json.dump(settings, f, indent=4)
    except Exception:
        pass

def is_test_creation_disabled():
    settings = load_test_settings()
    return settings.get("creation_disabled", False)

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

def load_waiting_users():
    try:
        if os.path.exists(TEST_WAITING_LIST_FILE):
            with open(TEST_WAITING_LIST_FILE, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    save_waiting_users({})
    return {}

def save_waiting_users(users):
    os.makedirs(os.path.dirname(TEST_WAITING_LIST_FILE), exist_ok=True)
    with open(TEST_WAITING_LIST_FILE, 'w') as f:
        json.dump(users, f, indent=4)

def _has_used_test_config_from(configs, user_id):
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

def has_used_test_config(user_id):
    return _has_used_test_config_from(load_test_configs(), user_id)

def add_to_waiting_list(user_id, username=None, language=None):
    if has_used_test_config(user_id):
        return False

    waiting_users = load_waiting_users()
    key = str(user_id)
    if key in waiting_users:
        return False

    waiting_users[key] = {
        "telegram_id": user_id,
        "telegram_username": username,
        "language": language,
        "added_at": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }
    save_waiting_users(waiting_users)
    return True

def _mark_test_config_used_in_memory(configs, user_id, username=None, language=None, telegram_username=None, server_id=None):
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
    if server_id:
        entry['server_id'] = server_id

    configs[key] = entry

def mark_test_config_used(user_id, username=None, language=None, telegram_username=None, server_id=None):
    configs = load_test_configs()
    _mark_test_config_used_in_memory(
        configs,
        user_id,
        username=username,
        language=language,
        telegram_username=telegram_username,
        server_id=server_id,
    )
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
    language = get_user_language(user_id)

    # Check if test creation is disabled
    if is_test_creation_disabled():
        if has_used_test_config(user_id):
            bot.reply_to(
                message,
                get_message_text(language, "test_config_used"),
                reply_markup=create_main_markup(is_admin=False, user_id=user_id)
            )
            return

        add_to_waiting_list(user_id, message.from_user.username, language)
        bot.reply_to(
            message,
            get_message_text(language, "test_config_waiting_list"),
            reply_markup=create_main_markup(is_admin=False, user_id=user_id)
        )
        return

    # Check if user has already used a test config
    if has_used_test_config(user_id):
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
    # Check if test creation is disabled
    if is_test_creation_disabled():
        if has_used_test_config(user_id):
            bot.answer_callback_query(call.id)
            bot.edit_message_text(
                get_message_text(language, "test_config_used"),
                chat_id=call.message.chat.id,
                message_id=call.message.message_id
            )
            return

        add_to_waiting_list(user_id, call.from_user.username, language)
        bot.answer_callback_query(call.id)
        bot.edit_message_text(
            get_message_text(language, "test_config_waiting_list"),
            chat_id=call.message.chat.id,
            message_id=call.message.message_id
        )
        return

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

def _send_created_test_config(chat_id, username, user_uri_data, is_automatic=False):
    if user_uri_data and 'normal_sub' in user_uri_data:
        sub_url = user_uri_data['normal_sub']
        ipv4_url = user_uri_data.get('ipv4', '')

        # Create QR code for IPv4 URL when available.
        qr = qrcode.make(ipv4_url or sub_url)
        bio = io.BytesIO()
        qr.save(bio, 'PNG')
        bio.seek(0)

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
            f"Subscription URL:\n{sub_url}\n\n"
            f"Scan the QR code to configure your VPN client."
        )
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

def _create_test_config_with_client(
    user_id,
    chat_id,
    api_client,
    existing_usernames,
    test_configs,
    is_automatic=False,
    language=None,
    telegram_username=None,
):
    if _has_used_test_config_from(test_configs, user_id):
        return False

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

    if not result:
        return False

    _mark_test_config_used_in_memory(
        test_configs,
        user_id,
        username=username,
        language=language,
        telegram_username=telegram_username,
        server_id=api_client.server_id,
    )
    existing_usernames.add(username)

    user_uri_data = api_client.get_user_uri(username)
    _send_created_test_config(chat_id, username, user_uri_data, is_automatic=is_automatic)
    return True

def create_test_config(user_id, chat_id, is_automatic=False, language=None, telegram_username=None, ignore_creation_disabled=False):
    # Check if test creation is disabled
    if is_test_creation_disabled() and not ignore_creation_disabled:
        return False

    configs = load_test_configs()
    if _has_used_test_config_from(configs, user_id):
        return False

    multi_api = MultiServerAPI()

    def allocate(existing_usernames):
        return allocate_username("t", user_id, existing_usernames)

    def create(api_client, username):
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
        return result

    username, result, api_client = multi_api.create_user_with_retry(allocate, create)
    if result:
        _mark_test_config_used_in_memory(
            configs,
            user_id,
            username=username,
            language=language,
            telegram_username=telegram_username,
            server_id=api_client.server_id,
        )
        user_uri_data = api_client.get_user_uri(username)
        _send_created_test_config(chat_id, username, user_uri_data, is_automatic=is_automatic)
        save_test_configs(configs)
        return True

    if not is_automatic:
        bot.send_message(
            chat_id,
            "❌ Failed to create test configuration. Please try again later or contact support.",
            parse_mode="Markdown"
        )
    return False

def _safe_server_weight(value):
    try:
        weight = float(value)
    except (TypeError, ValueError):
        return 1.0
    return weight if weight > 0 else 1.0

def _build_bulk_test_config_state():
    multi_api = MultiServerAPI()
    existing_usernames = set()
    server_states = []

    for index, (server, client) in enumerate(multi_api.iter_clients(include_disabled=True)):
        users = client.get_users()
        if users is None:
            continue

        existing_usernames.update(multi_api.extract_usernames(users))
        if not server.get("enabled", True):
            continue

        weight = _safe_server_weight(server.get("weight", 1))
        server_states.append({
            "index": index,
            "client": client,
            "active_count": multi_api.active_user_count(users),
            "weight": weight,
        })

    return existing_usernames, server_states

def _select_bulk_server_state(server_states):
    if not server_states:
        return None
    return min(
        server_states,
        key=lambda state: (state["active_count"] / state["weight"], state["index"])
    )


# ─── Admin: Reset Test Accounts ───────────────────────────────────────────────

def build_test_accounts_menu():
    settings = load_test_settings()
    disabled = settings.get("creation_disabled", False)
    status_text = "🔴 *Disabled*" if disabled else "🟢 *Enabled*"
    toggle_text = "✅ Enable Test Creation" if disabled else "🚫 Disable Test Creation"
    toggle_action = "enable" if disabled else "disable"
    waiting_count = len(load_waiting_users())

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("⏰ Reset Expired Only", callback_data="reset_test:expired"),
        types.InlineKeyboardButton("♻️ Reset All", callback_data="reset_test:all"),
    )
    markup.add(types.InlineKeyboardButton(toggle_text, callback_data=f"toggle_test_creation:{toggle_action}"))
    markup.add(types.InlineKeyboardButton("👥 Manage Waiting Users", callback_data="manage_waiting"))
    markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data="reset_test:cancel"))

    text = (
        f"🔄 *Manage Test Accounts*\n\n"
        f"Current test creation status: {status_text}\n"
        f"⏳ Waiting Users: *{waiting_count}*\n\n"
        f"Choose an option:\n"
        f"• *Expired Only* — users whose 30-day test config has already expired\n"
        f"• *Reset All* — every user in the database (including active ones)\n\n"
        f"The `test_configs.json` database is *kept intact* for broadcasting."
    )
    return text, markup

def build_waiting_management_menu():
    waiting_count = len(load_waiting_users())
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("🎁 Create & Send Configs", callback_data="waiting_prompt:create"))
    markup.add(types.InlineKeyboardButton("📢 Notify Eligibility", callback_data="waiting_prompt:notify"))
    markup.add(types.InlineKeyboardButton("🗑️ Clear List", callback_data="waiting_action:clear"))
    markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="waiting_action:back"))
    text = (
        f"👥 *Manage Waiting Users*\n\n"
        f"⏳ Waiting Users: *{waiting_count}*\n\n"
        "Choose an action:"
    )
    return text, markup

def build_waiting_chunk_menu(action):
    waiting_count = len(load_waiting_users())
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("20 Users", callback_data=f"waiting_chunk:{action}:20"),
        types.InlineKeyboardButton("50 Users", callback_data=f"waiting_chunk:{action}:50"),
    )
    markup.add(
        types.InlineKeyboardButton("100 Users", callback_data=f"waiting_chunk:{action}:100"),
        types.InlineKeyboardButton("All Users", callback_data=f"waiting_chunk:{action}:all"),
    )
    markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data="waiting_chunk:cancel"))
    text = (
        f"There are {waiting_count} users currently in the waiting list. "
        "Select how many users to process in this chunk:"
    )
    return text, markup

@bot.message_handler(func=lambda message: is_admin(message.from_user.id) and message.text == '🧪 Manage Test Accounts')
def reset_test_accounts_menu(message):
    """Admin command: show reset and settings management."""
    text, markup = build_test_accounts_menu()
    bot.reply_to(
        message,
        text,
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("toggle_test_creation:"))
def handle_toggle_test_creation(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ Unauthorized")
        return

    action = call.data.split(":", 1)[1]
    settings = load_test_settings()

    if action == "enable":
        settings["creation_disabled"] = False
        msg = "🟢 Test account creation enabled."
    else:
        settings["creation_disabled"] = True
        msg = "🔴 Test account creation disabled."

    save_test_settings(settings)
    bot.answer_callback_query(call.id, msg)

    text, markup = build_test_accounts_menu()

    bot.edit_message_text(
        text,
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data == "manage_waiting")
def handle_manage_waiting(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ Unauthorized")
        return

    text, markup = build_waiting_management_menu()
    bot.answer_callback_query(call.id)
    bot.edit_message_text(
        text,
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("waiting_action:"))
def handle_waiting_action(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ Unauthorized")
        return

    action = call.data.split(":", 1)[1]

    if action == "back":
        text, markup = build_test_accounts_menu()
        bot.answer_callback_query(call.id)
        bot.edit_message_text(
            text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=markup,
            parse_mode="Markdown"
        )
        return

    if action == "clear":
        waiting_count = len(load_waiting_users())
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("✅ Confirm", callback_data="waiting_action:clear_confirm"),
            types.InlineKeyboardButton("❌ Cancel", callback_data="manage_waiting"),
        )
        bot.answer_callback_query(call.id)
        bot.edit_message_text(
            f"⚠️ Clear all *{waiting_count}* waiting users?\n\nThis cannot be undone.",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=markup,
            parse_mode="Markdown"
        )
        return

    if action == "clear_confirm":
        save_waiting_users({})
        text, markup = build_waiting_management_menu()
        bot.answer_callback_query(call.id, "Waiting list cleared.")
        bot.edit_message_text(
            f"✅ Waiting list cleared.\n\n{text}",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=markup,
            parse_mode="Markdown"
        )

@bot.callback_query_handler(func=lambda call: call.data.startswith("waiting_prompt:"))
def handle_waiting_prompt(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ Unauthorized")
        return

    action = call.data.split(":", 1)[1]
    if action not in ("create", "notify"):
        bot.answer_callback_query(call.id, "Invalid action.")
        return

    text, markup = build_waiting_chunk_menu(action)
    bot.answer_callback_query(call.id)
    bot.edit_message_text(
        text,
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("waiting_chunk:"))
def handle_waiting_chunk(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ Unauthorized")
        return

    if call.data == "waiting_chunk:cancel":
        text, markup = build_waiting_management_menu()
        bot.answer_callback_query(call.id)
        bot.edit_message_text(
            text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=markup,
            parse_mode="Markdown"
        )
        return

    try:
        _, action, chunk_size = call.data.split(":", 2)
    except ValueError:
        bot.answer_callback_query(call.id, "Invalid chunk.")
        return

    if action not in ("create", "notify"):
        bot.answer_callback_query(call.id, "Invalid action.")
        return

    waiting_users = load_waiting_users()
    if not waiting_users:
        text, markup = build_waiting_management_menu()
        bot.answer_callback_query(call.id, "Waiting list is empty.")
        bot.edit_message_text(
            text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=markup,
            parse_mode="Markdown"
        )
        return

    if chunk_size == "all":
        limit = len(waiting_users)
    else:
        try:
            limit = int(chunk_size)
        except ValueError:
            bot.answer_callback_query(call.id, "Invalid chunk size.")
            return

    selected_users = list(waiting_users.items())[:limit]
    processed_count = 0
    failure_count = 0

    bot.answer_callback_query(call.id)
    bot.edit_message_text(
        f"⏳ Processing {len(selected_users)} waiting users...",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id
    )

    test_configs = None
    existing_usernames = None
    server_states = None
    state_changed = False
    if action == "create":
        test_configs = load_test_configs()
        existing_usernames, server_states = _build_bulk_test_config_state()
        if not server_states:
            text, markup = build_waiting_management_menu()
            bot.edit_message_text(
                f"❌ No healthy enabled VPN servers were available.\n\n{text}",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=markup,
                parse_mode="Markdown"
            )
            return

    for user_key, user_data in selected_users:
        user_id = user_data.get("telegram_id") or int(user_key)
        language = user_data.get("language") or get_user_language(user_id)
        telegram_username = user_data.get("telegram_username")
        success = False

        try:
            if action == "create":
                server_state = _select_bulk_server_state(server_states)
                success = _create_test_config_with_client(
                    user_id,
                    user_id,
                    server_state["client"],
                    existing_usernames,
                    test_configs,
                    is_automatic=True,
                    language=language,
                    telegram_username=telegram_username,
                )
                if success:
                    server_state["active_count"] += 1
            elif action == "notify":
                bot.send_message(user_id, get_message_text(language, "test_config_waitlist_eligible"))
                success = True
        except Exception as e:
            print(f"Waiting list {action} failed for {user_id}: {e}")
            success = False

        if success:
            waiting_users.pop(user_key, None)
            state_changed = True
            processed_count += 1
            if processed_count % 25 == 0:
                save_waiting_users(waiting_users)
                if test_configs is not None:
                    save_test_configs(test_configs)
        else:
            failure_count += 1

        time.sleep(0.1)

    if state_changed:
        save_waiting_users(waiting_users)
        if test_configs is not None:
            save_test_configs(test_configs)

    remaining_count = len(waiting_users)
    text, markup = build_waiting_management_menu()
    bot.edit_message_text(
        f"✅ *Waiting list chunk complete!*\n\n"
        f"• Action: `{action}`\n"
        f"• Processed: *{processed_count}*\n"
        f"• Failed: *{failure_count}*\n"
        f"• Remaining in waiting list: *{remaining_count}*\n\n"
        f"{text}",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
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
